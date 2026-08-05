"""临访通行记录。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class VisitPass(Base):
    __tablename__ = "visit_passes"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    access_point_id: Mapped[int] = mapped_column(ForeignKey("access_points.id"), nullable=False)
    grant_id: Mapped[int] = mapped_column(ForeignKey("access_grants.id"), nullable=False, index=True)
    hours: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_by_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
