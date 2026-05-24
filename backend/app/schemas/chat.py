"""Pydantic schemas for Chat."""

from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = "新对话"
    model_id: str = Field(..., min_length=1)


class ConversationResponse(BaseModel):
    id: str
    title: str
    model_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    conv_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatStreamRequest(BaseModel):
    conv_id: str | None = None          # None = create new conversation
    message: str = Field(..., min_length=1)
    model_id: str = Field(..., min_length=1)


class ChatHistoryResponse(BaseModel):
    conversation: ConversationResponse
    messages: list[MessageResponse]
