"""登录与当前用户。"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.systems.platform.models.identity import StaffRole, StaffUser
from app.core.schemas.common import LoginIn, MeOut, TokenOut
from app.core.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    staff = db.scalar(select(StaffUser).where(StaffUser.username == body.username))
    if staff is None or not staff.is_active or not verify_password(body.password, staff.password_hash):
        raise AppError("invalid_credentials", "用户名或密码错误", status_code=401)
    token = create_access_token(
        subject=str(staff.id),
        extra={"site_id": staff.site_id, "typ": "staff"},
    )
    return TokenOut(access_token=token)


@router.get("/me", response_model=MeOut)
def me(ctx: RequestContext = Depends(get_current_context)):
    return MeOut(
        id=ctx.staff.id,
        username=ctx.staff.username,
        display_name=ctx.staff.display_name,
        site_id=ctx.site_id,
        merchant_id=ctx.merchant_id,
        role_codes=sorted(ctx.role_codes),
        permissions=sorted(ctx.permissions),
    )
