"""通知查询 API（员工）。"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import MemberContext, RequestContext, get_current_context, get_current_member
from app.core.domain.member_brief import load_member_briefs
from app.core.schemas.common import MemberBrief
from app.core.schemas.paging import PageOut
from app.systems.platform.models.notification import Notification

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
    member: MemberBrief | None = None


@router.get("/notifications", response_model=PageOut[NotificationOut])
def list_staff_notifications(
    merchant_id: int | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("order:read", "member:read", "access:read")
    filters = [Notification.site_id == ctx.site_id]
    if ctx.is_site_admin:
        if merchant_id is not None:
            filters.append(Notification.merchant_id == merchant_id)
    else:
        mid = ctx.resolve_merchant_id(merchant_id)
        filters.append(Notification.merchant_id == mid)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        filters.append(or_(Notification.title.ilike(like), Notification.body.ilike(like), Notification.event_type.ilike(like)))
    total = db.scalar(select(func.count()).select_from(Notification).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(Notification)
            .where(*filters)
            .order_by(Notification.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    briefs = load_member_briefs(db, {r.member_id for r in rows if r.member_id is not None})
    items = [
        NotificationOut(
            id=r.id,
            merchant_id=r.merchant_id,
            member_id=r.member_id,
            audience=r.audience,
            event_type=r.event_type,
            title=r.title,
            body=r.body,
            created_at=r.created_at,
            member=briefs.get(r.member_id) if r.member_id else None,
        )
        for r in rows
    ]
    return PageOut(items=items, total=total, page=page, page_size=page_size)


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
