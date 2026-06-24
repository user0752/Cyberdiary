"""Unit tests for compile_service — parse, prompt building, model resolution."""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.compile_service import (
    parse_compile_output,
    _build_compile_messages,
    _resolve_compile_model,
    sanitize_error_message,
)


# ---------------------------------------------------------------------------
# parse_compile_output
# ---------------------------------------------------------------------------

class TestParseCompileOutput:
    """Test LLM output parsing — both JSON and legacy formats."""

    def test_json_format(self):
        output = """{"pages": [{"title": "FastAPI", "type": "concept", "content": "A web framework", "summary": "Modern Python framework", "tags": ["python", "web"]}]}"""
        pages = parse_compile_output(output, ["m1"])
        assert len(pages) == 1
        assert pages[0]["title"] == "FastAPI"
        assert pages[0]["wiki_type"] == "concept"
        assert pages[0]["source_memo_ids"] == ["m1"]
        assert "web" in pages[0]["tags"]

    def test_json_multi_page(self):
        output = """{"pages": [
            {"title": "Page 1", "type": "concept", "content": "Content 1", "summary": "S1", "tags": []},
            {"title": "Page 2", "type": "entity", "content": "Content 2", "summary": "S2", "tags": ["tag"]}
        ]}"""
        pages = parse_compile_output(output, ["m1", "m2"])
        assert len(pages) == 2
        assert pages[0]["title"] == "Page 1"
        assert pages[1]["wiki_type"] == "entity"
        assert pages[1]["tags"] == ["tag"]

    def test_unknown_wiki_type_defaults_to_concept(self):
        output = """{"pages": [{"title": "X", "type": "invalid_type", "content": "c", "summary": "", "tags": []}]}"""
        pages = parse_compile_output(output, ["m1"])
        assert pages[0]["wiki_type"] == "concept"

    def test_tags_as_string(self):
        output = """{"pages": [{"title": "X", "type": "concept", "content": "c", "summary": "", "tags": "python, web, ai"}]}"""
        pages = parse_compile_output(output, ["m1"])
        assert pages[0]["tags"] == ["python", "web", "ai"]

    def test_slug_generation_from_title(self):
        output = """{"pages": [{"title": "Python Web Framework", "type": "concept", "content": "c", "summary": "", "tags": []}]}"""
        pages = parse_compile_output(output, ["m1"])
        assert pages[0]["slug"] == "python-web-framework"

    def test_legacy_fallback_format(self):
        output = "---\ntitle: Legacy Page\ntype: entity\n---\n# Legacy Page\nSome content here."
        pages = parse_compile_output(output, ["m1"])
        assert len(pages) >= 1
        assert pages[0]["title"] == "Legacy Page"

    def test_empty_output(self):
        pages = parse_compile_output("", ["m1"])
        assert pages == []

    def test_malformed_json_graceful(self):
        pages = parse_compile_output("{invalid json", ["m1"])
        assert isinstance(pages, list)  # should not raise


# ---------------------------------------------------------------------------
# _build_compile_messages
# ---------------------------------------------------------------------------

class TestBuildCompileMessages:
    """Test prompt building."""

    def test_builds_system_and_user_messages(self):
        class FakeMemo:
            def __init__(self, content):
                self.content = content

        memos = [FakeMemo("First memo"), FakeMemo("Second memo")]
        messages = _build_compile_messages(memos)  # type: ignore[arg-type]

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "First memo" in messages[1]["content"]
        assert "Second memo" in messages[1]["content"]

    def test_empty_memos(self):
        messages = _build_compile_messages([])  # type: ignore[arg-type]
        assert messages[1]["content"]  # still produces a template


# ---------------------------------------------------------------------------
# _resolve_compile_model
# ---------------------------------------------------------------------------

class TestResolveCompileModel:
    """Test model resolution."""

    @pytest.mark.asyncio
    async def test_resolves_valid_model(self):
        mock_db = AsyncMock()
        with patch(
            "app.services.compile_service.llm_service.get_model_config_from_db",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = {"model": "deepseek/deepseek-chat"}
            result = await _resolve_compile_model(mock_db, "model-1")
            assert result == {"model": "deepseek/deepseek-chat"}

    @pytest.mark.asyncio
    async def test_raises_when_model_not_found(self):
        mock_db = AsyncMock()
        with patch(
            "app.services.compile_service.llm_service.get_model_config_from_db",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = None
            with pytest.raises(ValueError, match="Model unknown-model not configured"):
                await _resolve_compile_model(mock_db, "unknown-model")


# ---------------------------------------------------------------------------
# sanitize_error_message (from utils, used in compile_service)
# ---------------------------------------------------------------------------

class TestSanitizeErrorMessage:
    def test_masks_api_key(self):
        result = sanitize_error_message("Error with key sk-abcdefghijklmnop")
        assert "sk-***" in result
        assert "sk-abcdefghijklmnop" not in result

    def test_truncates_long_messages(self):
        long_msg = "x" * 600
        result = sanitize_error_message(long_msg)
        assert len(result) <= 500 + len("...(truncated)")

    def test_passes_safe_messages(self):
        safe = "A simple error message"
        result = sanitize_error_message(safe)
        assert result == safe
