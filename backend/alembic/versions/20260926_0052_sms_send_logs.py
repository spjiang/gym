"""平台短信发送记录

Revision ID: 20260926_0052
Revises: 20260924_0051
Create Date: 2026-09-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260926_0052"
down_revision: Union[str, None] = "20260924_0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sms_send_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("scene", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("template_code", sa.String(64), nullable=True),
        sa.Column("sign_name", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("provider_code", sa.String(64), nullable=True),
        sa.Column("provider_message", sa.String(512), nullable=True),
        sa.Column("request_json", JSONB(), nullable=True),
        sa.Column("response_json", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sms_send_logs_site_id", "sms_send_logs", ["site_id"])
    op.create_index("ix_sms_send_logs_phone", "sms_send_logs", ["phone"])
    op.create_index("ix_sms_send_logs_created_at", "sms_send_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_sms_send_logs_created_at", table_name="sms_send_logs")
    op.drop_index("ix_sms_send_logs_phone", table_name="sms_send_logs")
    op.drop_index("ix_sms_send_logs_site_id", table_name="sms_send_logs")
    op.drop_table("sms_send_logs")
