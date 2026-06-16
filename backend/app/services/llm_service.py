"""LiteLLM unified wrapper - routes to DeepSeek / Qwen / Ollama."""

import asyncio
import json
import logging
from typing import AsyncGenerator

import httpx
import litellm

from app.core.config import settings
from app.core.security import decrypt_api_key
from app.core.llm_cache import LLMCache

litellm.drop_params = True  # Ignore unsupported params for different providers

logger = logging.getLogger(__name__)

# Global LLM cache instance (lazy-initialized on first use)
llm_cache = LLMCache(db_path="./data/llm_cache.db", memory_size=100, ttl=86400)




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
    try:
        api_key = decrypt_api_key(model_config.get("api_key_enc", ""))
    except Exception:
        logger.warning("Failed to decrypt API key for model %s — using empty key", model_name)
        api_key = ""
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
    **kwargs,
) -> litellm.ModelResponse | AsyncGenerator:
    """Unified chat completion entry point with LLM cache support.

    Extra kwargs (response_format, timeout, temperature, etc.) are
    forwarded directly to litellm.acompletion.
    """
    # Extract hard timeout from kwargs (default 60s), remove before forwarding
    hard_timeout = kwargs.pop("timeout", 60.0)

    # Check cache for non-streaming calls
    if not stream:
        prompt_snapshot = json.dumps(messages, ensure_ascii=False)
        model_name = model_config.get("model_name", "")
        cached = await llm_cache.get(prompt_snapshot, model_name, timeout=hard_timeout, **kwargs)
        if cached:
            logger.debug("LLM cache hit")
            return litellm.ModelResponse.model_validate_json(cached)

    try:
        kw = build_litellm_kwargs(model_config)
    except Exception as e:
        logger.error("Failed to build litellm kwargs (bad model config): %s", e)
        raise ValueError(f"Model configuration error: {e}") from e

    kw["messages"] = messages
    kw["stream"] = stream
    kw["timeout"] = hard_timeout  # Pass to litellm so httpx sets TCP-level timeout
    kw.update(kwargs)

    model_name = kw.get("model", "unknown")

    try:
        result = await asyncio.wait_for(
            litellm.acompletion(**kw),
            timeout=hard_timeout + 10,  # 10s buffer: litellm timeout fires first
        )
    except asyncio.TimeoutError:
        logger.error(
            "LLM call timed out after %.1fs to model %s",
            hard_timeout, model_name,
        )
        raise asyncio.TimeoutError(
            f"LLM request to {model_name} timed out after {hard_timeout}s"
        )

    # Cache non-streaming responses
    if not stream and hasattr(result, "model_dump_json"):
        prompt_snapshot = json.dumps(messages, ensure_ascii=False)
        model_name = model_config.get("model_name", "")
        await llm_cache.set(prompt_snapshot, model_name, result.model_dump_json(), timeout=hard_timeout, **kwargs)

    return result


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
