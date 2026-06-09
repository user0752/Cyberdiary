"""Model management API endpoints."""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.security import encrypt_api_key
from app.models.settings import Setting
from app.schemas.memo import ApiResponse
from app.services import llm_service

router = APIRouter(prefix="/models", tags=["models"])


class ModelCreate(BaseModel):
    provider: str = Field(..., pattern=r"^(deepseek|qwen|ollama|mimo)$")
    model_name: str = Field(..., min_length=1)
    display_name: str = ""
    api_key: str = ""
    endpoint: str = ""


class ModelUpdate(BaseModel):
    display_name: str | None = None
    api_key: str | None = None
    endpoint: str | None = None
    enabled: bool | None = None


async def get_models_from_db(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(Setting).where(Setting.key == "models"))
    row = result.scalar_one_or_none()
    if not row:
        return []
    return json.loads(row.value)


async def save_models_to_db(db: AsyncSession, models: list[dict]):
    result = await db.execute(select(Setting).where(Setting.key == "models"))
    row = result.scalar_one_or_none()
    if row:
        row.value = json.dumps(models, ensure_ascii=False)
        row.updated_at = datetime.now(timezone.utc)
    else:
        db.add(Setting(key="models", value=json.dumps(models, ensure_ascii=False)))
    await db.flush()


@router.get("", response_model=ApiResponse[list[dict]])
async def list_models(db: AsyncSession = Depends(get_db)):
    models = await get_models_from_db(db)
    # Mask API keys in response
    safe = []
    for m in models:
        m_copy = dict(m)
        if m_copy.get("api_key_enc"):
            m_copy["api_key_enc"] = "***"
        safe.append(m_copy)
    return ApiResponse(data=safe)


@router.post("", response_model=ApiResponse[dict])
async def create_model(data: ModelCreate, db: AsyncSession = Depends(get_db)):
    models = await get_models_from_db(db)

    model_entry = {
        "id": str(uuid.uuid4()),
        "provider": data.provider,
        "model_name": data.model_name,
        "display_name": data.display_name or data.model_name,
        "api_key_enc": encrypt_api_key(data.api_key) if data.api_key else "",
        "endpoint": data.endpoint,
        "enabled": True,
    }
    models.append(model_entry)
    await save_models_to_db(db, models)

    return ApiResponse(data=model_entry)


@router.put("/{model_id}", response_model=ApiResponse[dict])
async def update_model(model_id: str, data: ModelUpdate, db: AsyncSession = Depends(get_db)):
    models = await get_models_from_db(db)
    for m in models:
        if m["id"] == model_id:
            if data.display_name is not None:
                m["display_name"] = data.display_name
            if data.api_key is not None and data.api_key:
                m["api_key_enc"] = encrypt_api_key(data.api_key)
            if data.endpoint is not None:
                m["endpoint"] = data.endpoint
            if data.enabled is not None:
                m["enabled"] = data.enabled
            await save_models_to_db(db, models)
            return ApiResponse(data=m)
    raise HTTPException(status_code=404, detail="Model not found")


@router.delete("/{model_id}", response_model=ApiResponse)
async def delete_model(model_id: str, db: AsyncSession = Depends(get_db)):
    models = await get_models_from_db(db)
    models = [m for m in models if m["id"] != model_id]
    await save_models_to_db(db, models)
    return ApiResponse(message="Model deleted")


@router.post("/{model_id}/test", response_model=ApiResponse[dict])
async def test_model(model_id: str, db: AsyncSession = Depends(get_db)):
    models = await get_models_from_db(db)
    for m in models:
        if m["id"] == model_id:
            result = await llm_service.test_model_connection(m)
            return ApiResponse(data=result)
    raise HTTPException(status_code=404, detail="Model not found")


@router.get("/ollama/list", response_model=ApiResponse[list[dict]])
async def list_ollama_models():
    models = await llm_service.list_ollama_models()
    return ApiResponse(data=models)


class ModelDefaults(BaseModel):
    default_chat_model: str = ""
    default_compile_model: str = ""


@router.get("/defaults", response_model=ApiResponse[ModelDefaults])
async def get_model_defaults(db: AsyncSession = Depends(get_db)):
    """Get default model IDs for chat and compile."""
    defaults = ModelDefaults()
    for key in ("default_chat_model", "default_compile_model"):
        result = await db.execute(select(Setting).where(Setting.key == key))
        row = result.scalar_one_or_none()
        if row:
            setattr(defaults, key, row.value)
    return ApiResponse(data=defaults)


@router.put("/defaults", response_model=ApiResponse)
async def update_model_defaults(data: ModelDefaults, db: AsyncSession = Depends(get_db)):
    """Set default model IDs for chat and compile."""
    from datetime import datetime, timezone
    for key, value in data.model_dump().items():
        if not value:  # Skip empty values to avoid overwriting existing defaults
            continue
        result = await db.execute(select(Setting).where(Setting.key == key))
        row = result.scalar_one_or_none()
        if row:
            row.value = value
            row.updated_at = datetime.now(timezone.utc)
        else:
            db.add(Setting(key=key, value=value))
    await db.commit()
    return ApiResponse(message="Defaults updated")
