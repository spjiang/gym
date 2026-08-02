"""审计写入。"""

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def write_audit(
    db: Session,
    *,
    action: str,
    target_type: str,
    target_id: str | int,
    summary: str,
    actor_staff_id: int | None = None,
    site_id: int | None = None,
    merchant_id: int | None = None,
) -> AuditLog:
    log = AuditLog(
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        summary=summary,
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=merchant_id,
    )
    db.add(log)
    db.flush()
    return log
