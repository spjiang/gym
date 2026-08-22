"""20260822_0039 课时提成历史受益人与 coach_id 回填。"""

from __future__ import annotations

from alembic import op

revision = "20260822_0039"
down_revision = "20260821_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 历史课时记录：受益人是教练时补上 coach_id
    op.execute(
        """
        UPDATE commission_records
        SET coach_id = beneficiary_id
        WHERE scope IN ('group_session', 'pt_session')
          AND beneficiary_type = 'coach'
          AND coach_id IS NULL
        """
    )
    # 已绑定会员的教练：未结算课时提成迁到会员，避免双轨
    op.execute(
        """
        UPDATE commission_records AS cr
        SET beneficiary_type = 'member',
            beneficiary_id = c.member_id,
            coach_id = c.id,
            beneficiary_name = TRIM(BOTH FROM CONCAT(COALESCE(m.name, ''), ' ', COALESCE(m.phone, '')))
        FROM coaches AS c
        JOIN members AS m ON m.id = c.member_id
        WHERE cr.beneficiary_type = 'coach'
          AND cr.beneficiary_id = c.id
          AND c.member_id IS NOT NULL
          AND cr.status IN ('pending', 'confirmed')
        """
    )


def downgrade() -> None:
    pass
