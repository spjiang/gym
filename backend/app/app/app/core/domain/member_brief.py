"""会员摘要批量加载（列表嵌套用）。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.schemas.common import MemberBrief
from app.systems.platform.models.member import Member


def load_member_briefs(db: Session, ids: set[int] | list[int]) -> dict[int, MemberBrief]:
    clean = {int(i) for i in ids if i is not None}
    if not clean:
        return {}
    rows = db.scalars(select(Member).where(Member.id.in_(clean))).all()
    return {m.id: MemberBrief(id=m.id, name=m.name, phone=m.phone) for m in rows}
