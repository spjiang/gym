"""统一分页请求/响应契约。"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


class PageIn(BaseModel):
    page: int = Field(1, ge=1, description="页码，从 1 起")
    page_size: int = Field(20, ge=1, le=100, description="每页条数")


class PageOut(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


def paginate(db: Session, stmt: Select, *, page: int, page_size: int) -> tuple[list, int]:
    """对已带筛选条件的查询做计数与切片。"""
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())
    return rows, int(total)
