"""会籍履约与门禁授权联动。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.platform.models.access import AccessGrant
from app.systems.platform.models.commerce import Order
from app.systems.gym.models.membership import (
    ConsumptionKind,
    ConsumptionSource,
    Membership,
    MembershipConsumption,
    MembershipOrderAction,
    MembershipOrderLink,
    MembershipProduct,
    MembershipProductAccessPoint,
    MembershipStatus,
    ProductType,
)
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.notifications import write_notification
from app.systems.platform.services.sync_queue import GrantSyncMessage, publish_grant_sync


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def product_access_point_ids(db: Session, product_id: int) -> list[int]:
    rows = db.scalars(
        select(MembershipProductAccessPoint.access_point_id).where(
            MembershipProductAccessPoint.product_id == product_id
        )
    ).all()
    return list(rows)


def validate_product_for_sale(
    product: MembershipProduct, access_point_ids: list[int], *, require_active: bool = True
) -> None:
    if require_active and not product.is_active:
        raise AppError("product_inactive", "卡种已停用，不可办卡", status_code=400)
    if not access_point_ids:
        raise AppError("product_no_access_points", "卡种未绑定门禁点，不可售卖", status_code=400)
    if product.product_type == ProductType.TERM.value:
        if not product.duration_days or product.duration_days <= 0:
            raise AppError("invalid_product", "期限卡必须配置有效天数", status_code=400)
    elif product.product_type == ProductType.COUNT.value:
        if not product.session_count or product.session_count <= 0:
            raise AppError("invalid_product", "次卡必须配置次数", status_code=400)
    elif product.product_type == ProductType.VALUE.value:
        if product.stored_value is None or product.stored_value <= 0:
            raise AppError("invalid_product", "储值卡必须配置储值额度", status_code=400)
    else:
        raise AppError("invalid_product", "未知卡种类型", status_code=400)


def sync_grants_for_membership(db: Session, membership: Membership, *, revoke: bool = False) -> None:
    """按卡种门禁同步授权；revoke=True 时撤销关联授权。"""
    point_ids = product_access_point_ids(db, membership.product_id)
    now = _now()
    for point_id in point_ids:
        existing = list(
            db.scalars(
                select(AccessGrant).where(
                    AccessGrant.member_id == membership.member_id,
                    AccessGrant.access_point_id == point_id,
                    AccessGrant.merchant_id == membership.merchant_id,
                    AccessGrant.revoked.is_(False),
                )
            ).all()
        )
        if revoke:
            for g in existing:
                g.revoked = True
                publish_grant_sync(
                    GrantSyncMessage(
                        grant_id=g.id,
                        access_point_id=g.access_point_id,
                        member_id=g.member_id,
                        action="revoke",
                    )
                )
            continue

        # 生效：更新或创建授权
        valid_until = membership.ends_at
        if membership.product_type == ProductType.COUNT.value:
            # 次卡：授权到较远日期，实际以会籍状态为准；停卡时撤销
            valid_until = now + timedelta(days=3650)
        elif membership.product_type == ProductType.VALUE.value:
            valid_until = now + timedelta(days=3650)
        if valid_until is None:
            valid_until = now + timedelta(days=30)

        if existing:
            g = existing[0]
            g.valid_from = membership.starts_at or now
            g.valid_until = valid_until
            g.revoked = False
            db.flush()
            publish_grant_sync(
                GrantSyncMessage(
                    grant_id=g.id,
                    access_point_id=g.access_point_id,
                    member_id=g.member_id,
                    action="upsert",
                )
            )
        else:
            g = AccessGrant(
                member_id=membership.member_id,
                access_point_id=point_id,
                merchant_id=membership.merchant_id,
                valid_from=membership.starts_at or now,
                valid_until=valid_until,
                revoked=False,
            )
            db.add(g)
            db.flush()
            publish_grant_sync(
                GrantSyncMessage(
                    grant_id=g.id,
                    access_point_id=g.access_point_id,
                    member_id=g.member_id,
                    action="upsert",
                )
            )


def _create_membership_from_product(
    db: Session, *, product: MembershipProduct, member_id: int, merchant_id: int
) -> Membership:
    now = _now()
    m = Membership(
        merchant_id=merchant_id,
        member_id=member_id,
        product_id=product.id,
        product_type=product.product_type,
        status=MembershipStatus.ACTIVE.value,
        starts_at=now,
        ends_at=None,
        remaining_sessions=None,
        balance=None,
    )
    if product.product_type == ProductType.TERM.value:
        m.ends_at = now + timedelta(days=int(product.duration_days))
    elif product.product_type == ProductType.COUNT.value:
        m.remaining_sessions = int(product.session_count)
        m.ends_at = now + timedelta(days=3650)
    else:
        m.balance = Decimal(product.stored_value)
        m.ends_at = now + timedelta(days=3650)
    db.add(m)
    db.flush()
    sync_grants_for_membership(db, m, revoke=False)
    return m


def _renew_membership(db: Session, membership: Membership, product: MembershipProduct) -> Membership:
    now = _now()
    if membership.status == MembershipStatus.VOID.value:
        raise AppError("invalid_state", "已作废会籍不可续卡", status_code=400)

    if product.product_type == ProductType.TERM.value:
        ends = _ensure_aware(membership.ends_at)
        base = ends if ends and ends > now else now
        membership.ends_at = base + timedelta(days=int(product.duration_days))
        membership.starts_at = _ensure_aware(membership.starts_at) or now
        membership.status = MembershipStatus.ACTIVE.value
    elif product.product_type == ProductType.COUNT.value:
        cur = membership.remaining_sessions or 0
        membership.remaining_sessions = cur + int(product.session_count)
        membership.status = MembershipStatus.ACTIVE.value
    else:
        cur = membership.balance or Decimal("0")
        membership.balance = cur + Decimal(product.stored_value)
        membership.status = MembershipStatus.ACTIVE.value

    db.flush()
    sync_grants_for_membership(db, membership, revoke=False)
    return membership


def fulfill_membership_order(db: Session, order: Order, *, actor_staff_id: int | None = None) -> Membership | None:
    """支付成功后履约会籍；非 membership 订单返回 None。"""
    if order.order_type != "membership":
        return None

    link = db.scalar(select(MembershipOrderLink).where(MembershipOrderLink.order_id == order.id))
    if link is None:
        raise AppError("fulfill_missing_link", "会籍订单缺少履约关联", status_code=500)
    if link.fulfilled_membership_id is not None:
        return db.get(Membership, link.fulfilled_membership_id)

    product = db.get(MembershipProduct, link.product_id)
    if product is None:
        link.fulfill_error = "product_missing"
        db.flush()
        raise AppError("fulfill_failed", "卡种不存在，无法履约", status_code=500)

    try:
        if link.action == MembershipOrderAction.RENEW.value:
            if link.target_membership_id is None:
                raise AppError("fulfill_failed", "续卡缺少目标会籍", status_code=400)
            membership = db.get(Membership, link.target_membership_id)
            if membership is None:
                raise AppError("fulfill_failed", "目标会籍不存在", status_code=404)
            membership = _renew_membership(db, membership, product)
        else:
            membership = _create_membership_from_product(
                db, product=product, member_id=link.member_id, merchant_id=order.merchant_id
            )
        link.fulfilled_membership_id = membership.id
        link.fulfill_error = None
        write_audit(
            db,
            action="membership.fulfill",
            target_type="membership",
            target_id=membership.id,
            summary=f"订单 {order.id} 履约 {link.action}",
            actor_staff_id=actor_staff_id,
            site_id=order.site_id,
            merchant_id=order.merchant_id,
        )
        write_notification(
            db,
            site_id=order.site_id,
            merchant_id=order.merchant_id,
            member_id=link.member_id,
            event_type="membership.fulfilled",
            title="会籍开通成功",
            body=f"订单 #{order.id} 会籍已履约（{link.action}）",
        )
        db.flush()
        return membership
    except AppError as exc:
        link.fulfill_error = exc.code
        db.flush()
        raise


_EDITABLE_STATUS = {
    MembershipStatus.ACTIVE.value,
    MembershipStatus.FROZEN.value,
    MembershipStatus.EXPIRED.value,
}


def update_membership(
    db: Session,
    membership: Membership,
    *,
    actor_staff_id: int,
    site_id: int,
    member_id: int | None = None,
    product_id: int | None = None,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
    remaining_sessions: int | None = None,
    balance: Decimal | None = None,
    status: str | None = None,
    remark: str | None = None,
    fields_set: set[str] | None = None,
) -> Membership:
    """前台校正会籍档案；超管可改正会员/卡种。改完同步门禁。"""
    if membership.status == MembershipStatus.VOID.value:
        raise AppError("invalid_state", "已作废会籍不可编辑", status_code=400)
    changed = fields_set or set()
    identity_changed = ("member_id" in changed and member_id != membership.member_id) or (
        "product_id" in changed and product_id != membership.product_id
    )
    if identity_changed:
        # 先按旧会员/卡种撤授权，避免改挂后旧人仍能进门
        sync_grants_for_membership(db, membership, revoke=True)

    if "member_id" in changed:
        if member_id is None:
            raise AppError("invalid_member", "会员不能为空", status_code=400)
        membership.member_id = member_id
    if "product_id" in changed:
        if product_id is None:
            raise AppError("invalid_product", "卡种不能为空", status_code=400)
        product = db.get(MembershipProduct, product_id)
        if product is None or product.merchant_id != membership.merchant_id:
            raise AppError("not_found", "卡种不存在或不属于本商户", status_code=404)
        membership.product_id = product.id
        membership.product_type = product.product_type

    if "starts_at" in changed:
        membership.starts_at = _ensure_aware(starts_at)
    if "ends_at" in changed:
        membership.ends_at = _ensure_aware(ends_at)
    if "remaining_sessions" in changed:
        if remaining_sessions is not None and remaining_sessions < 0:
            raise AppError("invalid_sessions", "剩余次数不能为负数", status_code=400)
        membership.remaining_sessions = remaining_sessions
    if "balance" in changed:
        if balance is not None and balance < 0:
            raise AppError("invalid_balance", "余额不能为负数", status_code=400)
        membership.balance = balance
    if "status" in changed:
        if status not in _EDITABLE_STATUS:
            raise AppError("invalid_status", "会籍状态无效", status_code=400)
        membership.status = status
    if "remark" in changed:
        text = (remark or "").strip()
        membership.remark = text or None

    revoke = membership.status in {
        MembershipStatus.FROZEN.value,
        MembershipStatus.EXPIRED.value,
        MembershipStatus.VOID.value,
    }
    sync_grants_for_membership(db, membership, revoke=revoke)
    write_audit(
        db,
        action="membership.update",
        target_type="membership",
        target_id=membership.id,
        summary="编辑会籍档案",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=membership.merchant_id,
    )
    db.flush()
    return membership


def freeze_membership(db: Session, membership: Membership, *, actor_staff_id: int, site_id: int) -> Membership:
    if membership.status != MembershipStatus.ACTIVE.value:
        raise AppError("invalid_state", "仅生效中会籍可停卡", status_code=400)
    membership.status = MembershipStatus.FROZEN.value
    sync_grants_for_membership(db, membership, revoke=True)
    write_audit(
        db,
        action="membership.freeze",
        target_type="membership",
        target_id=membership.id,
        summary="停卡",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=membership.merchant_id,
    )
    db.flush()
    return membership


def consume_membership(
    db: Session,
    membership: Membership,
    *,
    actor_staff_id: int | None,
    site_id: int | None = None,
    sessions: int | None = None,
    amount: Decimal | None = None,
    source: str = ConsumptionSource.FRONT_DESK.value,
    note: str | None = None,
) -> MembershipConsumption:
    """次卡销次 / 储值卡按次计费；期限卡不参与销次。

    次卡传 sessions（默认 1），储值卡传 amount。扣减到 0 时自动置为已过期状态并撤授权。
    """
    if membership.status != MembershipStatus.ACTIVE.value:
        raise AppError("invalid_state", "仅生效中会籍可销次", status_code=400)

    now = _now()
    ends = _ensure_aware(membership.ends_at)
    if ends is not None and ends < now:
        membership.status = MembershipStatus.EXPIRED.value
        sync_grants_for_membership(db, membership, revoke=True)
        db.flush()
        raise AppError("membership_expired", "会籍已到期，不可销次", status_code=400)

    if membership.product_type == ProductType.COUNT.value:
        count = 1 if sessions is None else int(sessions)
        if count <= 0:
            raise AppError("invalid_sessions", "销次数量必须大于 0", status_code=400)
        remaining = membership.remaining_sessions or 0
        if remaining < count:
            raise AppError("no_sessions", f"剩余次数不足，当前剩余 {remaining} 次", status_code=400)
        membership.remaining_sessions = remaining - count
        kind = ConsumptionKind.SESSION.value
        used_sessions: int | None = count
        used_amount: Decimal | None = None
        if membership.remaining_sessions <= 0:
            membership.status = MembershipStatus.EXPIRED.value
    elif membership.product_type == ProductType.VALUE.value:
        if amount is None or amount <= 0:
            raise AppError("invalid_amount", "储值卡计费金额必须大于 0", status_code=400)
        balance = membership.balance or Decimal("0")
        if balance < amount:
            raise AppError("insufficient_balance", f"余额不足，当前余额 ¥{balance}", status_code=400)
        membership.balance = balance - amount
        kind = ConsumptionKind.VALUE.value
        used_sessions = None
        used_amount = Decimal(amount)
        if membership.balance <= 0:
            membership.status = MembershipStatus.EXPIRED.value
    else:
        raise AppError("unsupported_product", "期限卡按时段通行，无需销次", status_code=400)

    record = MembershipConsumption(
        merchant_id=membership.merchant_id,
        membership_id=membership.id,
        member_id=membership.member_id,
        kind=kind,
        sessions=used_sessions,
        amount=used_amount,
        remaining_sessions_after=membership.remaining_sessions,
        balance_after=membership.balance,
        source=source,
        note=(note or "").strip() or None,
        actor_staff_id=actor_staff_id,
    )
    db.add(record)
    if membership.status == MembershipStatus.EXPIRED.value:
        sync_grants_for_membership(db, membership, revoke=True)
    detail = f"{used_sessions} 次" if used_sessions is not None else f"¥{used_amount}"
    write_audit(
        db,
        action="membership.consume",
        target_type="membership",
        target_id=membership.id,
        summary=f"销次 {detail}，剩余次数 {membership.remaining_sessions}，余额 {membership.balance}",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=membership.merchant_id,
    )
    db.flush()
    return record


def void_membership(db: Session, membership: Membership, *, actor_staff_id: int, site_id: int) -> Membership:
    if membership.status == MembershipStatus.VOID.value:
        return membership
    membership.status = MembershipStatus.VOID.value
    sync_grants_for_membership(db, membership, revoke=True)
    write_audit(
        db,
        action="membership.void",
        target_type="membership",
        target_id=membership.id,
        summary="作废会籍",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=membership.merchant_id,
    )
    db.flush()
    return membership
