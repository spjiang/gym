"""提现单：教练/员工佣金提现与会员返点提现共用一张单据。

打款为线下动作，线上只记录状态流转：申请 → 审核通过 → 已打款，或被驳回。
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PayoutSource(str, Enum):
    """提现资金来源。"""

    COMMISSION = "commission"  # 教练/员工提成
    REBATE = "rebate"  # 会员推广返点


class PayoutStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


class PayoutMethod(str, Enum):
    OFFLINE_CASH = "offline_cash"
    OFFLINE_TRANSFER = "offline_transfer"
    OTHER = "other"


class Payout(Base):
    __tablename__ = "payouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    beneficiary_type: Mapped[str] = mapped_column(String(16), nullable=False)
    beneficiary_id: Mapped[int] = mapped_column(nullable=False, index=True)
    beneficiary_name: Mapped[str] = mapped_column(String(128), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PayoutStatus.REQUESTED.value, index=True
    )
    method: Mapped[str | None] = mapped_column(String(32))
    # 线下打款凭证号 / 转账流水号
    external_ref: Mapped[str | None] = mapped_column(String(64))
    # 本次提现单抵扣的提成欠额（现金 = amount）
    offset_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    note: Mapped[str | None] = mapped_column(String(255))
    reject_reason: Mapped[str | None] = mapped_column(String(255))
    requested_by_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    requested_by_member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    reviewed_by_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_by_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PayoutItem(Base):
    """佣金提现明细：锁定本次结算覆盖的提成记录。"""

    __tablename__ = "payout_items"
    __table_args__ = (
        UniqueConstraint("commission_record_id", name="uq_payout_item_commission_record"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payout_id: Mapped[int] = mapped_column(ForeignKey("payouts.id"), nullable=False, index=True)
    commission_record_id: Mapped[int] = mapped_column(
        ForeignKey("commission_records.id"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
