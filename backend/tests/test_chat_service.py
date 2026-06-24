"""Unit tests for chat_service - conversation CRUD and context building."""

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.models  # noqa: F401 - register all models with Base.metadata
from app.services import chat_service


FAKE_MODEL_CONFIG = {
    "model": "deepseek/deepseek-chat",
    "provider": "deepseek",
    "model_name": "deepseek-chat",
    "api_key_enc": "",
    "display_name": "DeepSeek Chat",
}


class TestConversationCRUD:
    @pytest.mark.asyncio
    async def test_create_conversation(self, db_session):
        conv = await chat_service.create_conversation(db_session, "Test Conv", "model-1")
        assert conv.id is not None
        assert conv.title == "Test Conv"
        assert conv.model_id == "model-1"

    @pytest.mark.asyncio
    async def test_get_conversation(self, db_session):
        conv = await chat_service.create_conversation(db_session, "Test Conv", "model-1")
        fetched = await chat_service.get_conversation(db_session, conv.id)
        assert fetched is not None
        assert fetched.id == conv.id
        assert fetched.title == "Test Conv"

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, db_session):
        result = await chat_service.get_conversation(db_session, "nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_conversations(self, db_session):
        conv1 = await chat_service.create_conversation(db_session, "Conv 1", "model-1")
        conv2 = await chat_service.create_conversation(db_session, "Conv 2", "model-1")
        conv3 = await chat_service.create_conversation(db_session, "Conv 3", "model-1")

        base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        conv1.updated_at = base_time
        conv2.updated_at = base_time + timedelta(hours=1)
        conv3.updated_at = base_time + timedelta(hours=2)
        await db_session.flush()

        result = await chat_service.list_conversations(db_session)
        assert len(result) == 3
        assert result[0].id == conv3.id
        assert result[1].id == conv2.id
        assert result[2].id == conv1.id

    @pytest.mark.asyncio
    async def test_delete_conversation(self, db_session):
        conv = await chat_service.create_conversation(db_session, "Test Conv", "model-1")
        result = await chat_service.delete_conversation(db_session, conv.id)
        assert result is True
        fetched = await chat_service.get_conversation(db_session, conv.id)
        assert fetched is None

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, db_session):
        result = await chat_service.delete_conversation(db_session, "nonexistent-id")
        assert result is False


class TestMessageCRUD:
    @pytest.mark.asyncio
    async def test_add_message(self, db_session):
        conv = await chat_service.create_conversation(db_session, "Test Conv", "model-1")
        msg = await chat_service.add_message(db_session, conv.id, "user", "Hello world")
        assert msg.id is not None
        assert msg.conv_id == conv.id
        assert msg.role == "user"
        assert msg.content == "Hello world"

    @pytest.mark.asyncio
    async def test_get_messages(self, db_session):
        conv = await chat_service.create_conversation(db_session, "Test Conv", "model-1")
        msg1 = await chat_service.add_message(db_session, conv.id, "user", "First")
        msg2 = await chat_service.add_message(db_session, conv.id, "assistant", "Second")
        msg3 = await chat_service.add_message(db_session, conv.id, "user", "Third")

        base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        msg1.created_at = base_time
        msg2.created_at = base_time + timedelta(seconds=1)
        msg3.created_at = base_time + timedelta(seconds=2)
        await db_session.flush()

        result = await chat_service.get_messages(db_session, conv.id)
        assert len(result) == 3
        assert result[0].id == msg1.id
        assert result[1].id == msg2.id
        assert result[2].id == msg3.id

    @pytest.mark.asyncio
    async def test_get_messages_empty(self, db_session):
        conv = await chat_service.create_conversation(db_session, "Test Conv", "model-1")
        result = await chat_service.get_messages(db_session, conv.id)
        assert result == []


class TestBuildChatContext:
    @pytest.mark.asyncio
    @patch("app.services.chat_service.llm_service.get_model_config_from_db", new_callable=AsyncMock)
    async def test_build_chat_context(self, mock_get_model, db_session):
        mock_get_model.return_value = FAKE_MODEL_CONFIG
        conv = await chat_service.create_conversation(db_session, "Test Conv", "model-1")
        await chat_service.add_message(db_session, conv.id, "user", "Previous question")
        await chat_service.add_message(db_session, conv.id, "assistant", "Previous answer")

        messages, model_id = await chat_service.build_chat_context(
            db_session, conv.id, "New question"
        )

        assert isinstance(messages, list)
        assert model_id == "model-1"
        assert messages[0]["role"] == "system"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "New question"
        assert "(知识库暂无内容" in messages[0]["content"]

    @pytest.mark.asyncio
    async def test_build_chat_context_no_conversation(self, db_session):
        with pytest.raises(ValueError, match="Conversation not found"):
            await chat_service.build_chat_context(db_session, "nonexistent-id", "Hello")

    @pytest.mark.asyncio
    @patch("app.services.chat_service.llm_service.get_model_config_from_db", new_callable=AsyncMock)
    async def test_build_chat_context_no_model(self, mock_get_model, db_session):
        mock_get_model.return_value = None
        conv = await chat_service.create_conversation(db_session, "Test Conv", "model-1")
        with pytest.raises(ValueError, match="Model not configured"):
            await chat_service.build_chat_context(db_session, conv.id, "Hello")
