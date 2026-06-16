"""Multi-agent compilation models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class HumanReviewTask(Base):
    __tablename__ = "human_review_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("compile_jobs.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviews: Mapped[str | None] = mapped_column(Text, nullable=True)
    arbitration: Mapped[str | None] = mapped_column(Text, nullable=True)
    wiki_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_edited_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    revised_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class CompilationCache(Base):
    __tablename__ = "compilation_cache"

    memo_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    wiki_content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ABTestRecord(Base):
    __tablename__ = "ab_test_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    variant: Mapped[str | None] = mapped_column(String(20), nullable=True)
    wiki_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluation_scores: Mapped[str | None] = mapped_column(Text, nullable=True)
    compilation_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)


class SemanticLink(Base):
    __tablename__ = "semantic_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    relation_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
