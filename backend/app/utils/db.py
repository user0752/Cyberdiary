"""Database query helpers for cross-dialect tag matching on JSON array columns.

Supports both SQLite (json_each) and PostgreSQL (jsonb containment) so the
same code path works in dev (SQLite) and production (PostgreSQL).
"""

from sqlalchemy import exists, func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import ColumnElement
from sqlalchemy.orm import Mapped

from app.core.config import settings


def _is_postgres() -> bool:
    """True when the configured database is PostgreSQL."""
    return settings.database_url.startswith(("postgresql", "postgres+"))


def tag_contains(column: Mapped[str], tag: str) -> ColumnElement:
    """Build a condition that checks if a JSON array Text column contains ``tag``.

    Uses SQLite's ``json_each`` table-valued function or PostgreSQL's
    ``jsonb @>`` containment operator depending on the configured dialect.
    Matching is exact (no substring false-positives like ``LIKE '%"tag"%'``)
    and avoids full-table string scans.
    """
    if _is_postgres():
        # Cast the text column to jsonb and check containment of a single-element array.
        # jsonb @> '["tag"]'::jsonb is true when the array contains "tag".
        return column.cast(postgresql.JSONB).contains([tag])

    # SQLite path — use json_each to expand the array and match exactly.
    json_each = func.json_each(column).table_valued("value")
    return exists(select(1).select_from(json_each).where(json_each.c.value == tag))
