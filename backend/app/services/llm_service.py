"""LiteLLM unified wrapper - routes to DeepSeek / Qwen / Ollama."""

import json
from typing import AsyncGenerator

import httpx
import litellm

from app.core.config import settings
from app.core.security import decrypt_api_key

litellm.drop_params = True  # Ignore unsupported params for different providers


async def get_model_config_from_db(db, model_id: str) -> dict | None:
    """Fetch model config from settings table."""
    from sqlalchemy import select
    from app.models.settings import Setting

    result = await db.execute(select(Setting).where(Setting.key == "models"))
    row = result.scalar_one_or_none()
    if not row:
        return None

    models = json.loads(row.value)
    for m in models:
        if m.get("id") == model_id:
            return m
    return None


def build_litellm_kwargs(model_config: dict) -> dict:
    """Convert model config dict to litellm kwargs."""
    provider = model_config.get("provider", "deepseek")
    model_name = model_config.get("model_name", "")
    api_key = decrypt_api_key(model_config.get("api_key_enc", ""))
    endpoint = model_config.get("endpoint", "")

    kwargs = {"api_key": api_key}

    if provider == "deepseek":
        kwargs["model"] = f"deepseek/{model_name}" if not model_name.startswith("deepseek/") else model_name
        if endpoint:
            kwargs["api_base"] = endpoint
    elif provider == "qwen":
        # Qwen uses DashScope OpenAI-compatible API
        # Use openai/ prefix so litellm routes to OpenAI-compatible mode
        kwargs["model"] = f"openai/{model_name}"
        kwargs["api_base"] = endpoint or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    elif provider == "ollama":
        kwargs["model"] = f"ollama/{model_name}" if not model_name.startswith("ollama/") else model_name
        kwargs["api_base"] = endpoint or settings.ollama_base_url
    elif provider == "mimo":
        kwargs["model"] = f"openai/{model_name}"
        kwargs["api_base"] = endpoint or "https://api.xiaomimimo.com/v1"

    return kwargs


async def chat_completion(
    model_config: dict,
    messages: list[dict],
    stream: bool = False,
) -> litellm.ModelResponse | AsyncGenerator:
    """Unified chat completion entry point."""
    kwargs = build_litellm_kwargs(model_config)
    kwargs["messages"] = messages
    kwargs["stream"] = stream

    return await litellm.acompletion(**kwargs)


async def test_model_connection(model_config: dict) -> dict:
    """Test if a model is reachable. Returns {ok: bool, message: str}."""
    try:
        kwargs = build_litellm_kwargs(model_config)
        kwargs["messages"] = [{"role": "user", "content": "ping"}]
        kwargs["max_tokens"] = 5
        kwargs["stream"] = False

        response = await litellm.acompletion(**kwargs)
        content = response.choices[0].message.content if response.choices else ""
        return {"ok": True, "message": f"Connected. Response: {content[:50]}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}


async def list_ollama_models() -> list[dict]:
    """Probe local Ollama for available models."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return [{"name": m["name"], "provider": "ollama"} for m in models]
    except Exception:
        pass
    return []
