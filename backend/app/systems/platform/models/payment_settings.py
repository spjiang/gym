"""场地支付配置、微信 openid 绑定、支付意图。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class SitePaymentSettings(Base):
    __tablename__ = "site_payment_settings"

    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), primary_key=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="unconfigured")
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mp_app_id: Mapped[str | None] = mapped_column(String(64))
    mp_app_secret_enc: Mapped[str | None] = mapped_column(Text)
    oa_app_id: Mapped[str | None] = mapped_column(String(64))
    oa_app_secret_enc: Mapped[str | None] = mapped_column(Text)
    mch_id: Mapped[str | None] = mapped_column(String(64))
    api_v3_key_enc: Mapped[str | None] = mapped_column(Text)
    mch_serial_no: Mapped[str | None] = mapped_column(String(128))
    mch_private_key_enc: Mapped[str | None] = mapped_column(Text)
    platform_serial_no: Mapped[str | None] = mapped_column(String(128))
    platform_public_key_enc: Mapped[str | None] = mapped_column(Text)
    notify_url: Mapped[str | None] = mapped_column(String(512))
    h5_return_url: Mapped[str | None] = mapped_column(String(512))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))


class MemberWechatBinding(Base):
    __tablename__ = "member_wechat_bindings"
    __table_args__ = (
        UniqueConstraint("mp_openid", name="uq_member_wechat_mp_openid"),
        UniqueConstraint("oa_openid", name="uq_member_wechat_oa_openid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), nullable=False, unique=True, index=True)
    mp_openid: Mapped[str | None] = mapped_column(String(128))
    oa_openid: Mapped[str | None] = mapped_column(String(128))
    union_id: Mapped[str | None] = mapped_column(String(128))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PaymentIntent(Base):
    __tablename__ = "payment_intents"
    __table_args__ = (UniqueConstraint("out_trade_no", name="uq_payment_intents_out_trade_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    out_trade_no: Mapped[str] = mapped_column(String(64), nullable=False)
    scene: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    provider_prepay_id: Mapped[str | None] = mapped_column(String(128))
    provider_ref: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefundIntent(Base):
    __tablename__ = "refund_intents"
    __table_args__ = (UniqueConstraint("out_refund_no", name="uq_refund_intents_out_refund_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    out_refund_no: Mapped[str] = mapped_column(String(64), nullable=False)
    out_trade_no: Mapped[str | None] = mapped_column(String(64))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    suggested_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created", index=True)
    force: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    provider_ref: Mapped[str | None] = mapped_column(String(128))
    error_message: Mapped[str | None] = mapped_column(String(512))
    actor_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    succeeded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
