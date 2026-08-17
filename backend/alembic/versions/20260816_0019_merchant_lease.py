"""20260816_0019 商户租赁有效期。"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260816_0019"
down_revision = "20260816_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("merchants", sa.Column("lease_starts_on", sa.Date()))
    op.add_column("merchants", sa.Column("lease_ends_on", sa.Date()))


def downgrade() -> None:
    op.drop_column("merchants", "lease_ends_on")
    op.drop_column("merchants", "lease_starts_on")
