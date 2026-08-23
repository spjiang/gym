"""经营报表 API。"""

import csv
import io
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.systems.platform.services.reports import (
    list_commerce_payments,
    summarize_activity,
    summarize_commerce,
    summarize_course,
    summarize_inventory,
    summarize_membership,
    summarize_revenue_split,
)

router = APIRouter(prefix="/reports", tags=["reports"])


class BreakdownRow(BaseModel):
    charge_total: Decimal
    refund_total: Decimal
    net_total: Decimal


class ChannelRow(BreakdownRow):
    channel: str


class OrderTypeRow(BreakdownRow):
    order_type: str


class CommerceSummaryOut(BaseModel):
    date_from: date
    date_to: date
    merchant_id: int | None
    charge_total: Decimal
    refund_total: Decimal
    net_total: Decimal
    by_channel: list[ChannelRow]
    by_order_type: list[OrderTypeRow]


def _resolve_report_merchant(ctx: RequestContext, merchant_id: int | None) -> int | None:
    """场地级账号（超管/运营）可空（全场地）或指定；商户管理员强制本商户。"""
    if ctx.is_site_wide:
        return merchant_id
    if ctx.merchant_id is None:
        raise AppError("merchant_required", "当前账号未绑定商户", status_code=403)
    if merchant_id is not None and merchant_id != ctx.merchant_id:
        raise AppError("forbidden", "禁止跨商户查看报表", status_code=403)
    return ctx.merchant_id


def _validate_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise AppError("invalid_range", "结束日期不得早于开始日期", status_code=400)


@router.get("/commerce-summary", response_model=CommerceSummaryOut)
def commerce_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("report:read")
    _validate_range(date_from, date_to)
    mid = _resolve_report_merchant(ctx, merchant_id)
    summary = summarize_commerce(
        db,
        site_id=ctx.site_id,
        date_from=date_from,
        date_to=date_to,
        merchant_id=mid,
    )
    return CommerceSummaryOut(
        date_from=date_from,
        date_to=date_to,
        merchant_id=mid,
        charge_total=summary.charge_total,
        refund_total=summary.refund_total,
        net_total=summary.net_total,
        by_channel=[ChannelRow(**row) for row in summary.by_channel],
        by_order_type=[OrderTypeRow(**row) for row in summary.by_order_type],
    )


@router.get("/commerce-payments.csv")
def commerce_payments_csv(
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("report:read")
    _validate_range(date_from, date_to)
    mid = _resolve_report_merchant(ctx, merchant_id)
    rows = list_commerce_payments(
        db,
        site_id=ctx.site_id,
        date_from=date_from,
        date_to=date_to,
        merchant_id=mid,
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "payment_id",
            "order_id",
            "merchant_id",
            "order_type",
            "kind",
            "channel",
            "amount",
            "created_at",
            "order_title",
        ]
    )
    for payment, order in rows:
        writer.writerow(
            [
                payment.id,
                order.id,
                order.merchant_id,
                order.order_type,
                payment.kind,
                payment.channel,
                str(payment.amount),
                payment.created_at.isoformat() if payment.created_at else "",
                order.title,
            ]
        )
    buf.seek(0)
    filename = f"commerce-payments-{date_from}-{date_to}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class MembershipSummaryOut(BaseModel):
    date_from: date
    date_to: date
    merchant_id: int | None
    new_count: int
    renew_count: int
    active_count: int
    frozen_count: int
    expired_in_range: int


class CourseSummaryOut(BaseModel):
    date_from: date
    date_to: date
    merchant_id: int | None
    session_count: int
    booking_count: int
    full_session_count: int
    attended_count: int
    pt_consume_count: int
    pt_appointment_count: int = 0
    pt_completed_count: int = 0


class RevenueSplitRowOut(BaseModel):
    category: str
    label: str
    charge_total: Decimal
    refund_total: Decimal
    net_total: Decimal


class RevenueSplitOut(BaseModel):
    date_from: date
    date_to: date
    merchant_id: int | None
    rows: list[RevenueSplitRowOut]
    net_total: Decimal


