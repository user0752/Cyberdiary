"""Game models for tower-defense quiz system."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GameQuestion(Base):
    __tablename__ = "game_questions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    wiki_page_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("wiki_pages.id"), nullable=True
    )
    question_type: Mapped[str] = mapped_column(String(20), default="choice")
    difficulty: Mapped[str] = mapped_column(String(10), default="medium")
    question_text: Mapped[str] = mapped_column(Text)
    options: Mapped[str] = mapped_column(Text)  # JSON array string
    correct_answer: Mapped[str] = mapped_column(String(10))
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class GameSession(Base):
    __tablename__ = "game_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    wiki_page_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("wiki_pages.id"), nullable=True
    )
    model_id: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="active")
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    question_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GameAnswer(Base):
    __tablename__ = "game_answers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("game_sessions.id", ondelete="CASCADE")
    )
    question_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("game_questions.id")
    )
    user_answer: Mapped[str] = mapped_column(String(10))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
