"""AI 分析表

Revision ID: 20260822_0045
Revises: 20260822_0044
Create Date: 2026-08-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260822_0045"
down_revision: Union[str, None] = "20260822_0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_prompt_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("data_source", sa.String(64), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("user_prompt_template", sa.Text(), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "code", name="uq_ai_prompt_template_site_code"),
    )
    op.create_index("ix_ai_prompt_templates_site_id", "ai_prompt_templates", ["site_id"])

    op.create_table(
        "ai_llm_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="openai_compatible"),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("api_key_enc", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("remark", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_llm_accounts_site_id", "ai_llm_accounts", ["site_id"])

    op.create_table(
        "ai_analysis_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_id", sa.Integer(), nullable=False),
        sa.Column("merchant_id", sa.Integer(), nullable=True),
        sa.Column("staff_id", sa.Integer(), nullable=True),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("llm_account_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="success"),
        sa.Column("input_summary", sa.String(512), nullable=True),
        sa.Column("result_text", sa.Text(), nullable=True),
        sa.Column("error_message", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["llm_account_id"], ["ai_llm_accounts.id"]),
        sa.ForeignKeyConstraint(["merchant_id"], ["merchants.id"]),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"]),
        sa.ForeignKeyConstraint(["staff_id"], ["staff_users.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["ai_prompt_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_analysis_records_site_id", "ai_analysis_records", ["site_id"])
    op.create_index("ix_ai_analysis_records_template_id", "ai_analysis_records", ["template_id"])
    op.create_index("ix_ai_analysis_records_llm_account_id", "ai_analysis_records", ["llm_account_id"])


def downgrade() -> None:
    op.drop_table("ai_analysis_records")
    op.drop_table("ai_llm_accounts")
    op.drop_table("ai_prompt_templates")
