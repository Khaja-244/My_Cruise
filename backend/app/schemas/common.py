from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Standard paginated API response."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class ErrorDetails(BaseModel):
    """Structured application error returned by the API."""

    code: str
    message: str
    details: dict | None = None
    request_id: str | None = None


class Message(BaseModel):
    """Simple message response used by action endpoints."""

    message: str
