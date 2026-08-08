from collections.abc import Sequence
from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    page_num: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=250)


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    page_num: int
    per_page: int
    total_items: int
    total_pages: int


def paginate(items: Sequence[T], params: PaginationParams) -> PaginatedResponse[T]:
    total = len(items)
    start = (params.page_num - 1) * params.per_page
    return PaginatedResponse(
        items=list(items[start : start + params.per_page]),
        page_num=params.page_num,
        per_page=params.per_page,
        total_items=total,
        total_pages=ceil(total / params.per_page) if total else 0,
    )
