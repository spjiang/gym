"""会员 OTP 挑战记录。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class MemberOtpChallenge(Base):
    __tablename__ = "member_otp_challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
