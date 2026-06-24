"""Shared test fixtures for multi-agent compile tests."""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Mock LLM response helpers
# ---------------------------------------------------------------------------

def mock_llm_response(content: str, model: str = "deepseek/deepseek-chat", tokens: int = 100):
    """Build a fake litellm ModelResponse with the given text content."""
    mock = MagicMock()
    choice = MagicMock()
    choice.message.content = content
    mock.choices = [choice]
    usage = MagicMock()
    usage.total_tokens = tokens
    mock.usage = usage
    mock.model = model
    return mock


def mock_stream_response(chunks: list[str]):
    """Build an async generator that yields fake streaming chunks."""
    async def _gen():
        for text in chunks:
            chunk = MagicMock()
            delta = MagicMock()
            delta.content = text
            choice = MagicMock()
            choice.delta = delta
            chunk.choices = [choice]
            yield chunk
    return _gen()


# ---------------------------------------------------------------------------
# Sample test data
# ---------------------------------------------------------------------------

SAMPLE_MEMOS = [
    "FastAPI is a modern Python web framework for building APIs. "
    "It uses Pydantic for data validation and supports async/await natively.",
    "SQLAlchemy 2.0 introduces a new ORM syntax with mapped_column and "
    "declarative base classes. Async support comes via aiosqlite and asyncpg.",
    "LangGraph is a framework for building stateful multi-actor applications "
    "with LLMs. It uses StateGraph with nodes and conditional edges.",
]

SAMPLE_RESEARCH_RESULT = {
    "entities": [
        {"name": "FastAPI", "type": "framework", "description": "Python web framework"},
        {"name": "SQLAlchemy", "type": "library", "description": "Python ORM"},
        {"name": "LangGraph", "type": "framework", "description": "LLM agent framework"},
    ],
    "relations": [
        {"source": "FastAPI", "target": "SQLAlchemy", "type": "uses"},
        {"source": "LangGraph", "target": "FastAPI", "type": "built_on"},
    ],
    "key_topics": ["Python", "Web Framework", "ORM", "LLM Agents"],
}

SAMPLE_INTEGRATED_KNOWLEDGE = {
    "entities": [
        {"name": "FastAPI", "type": "framework", "description": "Modern async Python web framework"},
        {"name": "SQLAlchemy 2.0", "type": "library", "description": "ORM with new syntax"},
        {"name": "LangGraph", "type": "framework", "description": "Stateful LLM agent framework"},
    ],
    "relations": [
        {"source": "FastAPI", "target": "SQLAlchemy 2.0", "type": "integrates_with"},
        {"source": "LangGraph", "target": "FastAPI", "type": "can_serve_via"},
    ],
    "gaps": [],
}

SAMPLE_WIKI_DRAFT = """# Python Backend Stack

## Overview

This wiki covers the modern Python backend stack: FastAPI, SQLAlchemy 2.0, and LangGraph.

## FastAPI

FastAPI is a modern, fast (high-performance) web framework for building APIs with Python.
It is built on Starlette and Pydantic, supporting async/await natively.

### Key Features
- Automatic OpenAPI docs
- Data validation via Pydantic
- Dependency injection system

## SQLAlchemy 2.0

SQLAlchemy 2.0 introduces significant improvements including a new ORM syntax with
`mapped_column` and declarative base classes.

## LangGraph

LangGraph is a framework for building stateful multi-actor applications with LLMs.
It uses a StateGraph pattern with nodes and conditional edges.
"""

SAMPLE_REVIEW_ACCURACY = {
    "score": 8.5,
    "feedback": "Good coverage of the three frameworks. Missing some details on async patterns.",
    "issues": ["Could expand on async session usage"],
    "suggestions": ["Add section on database session management"],
    "agent": "accuracy",
}

SAMPLE_REVIEW_READABILITY = {
    "score": 7.5,
    "feedback": "Well-structured but some sections are dense.",
    "issues": ["SQLAlchemy section could use more bullet points"],
    "suggestions": ["Break down SQLAlchemy section with examples"],
    "agent": "readability",
}

SAMPLE_ARBITRATION = {
    "final_score": 8.0,
    "passed": True,
    "summary": "Good quality overall; minor improvements suggested",
    "priority_suggestions": ["Add code examples", "Expand async section"],
    "accuracy_score": 8.5,
    "readability_score": 7.5,
}

SAMPLE_LINKS = {
    "suggested_links": [
        {"target_slug": "python-basics", "relation_type": "prerequisite", "confidence": 0.85, "reason": "Foundation knowledge"},
        {"target_slug": "api-design", "relation_type": "related", "confidence": 0.72, "reason": "Shared API concepts"},
    ]
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_state():
    """Minimal CompilationState for unit testing."""
    return {
        "memo_ids": ["m1", "m2", "m3"],
        "memos_content": SAMPLE_MEMOS,
        "compilation_config": {
            "model": "deepseek/deepseek-chat",
            "max_revisions": 3,
            "parallel_researchers": 3,
            "pass_threshold": 8.0,
            "enable_human_review": False,
        },
        "_model_config": {
            "model": "deepseek/deepseek-chat",
            "provider": "deepseek",
            "model_name": "deepseek-chat",
            "api_key_enc": "",
        },
        "job_id": "test-job-001",
        "memo_groups": [],
        "group_results": [],
        "research_results": [],
        "integrated_knowledge": {},
        "wiki_draft": "",
        "wiki_structure": {},
        "reviews": [],
        "arbitration_result": {},
        "final_score": 0.0,
        "review_passed": False,
        "revision_count": 0,
        "wiki_revised": "",
        "suggested_links": [],
        "final_wiki": "",
        "compilation_log": [],
        "current_layer": "coordinator",
        "current_agent": "coordinator",
        "next_action": "continue",
    }


@pytest.fixture
def mock_llm():
    """Patch llm_service.chat_completion to return a configurable mock."""
    with patch("app.services.llm_service.chat_completion") as mock:
        yield mock


@pytest.fixture
def mock_embedding():
    """Patch litellm.aembedding for coordinator clustering tests."""
    with patch("litellm.aembedding") as mock:
        mock.return_value = MagicMock(data=[{"embedding": [0.1] * 768}])
        yield mock


@pytest_asyncio.fixture
async def in_memory_db():
    """Create an in-memory SQLite database with schema, yield the session factory."""
    from app.core.database import Base, async_session as original_session

    # Point database to in-memory SQLite for tests
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./data/test_cybernote.db"

    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session = async_sessionmaker(engine, expire_on_commit=False)

    # Patch async_session in relevant modules
    with patch("app.services.multi_agent_graph.async_session", test_session), \
         patch("app.core.database.async_session", test_session):
        yield test_session

    await engine.dispose()


@pytest.fixture
def event_loop():
    """Create a fresh event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_session():
    """Create an in-memory SQLite database and yield a session.

    Use this for service-level tests that need a real database.
    """
    from app.core.database import Base
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    session = session_factory()

    yield session

    await session.close()
    await engine.dispose()
