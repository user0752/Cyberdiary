"""Database query helpers for cross-dialect tag matching on JSON array columns."""

from sqlalchemy import exists, func, select
from sqlalchemy.sql import ColumnElement
from sqlalchemy.orm import Mapped


def tag_contains(column: Mapped[str], tag: str) -> ColumnElement:
    """Build a condition that checks if a JSON array Text column contains ``tag``.

    Uses SQLite's ``json_each`` table-valued function so matching is exact
    (no substring false-positives like ``LIKE '%"tag"%'``) and avoids
    full-table string scans.
    """
    json_each = func.json_each(column).table_valued("value")
    return exists(select(1).select_from(json_each).where(json_each.c.value == tag))
