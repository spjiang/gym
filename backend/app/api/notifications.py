"""通知查询 API（员工）。"""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import MemberContext, RequestContext, get_current_context, get_current_member
from app.models.notification import Notification

router = APIRouter(tags=["notifications"])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    merchant_id: int | None
    member_id: int | None
    audience: str
    event_type: str
    title: str
    body: str
    created_at: datetime


@router.get("/notifications", response_model=list[NotificationOut])
def list_staff_notifications(
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("order:read", "member:read", "access:read")
    q = select(Notification).where(Notification.site_id == ctx.site_id)
    if ctx.is_site_admin:
        if merchant_id is not None:
            q = q.where(Notification.merchant_id == merchant_id)
    else:
        mid = ctx.resolve_merchant_id(merchant_id)
        q = q.where(Notification.merchant_id == mid)
    return list(db.scalars(q.order_by(Notification.id.desc()).limit(100)).all())


member_router = APIRouter(prefix="/member", tags=["member-notifications"])


@member_router.get("/notifications", response_model=list[NotificationOut])
def list_member_notifications(
    db: Session = Depends(get_db),
    mctx: MemberContext = Depends(get_current_member),
):
    return list(
        db.scalars(
            select(Notification)
            .where(Notification.member_id == mctx.member.id)
            .order_by(Notification.id.desc())
            .limit(100)
        ).all()
    )
