"""Unit tests for model management — DB read/write helpers."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.models  # noqa: F401 - register all models with Base.metadata
from app.api.v1.model import get_models_from_db, save_models_to_db, ModelCreate
from app.core.security import encrypt_api_key


@pytest.mark.asyncio
async def test_get_models_from_db_empty(db_session):
    """No models stored yet → returns empty list."""
    models = await get_models_from_db(db_session)
    assert models == []


@pytest.mark.asyncio
async def test_save_and_retrieve_models(db_session):
    """Save models then retrieve them."""
    sample = [
        {
            "id": "model-1",
            "provider": "deepseek",
            "model_name": "deepseek-chat",
            "display_name": "DeepSeek",
            "api_key_enc": encrypt_api_key("sk-test-key"),
            "endpoint": "",
            "enabled": True,
        }
    ]
    await save_models_to_db(db_session, sample)

    models = await get_models_from_db(db_session)
    assert len(models) == 1
    assert models[0]["id"] == "model-1"
    assert models[0]["provider"] == "deepseek"


@pytest.mark.asyncio
async def test_save_models_overwrites_existing(db_session):
    """Saving again should update, not duplicate."""
    v1 = [{"id": "m1", "provider": "deepseek", "model_name": "v1", "display_name": "V1", "api_key_enc": "", "endpoint": "", "enabled": True}]
    v2 = [{"id": "m2", "provider": "qwen", "model_name": "v2", "display_name": "V2", "api_key_enc": "", "endpoint": "", "enabled": True}]

    await save_models_to_db(db_session, v1)
    await save_models_to_db(db_session, v2)

    models = await get_models_from_db(db_session)
    assert len(models) == 1
    assert models[0]["provider"] == "qwen"


@pytest.mark.asyncio
async def test_multiple_models(db_session):
    """Store multiple models simultaneously."""
    sample = [
        {"id": "a", "provider": "deepseek", "model_name": "ds", "display_name": "DS", "api_key_enc": "", "endpoint": "", "enabled": True},
        {"id": "b", "provider": "qwen", "model_name": "qw", "display_name": "QW", "api_key_enc": "", "endpoint": "", "enabled": True},
        {"id": "c", "provider": "ollama", "model_name": "llama", "display_name": "Llama", "api_key_enc": "", "endpoint": "", "enabled": False},
    ]
    await save_models_to_db(db_session, sample)

    models = await get_models_from_db(db_session)
    assert len(models) == 3
    providers = {m["provider"] for m in models}
    assert providers == {"deepseek", "qwen", "ollama"}
