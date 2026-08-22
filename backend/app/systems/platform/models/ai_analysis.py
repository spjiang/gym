"""AI 分析：提示词模版、大模型账号与分析记录。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AiPromptTemplate(Base):
    """提示词模版：按场景绑定数据源与输出要求。"""

    __tablename__ = "ai_prompt_templates"
    __table_args__ = (UniqueConstraint("site_id", "code", name="uq_ai_prompt_template_site_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    data_source: Mapped[str] = mapped_column(String(64), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(512))
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiLlmAccount(Base):
    """大模型调用账号（API Key 加密存储）。"""

    __tablename__ = "ai_llm_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="openai_compatible")
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    api_key_enc: Mapped[str | None] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AiAnalysisRecord(Base):
    """AI 分析执行记录。"""

    __tablename__ = "ai_analysis_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id"), nullable=False, index=True)
    merchant_id: Mapped[int | None] = mapped_column(ForeignKey("merchants.id"), index=True)
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"), index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("ai_prompt_templates.id"), nullable=False, index=True)
    llm_account_id: Mapped[int] = mapped_column(ForeignKey("ai_llm_accounts.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    input_summary: Mapped[str | None] = mapped_column(String(512))
    result_text: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
