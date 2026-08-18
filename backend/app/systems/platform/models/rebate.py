"""会员推广返点：场地默认配置、返点账户与账户流水。

返点只用于线下提现，不能抵扣消费；账户余额 = 可提现余额，
提现中的金额转入 frozen_amount，退款冲回不足时记入 debt_amount 待后续返点抵扣。
"""

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


class RebateLedgerKind(str, Enum):
    """账户流水类型。"""

    EARN = "earn"  # 下级消费入账
    REVERSE = "reverse"  # 下级退款冲回
    WITHDRAW_FREEZE = "withdraw_freeze"  # 提现申请冻结
    WITHDRAW_PAID = "withdraw_paid"  # 提现线下打款完成
    WITHDRAW_REVERT = "withdraw_revert"  # 提现被驳回或撤销，解冻回余额
    ADJUST = "adjust"  # 人工调整


class SitePromotionSettings(Base):
    """场地级推广默认值：会员推广位未单独配置时回落到此。"""

    __tablename__ = "site_promotion_settings"
    __table_args__ = (UniqueConstraint("site_id", name="uq_site_promotion_settings_site"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    # 会员建档 / 自助注册时自动生成个人推广码
    auto_create_member_code: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_rebate_rate: Mapped[Decimal] = mapped_column(
        Numeric(7, 4), nullable=False, default=Decimal("0")
    )
    default_downline_discount_rate: Mapped[Decimal] = mapped_column(
        Numeric(7, 4), nullable=False, default=Decimal("0")
    )
    # 单笔提现下限，低于此金额不允许申请
    min_withdraw_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("1.00")
    )
    # 返点入账后需满该天数才计入可提现；0 表示即时可提。用于降低先提现再退款产生欠额
    withdraw_hold_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MemberRebateAccount(Base):
    """会员返点账户，一人一户。"""

    __tablename__ = "member_rebate_accounts"
    __table_args__ = (UniqueConstraint("member_id", name="uq_member_rebate_account_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    frozen_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    # 退款冲回时余额不足的欠额，后续返点优先抵扣
    debt_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    total_earned: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    total_withdrawn: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MemberRebateLedger(Base):
    """返点账户流水；对同一来源同一类型幂等。"""

    __tablename__ = "member_rebate_ledgers"
    __table_args__ = (
        UniqueConstraint(
            "kind", "source_type", "source_id", name="uq_member_rebate_ledger_source"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("member_rebate_accounts.id"), nullable=False, index=True
    )
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # 正数入账、负数出账
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(32))
    source_id: Mapped[int | None] = mapped_column(Integer)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)
    # 产生该笔返点的下级会员
    from_member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), index=True)
    base_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    note: Mapped[str | None] = mapped_column(String(255))
    actor_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
