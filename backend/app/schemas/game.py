"""Pydantic schemas for Game."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.memo import ApiResponse  # reuse unified wrapper


class GenerateRequest(BaseModel):
    wiki_page_id: str | None = None
    count: int = Field(default=5, ge=1, le=20)
    difficulty: str = Field(default="medium", pattern=r"^(easy|medium|hard)$")
    model_id: str = Field(..., min_length=1)


class QuestionResponse(BaseModel):
    id: str
    wiki_page_id: str | None
    question_type: str
    difficulty: str
    question_text: str
    options: str  # JSON string
    source_title: str | None

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id: str
    wiki_page_id: str | None
    model_id: str
    status: str
    total_questions: int
    correct_count: int
    created_at: datetime
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class SessionCreateResponse(BaseModel):
    session: SessionResponse
    questions: list[QuestionResponse]


class AnswerSubmit(BaseModel):
    question_id: str
    user_answer: str = Field(..., pattern=r"^[ABCD]$")


class AnswerResult(BaseModel):
    question_id: str
    user_answer: str
    is_correct: bool
    correct_answer: str
    explanation: str | None


class SessionSummary(BaseModel):
    session: SessionResponse
    answers: list[AnswerResult]
