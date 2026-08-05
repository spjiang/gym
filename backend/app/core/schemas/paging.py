"""统一分页请求/响应契约。"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageIn(BaseModel):
    page: int = Field(1, ge=1, description="页码，从 1 起")
    page_size: int = Field(20, ge=1, le=100, description="每页条数")


class PageOut(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
