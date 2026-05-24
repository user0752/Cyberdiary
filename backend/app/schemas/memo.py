"""Pydantic schemas for Memo."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class MemoCreate(BaseModel):
    content: str = Field(..., min_length=1, description="Markdown content")
    tags: list[str] = Field(default_factory=list)
    memo_type: str = Field(default="note", pattern=r"^(note|idea|reference|log)$")
    source_url: str | None = None
    pinned: bool = False


class MemoUpdate(BaseModel):
    content: str | None = None
    tags: list[str] | None = None
    memo_type: str | None = Field(default=None, pattern=r"^(note|idea|reference|log)$")
    source_url: str | None = None
    compiled: bool | None = None
    archived: bool | None = None
    pinned: bool | None = None


class MemoResponse(BaseModel):
    id: str
    content: str
    tags: str  # JSON string
    memo_type: str
    source_url: str | None
    compiled: bool
    archived: bool
    pinned: bool
    created_at: datetime
    updated_at: datetime

    @property
    def tag_list(self) -> list[str]:
        import json
        return json.loads(self.tags) if self.tags else []

    model_config = {"from_attributes": True}


class MemoListResponse(BaseModel):
    items: list[MemoResponse]
    total: int
    page: int
    page_size: int


class ApiResponse(BaseModel, Generic[T]):
    """Unified API response wrapper."""
    code: int = 0
    message: str = "ok"
    data: T | None = None
