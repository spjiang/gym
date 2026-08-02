"""站内通知写入。"""

from sqlalchemy.orm import Session

from app.models.notification import Notification


def write_notification(
    db: Session,
    *,
    site_id: int,
    event_type: str,
    title: str,
    body: str,
    merchant_id: int | None = None,
    member_id: int | None = None,
    audience: str = "member",
) -> Notification:
    row = Notification(
        site_id=site_id,
        merchant_id=merchant_id,
        member_id=member_id,
        audience=audience,
        event_type=event_type,
        title=title,
        body=body,
    )
    db.add(row)
    db.flush()
    return row
