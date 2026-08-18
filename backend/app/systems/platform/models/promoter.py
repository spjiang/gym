"""推广位：推广码 / 二维码与推广规则绑定。"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PromoterSubjectType(str, Enum):
    """推广主体：会员推荐、员工（含教练）推广、渠道位（短视频/线下物料）。"""

    MEMBER = "member"
    STAFF = "staff"
    CHANNEL = "channel"


class PromoterChannel(str, Enum):
    """推广触达渠道，用于统计不同投放位的转化。"""

    MEMBER_SHARE = "member_share"
    SHORT_VIDEO = "short_video"
    POSTER = "poster"
    OFFLINE = "offline"
    OTHER = "other"


class PromoterCode(Base):
    __tablename__ = "promoter_codes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_promoter_code"),
        # 会员推广位一人一码：同场地下同一会员只允许一条，员工/渠道位不受限
        Index(
            "uq_promoter_member_code",
            "site_id",
            "subject_member_id",
            unique=True,
            postgresql_where=text("subject_type = 'member'"),
            sqlite_where=text("subject_type = 'member'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), index=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), index=True)
    subject_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default=PromoterChannel.OTHER.value)
    landing_path: Mapped[str | None] = mapped_column(String(128))
    # 为该推广位单独指定提成规则；留空走商户默认推荐规则
    commission_rule_id: Mapped[int | None] = mapped_column(ForeignKey("commission_rules.id"), index=True)
    # 下级消费给本推广位主体的返点比例；留空回落场地默认
    rebate_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    # 下级会员消费可享的减免比例，0.05 表示 95 折；留空回落场地默认
    downline_discount_rate: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    visit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
