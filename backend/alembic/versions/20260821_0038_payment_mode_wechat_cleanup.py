"""20260821_0038 支付模式清理：历史 jdpay 统一为 wechat。"""

from __future__ import annotations

from alembic import op

revision = "20260821_0038"
down_revision = "20260820_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 历史误标的「京东支付」实为微信 APIv3，落库统一为 wechat
    op.execute(
        """
        UPDATE site_payment_settings
        SET mode = 'wechat'
        WHERE lower(mode) = 'jdpay'
        """
    )


def downgrade() -> None:
    # 不可逆：不再写回 jdpay
    pass
