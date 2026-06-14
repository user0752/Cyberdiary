"""Pydantic schemas for Compile."""

from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field


class CompileTriggerRequest(BaseModel):
    memo_ids: list[str] | None = None   # None = all uncompiled memos
    model_id: str = Field(..., min_length=1)


class MultiAgentCompileRequest(BaseModel):
    memo_ids: list[str] = Field(..., min_length=1, max_length=50)
    config: Optional[dict] = None


class HumanReviewRequest(BaseModel):
    decision: Literal["approve", "revise", "reject"]
    edited_wiki: Optional[str] = None


class CompileJobResponse(BaseModel):
    id: str
    status: str
    memo_ids: str
    model_id: str
    result_summary: str | None
    error_msg: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
