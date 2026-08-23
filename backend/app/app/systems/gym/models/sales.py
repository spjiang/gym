"""销售档案：后台员工挂靠会员，销售提成统一记会员受益人。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SalesRep(Base):
    """销售档案；与教练档案类似，主身份为绑定会员。"""

    __tablename__ = "sales_reps"
    __table_args__ = (
        UniqueConstraint("staff_user_id", name="uq_sales_reps_staff_user"),
        UniqueConstraint("member_id", name="uq_sales_reps_member"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    staff_user_id: Mapped[int] = mapped_column(ForeignKey("staff_users.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    # 可选：指定销售提成规则；未指定时按商户默认规则（同场景优先级）
    commission_rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("commission_rules.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