class ActivitySummaryOut(BaseModel):
    date_from: date
    date_to: date
    merchant_id: int | None
    activity_count: int
    registered_count: int
    attended_count: int
    cancelled_count: int


class InventorySkuOut(BaseModel):
    sku_id: int
    name: str
    stock_qty: int
    low_stock_threshold: int
    is_low: bool


class InventorySummaryOut(BaseModel):
    date_from: date
    date_to: date
    merchant_id: int | None
    sale_qty: int
    skus: list[InventorySkuOut]


@router.get("/membership-summary", response_model=MembershipSummaryOut)
def membership_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("report:read")
    _validate_range(date_from, date_to)
    mid = _resolve_report_merchant(ctx, merchant_id)
    s = summarize_membership(
        db, site_id=ctx.site_id, date_from=date_from, date_to=date_to, merchant_id=mid
    )
    return MembershipSummaryOut(
        date_from=date_from,
        date_to=date_to,
        merchant_id=mid,
        new_count=s.new_count,
        renew_count=s.renew_count,
        active_count=s.active_count,
        frozen_count=s.frozen_count,
        expired_in_range=s.expired_in_range,
    )


@router.get("/course-summary", response_model=CourseSummaryOut)
def course_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("report:read")
    _validate_range(date_from, date_to)
    mid = _resolve_report_merchant(ctx, merchant_id)
    s = summarize_course(
        db, site_id=ctx.site_id, date_from=date_from, date_to=date_to, merchant_id=mid
    )
    return CourseSummaryOut(
        date_from=date_from,
        date_to=date_to,
        merchant_id=mid,
        session_count=s.session_count,
        booking_count=s.booking_count,
        full_session_count=s.full_session_count,
        attended_count=s.attended_count,
        pt_consume_count=s.pt_consume_count,
        pt_appointment_count=s.pt_appointment_count,
        pt_completed_count=s.pt_completed_count,
    )


@router.get("/revenue-split", response_model=RevenueSplitOut)
def revenue_split(
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """收入构成：会员 / 私教 / 团课 / 活动 / 零售 / 饮品。"""
    ctx.require_permission("report:read")
    _validate_range(date_from, date_to)
    mid = _resolve_report_merchant(ctx, merchant_id)
    rows = summarize_revenue_split(
        db, site_id=ctx.site_id, date_from=date_from, date_to=date_to, merchant_id=mid
    )
    return RevenueSplitOut(
        date_from=date_from,
        date_to=date_to,
        merchant_id=mid,
        rows=[RevenueSplitRowOut(**row.__dict__) for row in rows],
        net_total=sum((row.net_total for row in rows), Decimal("0.00")),
    )


@router.get("/activity-summary", response_model=ActivitySummaryOut)
def activity_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("report:read")
    _validate_range(date_from, date_to)
    mid = _resolve_report_merchant(ctx, merchant_id)
    s = summarize_activity(
        db, site_id=ctx.site_id, date_from=date_from, date_to=date_to, merchant_id=mid
    )
    return ActivitySummaryOut(
        date_from=date_from,
        date_to=date_to,
        merchant_id=mid,
        activity_count=s.activity_count,
        registered_count=s.registered_count,
        attended_count=s.attended_count,
        cancelled_count=s.cancelled_count,
    )


@router.get("/inventory-summary", response_model=InventorySummaryOut)
def inventory_summary(
    date_from: date = Query(...),
    date_to: date = Query(...),
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("report:read")
    _validate_range(date_from, date_to)
    mid = _resolve_report_merchant(ctx, merchant_id)
    s = summarize_inventory(
        db, site_id=ctx.site_id, date_from=date_from, date_to=date_to, merchant_id=mid
    )
    return InventorySummaryOut(
        date_from=date_from,
        date_to=date_to,
        merchant_id=mid,
        sale_qty=s.sale_qty,
        skus=[InventorySkuOut(**row.__dict__) for row in s.skus],
    )
