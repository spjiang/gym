"""业务分成体系：提成规则与提成记录。"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CommissionScope(str, Enum):
    """计提场景。"""

    MEMBERSHIP_SALE = "membership_sale"
    PT_SALE = "pt_sale"
    RETAIL_SALE = "retail_sale"
    ACTIVITY_SALE = "activity_sale"
    GROUP_SESSION = "group_session"
    PT_SESSION = "pt_session"
    REFERRAL = "referral"


# 由订单金额驱动的销售类场景
ORDER_SCOPES = {
    CommissionScope.MEMBERSHIP_SALE.value: "membership",
    CommissionScope.PT_SALE.value: "pt_package",
    CommissionScope.RETAIL_SALE.value: "retail",
    CommissionScope.ACTIVITY_SALE.value: "activity",
}


class CommissionBeneficiary(str, Enum):
    """受益方角色。"""

    SELLER = "seller"
    COACH = "coach"
    REFERRER = "referrer"


class CommissionBasis(str, Enum):
    """计提方式。"""

    PERCENT = "percent"
    FIXED = "fixed"
    PER_HEAD = "per_head"
    PER_SESSION = "per_session"


class CommissionStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PAID = "paid"
    VOID = "void"


class BeneficiaryType(str, Enum):
    STAFF = "staff"
    COACH = "coach"
    MEMBER = "member"


class CommissionCategory(str, Enum):
    """提成业务类别：销售 / 课时 / 推荐。"""

    SALE = "sale"
    SESSION = "session"
    REFERRAL = "referral"


# 场景 → 提成类别
SCOPE_CATEGORY = {
    CommissionScope.MEMBERSHIP_SALE.value: CommissionCategory.SALE.value,
    CommissionScope.PT_SALE.value: CommissionCategory.SALE.value,
    CommissionScope.RETAIL_SALE.value: CommissionCategory.SALE.value,
    CommissionScope.ACTIVITY_SALE.value: CommissionCategory.SALE.value,
    CommissionScope.GROUP_SESSION.value: CommissionCategory.SESSION.value,
    CommissionScope.PT_SESSION.value: CommissionCategory.SESSION.value,
    CommissionScope.REFERRAL.value: CommissionCategory.REFERRAL.value,
}


class CommissionRule(Base):
    """商户可配置的提成规则；同场景可配多条，按 priority 取首条命中。"""

    __tablename__ = "commission_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    beneficiary: Mapped[str] = mapped_column(String(32), nullable=False)
    basis: Mapped[str] = mapped_column(String(32), nullable=False)
    # percent 用 rate（0-1），fixed / per_head / per_session 用 unit_amount
    rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    unit_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    min_base_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    # 推荐提成是否仅算首单
    first_order_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CommissionRecord(Base):
    """提成流水。同一来源 + 同一受益人只计提一次。"""

    __tablename__ = "commission_records"
    __table_args__ = (
        UniqueConstraint(
            "scope",
            "source_type",
            "source_id",
            "beneficiary_type",
            "beneficiary_id",
            name="uq_commission_record_source_beneficiary",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), nullable=False, index=True)
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("commission_rules.id"), index=True)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # sale / session / referral
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CommissionCategory.SALE.value, index=True
    )
    # order / group_session / pt_appointment / pt_package
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), index=True)
    # 课时提成追溯教练档案；受益人已改为教练绑定会员
    coach_id: Mapped[int | None] = mapped_column(ForeignKey("coaches.id"), nullable=True, index=True)
    # 受益人多态引用：staff_users / coaches / members
    beneficiary_type: Mapped[str] = mapped_column(String(16), nullable=False)
    beneficiary_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    beneficiary_name: Mapped[str] = mapped_column(String(128), nullable=False)
    base_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    quantity: Mapped[int | None] = mapped_column(Integer)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=CommissionStatus.PENDING.value)
    note: Mapped[str | None] = mapped_column(String(255))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
