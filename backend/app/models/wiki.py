"""Wiki models - WikiPage and WikiLink."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WikiPage(Base):
    __tablename__ = "wiki_pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    wiki_type: Mapped[str] = mapped_column(String(50), nullable=False)  # concept|entity|comparison|synthesis|source
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[str] = mapped_column(Text, default="[]")
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_memo_ids: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )


class WikiLink(Base):
    __tablename__ = "wiki_links"
    __table_args__ = (UniqueConstraint("from_slug", "to_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    to_slug: Mapped[str] = mapped_column(String(255), nullable=False)
