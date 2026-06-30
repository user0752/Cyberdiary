"""Chat API endpoints - conversations + SSE streaming."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.schemas.chat import ChatStreamRequest, ConversationCreate, ConversationResponse, ConversationUpdate, MessageResponse
from app.schemas.memo import ApiResponse
from app.services import chat_service

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/conversations", response_model=ApiResponse[list[ConversationResponse]])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    convs = await chat_service.list_conversations(db)
    return ApiResponse(data=[ConversationResponse.model_validate(c) for c in convs])


@router.post("/conversations", response_model=ApiResponse[ConversationResponse])
async def create_conversation(data: ConversationCreate, db: AsyncSession = Depends(get_db)):
    conv = await chat_service.create_conversation(db, data.title, data.model_id)
    return ApiResponse(data=ConversationResponse.model_validate(conv))


@router.patch("/conversations/{conv_id}", response_model=ApiResponse[ConversationResponse])
async def update_conversation(
    conv_id: str,
    data: ConversationUpdate,
    db: AsyncSession = Depends(get_db),
):
    conv = await chat_service.rename_conversation(db, conv_id, data.title)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ApiResponse(data=ConversationResponse.model_validate(conv))


@router.delete("/conversations/{conv_id}", response_model=ApiResponse)
async def delete_conversation(conv_id: str, db: AsyncSession = Depends(get_db)):
    ok = await chat_service.delete_conversation(db, conv_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ApiResponse(message="Conversation deleted")


@router.get("/conversations/{conv_id}/messages", response_model=ApiResponse[list[MessageResponse]])
async def get_messages(
    conv_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    msgs = await chat_service.get_messages(db, conv_id, limit=limit)
    return ApiResponse(data=[MessageResponse.model_validate(m) for m in msgs])


@router.post("/stream")
async def chat_stream(data: ChatStreamRequest, db: AsyncSession = Depends(get_db)):
    """SSE streaming chat endpoint."""
    async def event_generator():
        async for chunk in chat_service.chat_stream(
            db, data.conv_id, data.message, data.model_id
        ):
            yield chunk

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
