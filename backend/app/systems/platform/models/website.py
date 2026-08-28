"""官网 CMS：站点配置与文章。"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.systems.platform.models.identity import JSONType


class WebsiteSettings(Base):
    """每场地一行：站点 / 首页 / 品牌 JSON。"""

    __tablename__ = "website_settings"
    __table_args__ = (UniqueConstraint("site_id", name="uq_website_settings_site"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    site_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    home_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    brands_json: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    updated_by_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WebsiteArticle(Base):
    """新闻 / 招聘 / 招商文章。"""

    __tablename__ = "website_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str | None] = mapped_column(String(255))
    cover_image_url: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contact_hint: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_by_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
