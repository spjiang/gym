"""20260805_0014 微信支付配置、openid 绑定、支付意图。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260805_0014"
down_revision = "20260805_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_payment_settings",
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), primary_key=True),
        sa.Column("mode", sa.String(32), nullable=False, server_default="unconfigured"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("mp_app_id", sa.String(64)),
        sa.Column("mp_app_secret_enc", sa.Text()),
        sa.Column("oa_app_id", sa.String(64)),
        sa.Column("oa_app_secret_enc", sa.Text()),
        sa.Column("mch_id", sa.String(64)),
        sa.Column("api_v3_key_enc", sa.Text()),
        sa.Column("mch_serial_no", sa.String(128)),
        sa.Column("mch_private_key_enc", sa.Text()),
        sa.Column("notify_url", sa.String(512)),
        sa.Column("h5_return_url", sa.String(512)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_by_staff_id", sa.Integer(), sa.ForeignKey("staff_users.id")),
    )
    op.create_table(
        "member_wechat_bindings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("mp_openid", sa.String(128)),
        sa.Column("oa_openid", sa.String(128)),
        sa.Column("union_id", sa.String(128)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.UniqueConstraint("member_id", name="uq_member_wechat_bindings_member"),
        sa.UniqueConstraint("mp_openid", name="uq_member_wechat_mp_openid"),
        sa.UniqueConstraint("oa_openid", name="uq_member_wechat_oa_openid"),
    )
    op.create_index("ix_member_wechat_bindings_member_id", "member_wechat_bindings", ["member_id"])
    op.create_table(
        "payment_intents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("out_trade_no", sa.String(64), nullable=False),
        sa.Column("scene", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("provider_prepay_id", sa.String(128)),
        sa.Column("provider_ref", sa.String(128)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("succeeded_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("out_trade_no", name="uq_payment_intents_out_trade_no"),
    )
    op.create_index("ix_payment_intents_site_id", "payment_intents", ["site_id"])
    op.create_index("ix_payment_intents_order_id", "payment_intents", ["order_id"])


def downgrade() -> None:
    op.drop_table("payment_intents")
    op.drop_table("member_wechat_bindings")
    op.drop_table("site_payment_settings")
