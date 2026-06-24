# -*- coding: utf-8 -*-
"""Initial schema -- all ORM tables as of 2025.

Revision ID: 001
Revises: None
Create Date: 2025-06-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- memos ---
    op.create_table(
        "memos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.Text(), server_default="[]"),
        sa.Column("memo_type", sa.String(20), server_default="note"),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("compiled", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("pinned", sa.Boolean(), server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # --- conversations ---
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(255), server_default="新对话"),
        sa.Column("model_id", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # --- messages ---
    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conv_id", sa.String(36), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # --- wiki_pages ---
    op.create_table(
        "wiki_pages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("slug", sa.String(255), unique=True, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("wiki_type", sa.String(50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("tags", sa.Text(), server_default="[]"),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("source_memo_ids", sa.Text(), server_default="[]"),
        sa.Column("version", sa.Integer(), server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # --- wiki_links ---
    op.create_table(
        "wiki_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("from_slug", sa.String(255), nullable=False),
        sa.Column("to_slug", sa.String(255), nullable=False),
        sa.UniqueConstraint("from_slug", "to_slug"),
    )

    # --- compile_jobs ---
    op.create_table(
        "compile_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("compile_type", sa.String(20), server_default="single"),
        sa.Column("memo_ids", sa.Text(), nullable=False),
        sa.Column("model_id", sa.String(100), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("error_msg", sa.Text(), nullable=True),
        sa.Column("progress", sa.Float(), server_default=sa.text("0.0")),
        sa.Column("current_agent", sa.String(50), nullable=True),
        sa.Column("current_layer", sa.String(20), nullable=True),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("compilation_log", sa.Text(), nullable=True),
        sa.Column("integrated_knowledge", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # --- human_review_tasks ---
    op.create_table(
        "human_review_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("compile_jobs.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("final_score", sa.Float(), nullable=True),
        sa.Column("reviews", sa.Text(), nullable=True),
        sa.Column("arbitration", sa.Text(), nullable=True),
        sa.Column("wiki_content", sa.Text(), nullable=True),
        sa.Column("user_edited_content", sa.Text(), nullable=True),
        sa.Column("revised_content", sa.Text(), nullable=True),
        sa.Column("final_content", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
    )

    # --- compilation_cache ---
    op.create_table(
        "compilation_cache",
        sa.Column("memo_id", sa.String(36), primary_key=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("wiki_content", sa.Text(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # --- game_questions ---
    op.create_table(
        "game_questions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("wiki_page_id", sa.String(36), sa.ForeignKey("wiki_pages.id"), nullable=True),
        sa.Column("question_type", sa.String(20), server_default="choice"),
        sa.Column("difficulty", sa.String(10), server_default="medium"),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", sa.Text(), nullable=False),
        sa.Column("correct_answer", sa.String(10), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("source_title", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # --- game_sessions ---
    op.create_table(
        "game_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("wiki_page_id", sa.String(36), sa.ForeignKey("wiki_pages.id"), nullable=True),
        sa.Column("model_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("total_questions", sa.Integer(), server_default=sa.text("0")),
        sa.Column("correct_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("question_ids", sa.Text(), server_default="[]"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("map_id", sa.String(100), nullable=True),
        sa.Column("lives", sa.Integer(), server_default=sa.text("20")),
        sa.Column("gold", sa.Integer(), server_default=sa.text("100")),
        sa.Column("current_wave", sa.Integer(), server_default=sa.text("0")),
        sa.Column("total_waves", sa.Integer(), server_default=sa.text("10")),
        sa.Column("tower_placements", sa.Text(), server_default="{}"),
        sa.Column("game_state", sa.String(20), server_default="setup"),
        sa.Column("wave_configs", sa.Text(), server_default="[]"),
    )

    # --- game_answers ---
    op.create_table(
        "game_answers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.String(36), sa.ForeignKey("game_questions.id"), nullable=False),
        sa.Column("user_answer", sa.String(10), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
    )

    # --- ab_test_records ---
    op.create_table(
        "ab_test_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("test_name", sa.String(100), nullable=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("variant", sa.String(20), nullable=True),
        sa.Column("wiki_content", sa.Text(), nullable=True),
        sa.Column("evaluation_scores", sa.Text(), nullable=True),
        sa.Column("compilation_time", sa.Float(), nullable=True),
        sa.Column("user_rating", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # --- semantic_links ---
    op.create_table(
        "semantic_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_slug", sa.String(200), nullable=True),
        sa.Column("target_slug", sa.String(200), nullable=True),
        sa.Column("relation_type", sa.String(50), nullable=True),
        sa.Column("confidence", sa.Float(), server_default=sa.text("0.5")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # --- settings ---
    op.create_table(
        "settings",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # --- Performance indexes ---
    op.create_index("idx_memos_compiled_archived", "memos", ["compiled", "archived", "created_at"])
    op.create_index("idx_wiki_pages_type_tags", "wiki_pages", ["wiki_type", "updated_at"])


def downgrade() -> None:
    op.drop_index("idx_wiki_pages_type_tags")
    op.drop_index("idx_memos_compiled_archived")
    op.drop_table("users")
    op.drop_table("settings")
    op.drop_table("semantic_links")
    op.drop_table("ab_test_records")
    op.drop_table("game_answers")
    op.drop_table("game_sessions")
    op.drop_table("game_questions")
    op.drop_table("compilation_cache")
    op.drop_table("human_review_tasks")
    op.drop_table("compile_jobs")
    op.drop_table("wiki_links")
    op.drop_table("wiki_pages")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("memos")
