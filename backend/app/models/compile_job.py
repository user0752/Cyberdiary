"""CompileJob model - tracks LLM compilation tasks."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CompileJob(Base):
    __tablename__ = "compile_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|running|done|failed
    compile_type: Mapped[str] = mapped_column(String(20), default="single")  # single|multi_agent
    memo_ids: Mapped[str] = mapped_column(Text, nullable=False)          # JSON array
    model_id: Mapped[str] = mapped_column(String(100), nullable=False)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    current_agent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_layer: Mapped[str | None] = mapped_column(String(20), nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    compilation_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    integrated_knowledge: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
