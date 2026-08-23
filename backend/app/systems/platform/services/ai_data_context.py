"""按提示词模版的数据源拉取分析上下文。"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import RequestContext
from app.systems.platform.models.audit import AuditLog
from app.systems.platform.models.commerce import Order
from app.systems.platform.models.member import Member, MerchantMember
from app.systems.platform.models.org import Merchant
from app.systems.platform.models.promoter import PromoterCode
from app.systems.platform.models.access import AccessEvent


def _day_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"不可序列化: {type(obj)}")


def _dump(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default)


def _merchant_name(db: Session, merchant_id: int | None) -> str:
    if merchant_id is None:
        return "全场地"
    row = db.get(Merchant, merchant_id)
    return row.name if row else f"商户#{merchant_id}"


def _order_filters(ctx: RequestContext, merchant_id: int | None):
    filters = [Order.site_id == ctx.site_id]
    if merchant_id is not None:
        filters.append(Order.merchant_id == merchant_id)
    elif not ctx.is_site_wide:
        mid = ctx.resolve_merchant_id()
        filters.append(Order.merchant_id == mid)
    return filters


def gather_analysis_context(
    db: Session,
    ctx: RequestContext,
    *,
    data_source: str,
    date_from: date,
    date_to: date,
    merchant_id: int | None = None,
) -> dict[str, Any]:
    """按数据源聚合 JSON 上下文，供提示词填充。"""
    start, end = _day_bounds(date_from, date_to)
    scope_name = _merchant_name(db, merchant_id)
    base = {
        "site_id": ctx.site_id,
        "merchant_id": merchant_id,
        "merchant_name": scope_name,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
    }

    source = (data_source or "operations").strip().lower()

    if source == "audit_logs":
        stmt = select(AuditLog).where(
            AuditLog.site_id == ctx.site_id,
            AuditLog.created_at >= start,
            AuditLog.created_at < end,
        )
        if merchant_id is not None:
            stmt = stmt.where(AuditLog.merchant_id == merchant_id)
        elif not ctx.is_site_wide:
            stmt = stmt.where(AuditLog.merchant_id == ctx.resolve_merchant_id())
        rows = db.scalars(stmt.order_by(AuditLog.id.desc()).limit(200)).all()
        by_action: dict[str, int] = {}
        by_channel: dict[str, int] = {}
        failures = 0
        for r in rows:
            by_action[r.action] = by_action.get(r.action, 0) + 1
            ch = r.client_channel or "unknown"
            by_channel[ch] = by_channel.get(ch, 0) + 1
            if r.status == "failure":
                failures += 1
        return {
            **base,
            "summary": {
                "total_logs": len(rows),
                "failure_count": failures,
                "top_actions": sorted(by_action.items(), key=lambda x: -x[1])[:10],
                "by_client_channel": by_channel,
            },
            "recent_logs": [
                {
                    "time": r.created_at,
                    "action": r.action,
                    "module": r.module,
                    "actor": r.actor_name or r.actor_account,
                    "client_channel": r.client_channel,
                    "summary": r.summary,
                    "status": r.status,
                    "request_path": r.request_path,
                }
                for r in rows[:80]
            ],
        }

    if source == "members":
        filters = [Member.site_id == ctx.site_id]
        if merchant_id is not None:
            mids = select(MerchantMember.member_id).where(MerchantMember.merchant_id == merchant_id)
            filters.append(Member.id.in_(mids))
        elif not ctx.is_site_wide:
            mid = ctx.resolve_merchant_id()
            mids = select(MerchantMember.member_id).where(MerchantMember.merchant_id == mid)
            filters.append(Member.id.in_(mids))
        total = db.scalar(select(func.count()).select_from(Member).where(*filters)) or 0
        with_face = db.scalar(
            select(func.count()).select_from(Member).where(*filters, Member.face_status == "registered")
        ) or 0
        with_pwd = db.scalar(
            select(func.count()).select_from(Member).where(*filters, Member.password_hash.is_not(None))
        ) or 0
        new_in_range = db.scalar(
            select(func.count()).select_from(Member).where(
                *filters, Member.created_at >= start, Member.created_at < end
            )
        ) or 0
        recent = db.scalars(
            select(Member).where(*filters).order_by(Member.id.desc()).limit(30)
        ).all()
        return {
            **base,
            "summary": {
                "total_members": total,
                "face_registered": with_face,
                "has_password": with_pwd,
                "new_members_in_range": new_in_range,
            },
            "recent_members": [
                {
                    "id": m.id,
                    "name": m.name,
                    "phone_tail": (m.phone or "")[-4:] if m.phone else None,
                    "created_at": m.created_at,
                    "gender": m.gender,
                }
                for m in recent
            ],
        }

    if source == "orders":
        filters = _order_filters(ctx, merchant_id)
        filters.extend([Order.created_at >= start, Order.created_at < end])
        rows = db.scalars(select(Order).where(*filters).order_by(Order.id.desc()).limit(100)).all()
        paid = [o for o in rows if o.status in ("paid", "completed", "refunded_partial")]
        amount_sum = sum(float(o.amount or 0) for o in paid)
        by_status: dict[str, int] = {}
        for o in rows:
            by_status[o.status] = by_status.get(o.status, 0) + 1
        return {
            **base,
            "summary": {
                "order_count": len(rows),
                "paid_count": len(paid),
                "paid_amount": amount_sum,
                "by_status": by_status,
            },
            "recent_orders": [
                {
                    "id": o.id,
                    "title": o.title,
                    "amount": o.amount,
                    "status": o.status,
                    "order_type": o.order_type,
                    "created_at": o.created_at,
                }
                for o in rows[:50]
            ],
        }

    if source == "promotion":
        promos = db.scalars(
            select(PromoterCode).where(PromoterCode.site_id == ctx.site_id).order_by(PromoterCode.id.desc()).limit(50)
        ).all()
        active = sum(1 for p in promos if p.is_active)
        top_visits = sorted(promos, key=lambda p: p.visit_count or 0, reverse=True)[:15]
        return {
            **base,
            "summary": {
                "promoter_code_count": len(promos),
                "active_count": active,
                "total_visit_count": sum(p.visit_count or 0 for p in promos),
            },
            "top_promoters": [
                {
                    "code": p.code,
                    "name": p.name,
                    "subject_type": p.subject_type,
                    "visit_count": p.visit_count,
                    "is_active": p.is_active,
                }
                for p in top_visits
            ],
        }

    if source == "access":
        from app.systems.platform.models.access import AccessPoint, AccessDevice

        stmt = (
            select(AccessEvent)
            .join(AccessPoint, AccessEvent.access_point_id == AccessPoint.id)
            .where(
                AccessPoint.site_id == ctx.site_id,
                AccessEvent.created_at >= start,
                AccessEvent.created_at < end,
            )
        )
        if merchant_id is not None:
            stmt = stmt.where(AccessPoint.merchant_id == merchant_id)
        rows = db.scalars(stmt.order_by(AccessEvent.id.desc()).limit(150)).all()
        granted = sum(1 for r in rows if r.allowed)
        denied = sum(1 for r in rows if not r.allowed)
        return {
            **base,
            "summary": {
                "event_count": len(rows),
                "granted": granted,
                "denied": denied,
            },
            "recent_events": [
                {
                    "time": r.created_at,
                    "allowed": r.allowed,
                    "member_id": r.member_id,
                    "device_id": r.device_id,
                    "reason": r.reason,
                }
                for r in rows[:60]
            ],
        }

    if source == "membership":
        try:
            from app.systems.gym.models.membership import Membership

            stmt = select(Membership).where(
                Membership.created_at >= start,
                Membership.created_at < end,
            )
            if merchant_id is not None:
                stmt = stmt.where(Membership.merchant_id == merchant_id)
            elif not ctx.is_site_wide:
                stmt = stmt.where(Membership.merchant_id == ctx.resolve_merchant_id())
            rows = db.scalars(stmt.order_by(Membership.id.desc()).limit(80)).all()
            active = sum(1 for m in rows if m.status == "active")
            return {
                **base,
                "summary": {
                    "membership_records_in_range": len(rows),
                    "active_in_sample": active,
                },
                "memberships": [
                    {
                        "id": m.id,
                        "member_id": m.member_id,
                        "product_id": m.product_id,
                        "product_type": m.product_type,
                        "status": m.status,
                        "starts_at": m.starts_at,
                        "ends_at": m.ends_at,
                    }
                    for m in rows[:40]
                ],
            }
        except Exception:
            return {**base, "summary": {"note": "会籍模块数据不可用"}, "memberships": []}

    if source == "catering":
        try:
            filters = _order_filters(ctx, merchant_id)
            filters.extend(
                [
                    Order.order_type == "catering",
                    Order.created_at >= start,
                    Order.created_at < end,
                ]
            )
            rows = db.scalars(select(Order).where(*filters).order_by(Order.id.desc()).limit(80)).all()
            amount = sum(float(o.amount or 0) for o in rows if o.status in ("paid", "completed"))
            return {
                **base,
                "summary": {
                    "catering_order_count": len(rows),
                    "paid_amount": amount,
                },
                "orders": [
                    {"id": o.id, "title": o.title, "amount": o.amount, "status": o.status, "created_at": o.created_at}
                    for o in rows[:40]
                ],
            }
        except Exception:
            return {**base, "summary": {"note": "餐饮订单数据不可用"}, "orders": []}

    # operations：综合经营概览
    order_filters = _order_filters(ctx, merchant_id)
    order_filters.extend([Order.created_at >= start, Order.created_at < end])
    orders = db.scalars(select(Order).where(*order_filters).order_by(Order.id.desc()).limit(60)).all()
    paid_orders = [o for o in orders if o.status in ("paid", "completed", "refunded_partial")]
    member_filters = [Member.site_id == ctx.site_id]
    if merchant_id is not None:
        mids = select(MerchantMember.member_id).where(MerchantMember.merchant_id == merchant_id)
        member_filters.append(Member.id.in_(mids))
    elif not ctx.is_site_wide:
        mid = ctx.resolve_merchant_id()
        mids = select(MerchantMember.member_id).where(MerchantMember.merchant_id == mid)
        member_filters.append(Member.id.in_(mids))
    member_total = db.scalar(select(func.count()).select_from(Member).where(*member_filters)) or 0
    audit_filters = [
        AuditLog.site_id == ctx.site_id,
        AuditLog.created_at >= start,
        AuditLog.created_at < end,
    ]
    if merchant_id is not None:
        audit_filters.append(AuditLog.merchant_id == merchant_id)
    elif not ctx.is_site_wide:
        audit_filters.append(AuditLog.merchant_id == ctx.resolve_merchant_id())
    audit_count = db.scalar(select(func.count()).select_from(AuditLog).where(*audit_filters)) or 0
    merchant_stmt = select(Merchant).where(Merchant.site_id == ctx.site_id)
    if merchant_id is not None:
        merchant_stmt = merchant_stmt.where(Merchant.id == merchant_id)
    merchants = db.scalars(merchant_stmt).all()
    return {
        **base,
        "summary": {
            "merchant_count": len(merchants),
            "member_total": member_total,
            "orders_in_range": len(orders),
            "paid_amount_in_range": sum(float(o.amount or 0) for o in paid_orders),
            "audit_logs_in_range": audit_count,
        },
        "merchants": [{"id": m.id, "name": m.name, "status": m.status} for m in merchants],
        "recent_orders": [
            {"id": o.id, "title": o.title, "amount": o.amount, "status": o.status, "order_type": o.order_type}
            for o in orders[:25]
        ],
    }


def render_prompt(template: str, *, data_json: str, ctx_vars: dict[str, str]) -> str:
    """渲染用户提示词模版中的占位符。"""
    text = template
    text = text.replace("{{data}}", data_json)
    for key, val in ctx_vars.items():
        text = text.replace(f"{{{{{key}}}}}", val)
    return text


def context_as_json(db: Session, ctx: RequestContext, **kwargs) -> str:
    payload = gather_analysis_context(db, ctx, **kwargs)
    return _dump(payload)
