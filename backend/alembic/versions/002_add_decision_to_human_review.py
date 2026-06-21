# -*- coding: utf-8 -*-
"""Add decision column to human_review_tasks.

Revision ID: 002
Revises: 001
Create Date: 2026-06-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "human_review_tasks",
        sa.Column("decision", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("human_review_tasks", "decision")
