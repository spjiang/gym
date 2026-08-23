"""活动报名履约：收款后确认名额。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.systems.gym.models.activity import ActivityRegistration, RegistrationStatus
from app.systems.platform.models.commerce import Order
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.notifications import write_notification


def fulfill_activity_order(
    db: Session, order: Order, *, actor_staff_id: int | None = None
) -> ActivityRegistration | None:
    """收款成功后把报名置为已确认；非活动订单返回 None。"""
    if order.order_type != "activity":
        return None

    registration = db.scalar(
        select(ActivityRegistration).where(ActivityRegistration.order_id == order.id)
    )
    if registration is None:
        return None
    if registration.status != RegistrationStatus.PENDING.value:
        return registration

    registration.status = RegistrationStatus.CONFIRMED.value
    write_audit(
        db,
        action="activity.registration_confirmed",
        target_type="activity_registration",
        target_id=registration.id,
        summary=f"订单 {order.id} 收款，报名确认",
        actor_staff_id=actor_staff_id,
        site_id=order.site_id,
        merchant_id=order.merchant_id,
    )
    write_notification(
        db,
        site_id=order.site_id,
        merchant_id=order.merchant_id,
        member_id=registration.member_id,
        event_type="activity.registered",
        title="活动报名成功",
        body=f"订单 #{order.id} {order.title} 报名已确认",
    )
    db.flush()
    return registration
