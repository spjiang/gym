"""设备侧接口：心跳与通行校验（与员工登录凭证分离）。"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_device
from app.systems.platform.models.access import AccessDevice, AccessEvent, AccessGrant
from app.core.schemas.common import VerifyIn, VerifyOut

router = APIRouter(prefix="/device", tags=["device"])


@router.post("/heartbeat")
def heartbeat(device: AccessDevice = Depends(get_device), db: Session = Depends(get_db)):
    device.last_seen_at = datetime.now(timezone.utc)
    device.is_online = True
    db.commit()
    return {"ok": True, "device_id": device.id, "last_seen_at": device.last_seen_at}


@router.post("/access/verify", response_model=VerifyOut)
def verify_access(
    body: VerifyIn,
    device: AccessDevice = Depends(get_device),
    db: Session = Depends(get_db),
):
    """低延迟通行校验：仅读授权表并写事件，不依赖批处理同步完成。"""
    now = datetime.now(timezone.utc)
    grant = db.scalar(
        select(AccessGrant).where(
            AccessGrant.member_id == body.member_id,
            AccessGrant.access_point_id == device.access_point_id,
            AccessGrant.revoked.is_(False),
            AccessGrant.valid_from <= now,
            AccessGrant.valid_until >= now,
        )
    )
    allowed = grant is not None
    reason = None if allowed else "no_valid_grant"
    event = AccessEvent(
        device_id=device.id,
        access_point_id=device.access_point_id,
        member_id=body.member_id,
        allowed=allowed,
        reason=reason,
        detail=None,
    )
    db.add(event)
    device.last_seen_at = now
    device.is_online = True
    db.commit()
    db.refresh(event)
    return VerifyOut(allowed=allowed, reason=reason, event_id=event.id)
