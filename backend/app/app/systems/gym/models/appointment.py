"""私教一对一预约排期。"""

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PtAppointmentStatus(str, Enum):
    BOOKED = "booked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


# 占用教练与会员时段的状态，取消后释放
BLOCKING_APPOINTMENT_STATUS = {
    PtAppointmentStatus.BOOKED.value,
    PtAppointmentStatus.COMPLETED.value,
    PtAppointmentStatus.NO_SHOW.value,
}


class PtAppointment(Base):
    __tablename__ = "pt_appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("coaches.id"), nullable=False, index=True)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("pt_packages.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=PtAppointmentStatus.BOOKED.value)
    location: Mapped[str | None] = mapped_column(String(128))
    note: Mapped[str | None] = mapped_column(String(255))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_reason: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
