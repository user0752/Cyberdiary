"""Pydantic schemas for Wiki."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WikiPageResponse(BaseModel):
    id: str
    slug: str
    title: str
    wiki_type: str
    content: str
    summary: str | None
    tags: str
    file_path: str | None
    source_memo_ids: str
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WikiPageListResponse(BaseModel):
    items: list[WikiPageResponse]
    total: int
    page: int
    page_size: int


class WikiUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    wiki_type: str | None = None


class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # wiki_type
    slug: str


class GraphEdge(BaseModel):
    source: str
    target: str


class WikiGraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
