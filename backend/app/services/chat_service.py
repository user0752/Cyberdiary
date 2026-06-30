"""Chat business logic - context injection + SSE streaming."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.chat import Conversation, Message
from app.services import llm_service
from app.services import wiki_service

logger = logging.getLogger(__name__)


async def create_conversation(db: AsyncSession, title: str, model_id: str) -> Conversation:
    conv = Conversation(
        id=str(uuid.uuid4()),
        title=title,
        model_id=model_id,
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return conv


async def list_conversations(db: AsyncSession) -> list[Conversation]:
    result = await db.execute(
        select(Conversation).order_by(Conversation.updated_at.desc())
    )
    return list(result.scalars().all())


async def get_conversation(db: AsyncSession, conv_id: str) -> Conversation | None:
    result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
    return result.scalar_one_or_none()


async def delete_conversation(db: AsyncSession, conv_id: str) -> bool:
    conv = await get_conversation(db, conv_id)
    if not conv:
        return False
    # Delete messages first
    await db.execute(delete(Message).where(Message.conv_id == conv_id))
    await db.delete(conv)
    await db.flush()
    return True


async def rename_conversation(db: AsyncSession, conv_id: str, title: str) -> Conversation | None:
    conv = await get_conversation(db, conv_id)
    if not conv:
        return None
    conv.title = title
    conv.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(conv)
    return conv


async def get_messages(db: AsyncSession, conv_id: str, limit: int = 50) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conv_id == conv_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def add_message(db: AsyncSession, conv_id: str, role: str, content: str) -> Message:
    msg = Message(
        id=str(uuid.uuid4()),
        conv_id=conv_id,
        role=role,
        content=content,
    )
    db.add(msg)
    await db.flush()
    await db.refresh(msg)
    return msg


async def build_chat_context(db: AsyncSession, conv_id: str, user_message: str) -> tuple[list[dict], str]:
    """Build messages array with system prompt + history + new user message.
    Returns (messages, model_id)."""
    conv = await get_conversation(db, conv_id)
    if not conv:
        raise ValueError("Conversation not found")

    model_config = await llm_service.get_model_config_from_db(db, conv.model_id)
    if not model_config:
        raise ValueError("Model not configured")

    # Get history
    history = await get_messages(db, conv_id)
    history_msgs = [{"role": m.role, "content": m.content} for m in history]

    # Build system prompt with Wiki context
    wiki_pages = await wiki_service.get_wiki_summaries(db, limit=50)
    if wiki_pages:
        wiki_context = "\n".join([
            f"- **{p.title}** ({p.wiki_type}): {p.summary}"
            for p in wiki_pages
        ])
    else:
        wiki_context = "(知识库暂无内容，请先编译笔记)"

    # Read chat system prompt template
    from pathlib import Path
    from app.utils.prompts import safe_substitute
    prompt_path = Path(__file__).parent.parent / "prompts" / "chat_system.md"
    model_display_name = model_config.get("display_name") or model_config.get("model_name", "unknown")
    try:
        template = prompt_path.read_text(encoding="utf-8")
        # Use safe_substitute so curly braces in wiki_context (e.g. JSON
        # snippets, code) cannot raise KeyError and crash the chat. Wrap
        # wiki content in a fence to mark it as data, mitigating prompt
        # injection from user-authored wiki pages.
        system_prompt = safe_substitute(
            template,
            wiki_context=f"<user_content>\n{wiki_context}\n</user_content>",
            model_name=model_display_name,
        )
    except Exception:
        system_prompt = (
            f"你是用户的个人知识助手，代号「赛博龙虾」。你当前运行的底层模型是：{model_display_name}。\n\n"
            f"## 用户的知识库摘要\n{wiki_context}\n\n"
            "回答时优先引用知识库中的内容。如果用户的问题与知识库无关，正常回答即可。"
            "用中文回答，语气自然，不要机器腔。"
        )

    messages = [{"role": "system", "content": system_prompt}] + history_msgs + [
        {"role": "user", "content": user_message}
    ]

    return messages, conv.model_id


async def chat_stream(
    db: AsyncSession,
    conv_id: str | None,
    message: str,
    model_id: str,
) -> AsyncGenerator[str, None]:
    """Stream chat response via SSE. Yields content chunks.

    Uses independent DB sessions for message persistence and context loading
    so the request-level session is NOT held open for the entire SSE lifetime
    (which can be 60-90s during LLM streaming). The request session is only
    used briefly to load context, then closed before streaming begins.
    """
    # Create conversation and save user message in an independent session
    async with async_session() as msg_db:
        async with msg_db.begin():
            if not conv_id:
                conv = Conversation(
                    id=str(uuid.uuid4()),
                    title="新对话",
                    model_id=model_id,
                )
                msg_db.add(conv)
                await msg_db.flush()
                conv_id = conv.id

            # Save user message
            user_msg = Message(
                id=str(uuid.uuid4()),
                conv_id=conv_id,
                role="user",
                content=message,
            )
            msg_db.add(user_msg)

            # Update conversation title (use first 30 chars of user message)
            conv = (await msg_db.execute(
                select(Conversation).where(Conversation.id == conv_id)
            )).scalar_one_or_none()
            if conv and len(conv.title) < 5:
                conv.title = message[:30] + ("..." if len(message) > 30 else "")
                conv.updated_at = datetime.now(timezone.utc)

    # Build messages array using build_chat_context in an independent session.
    # This ensures the request-level `db` session is not held during LLM streaming.
    try:
        async with async_session() as ctx_db:
            messages, _ = await build_chat_context(ctx_db, conv_id, message)
        # Also resolve model config in the same short-lived session
        async with async_session() as cfg_db:
            model_config = await llm_service.get_model_config_from_db(cfg_db, model_id)
    except ValueError as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
        yield "data: [DONE]\n\n"
        return

    if not model_config:
        yield f"data: {json.dumps({'error': 'Model not configured'})}\n\n"
        yield "data: [DONE]\n\n"
        return

    # Stream — no DB session held during this long-running loop
    full_response = ""
    try:
        response = await llm_service.chat_completion(model_config, messages, stream=True)
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                full_response += token
                yield f"data: {json.dumps({'content': token, 'conv_id': conv_id})}\n\n"

        # Save assistant response in an independent session
        if full_response:
            try:
                async with async_session() as save_db:
                    async with save_db.begin():
                        assistant_msg = Message(
                            id=str(uuid.uuid4()),
                            conv_id=conv_id,
                            role="assistant",
                            content=full_response,
                        )
                        save_db.add(assistant_msg)
            except Exception:
                logger.exception("Failed to save assistant response for conv %s", conv_id)

        yield "data: [DONE]\n\n"

    except Exception as e:
        # Sanitize — LLM provider exceptions may contain endpoint/api-key fragments.
        from app.utils.sanitize import sanitize_error_message
        error_msg = sanitize_error_message(str(e))
        yield f"data: {json.dumps({'error': error_msg, 'conv_id': conv_id})}\n\n"
        yield "data: [DONE]\n\n"
