"""Standardized pagination for list endpoints."""
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, le=10000)
    per_page: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def build(cls, items: list[T], total: int, params: PaginationParams) -> "PaginatedResponse[T]":
        total_pages = max(1, -(-total // params.per_page))  # ceiling division
        return cls(
            items=items,
            total=total,
            page=params.page,
            per_page=params.per_page,
            total_pages=total_pages,
            has_next=params.page < total_pages,
            has_prev=params.page > 1,
        )
