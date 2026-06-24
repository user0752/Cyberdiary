"""Linker Agent — discovers semantic links between current and existing Wiki pages."""

import json
import logging

from sqlalchemy import select

from app.core.database import async_session
from app.services import llm_service
from app.utils.prompts import load_prompt

logger = logging.getLogger(__name__)


async def _get_existing_wikis_summary(state) -> list[dict]:
    async with async_session() as db:
        try:
            from app.models.wiki import WikiPage
            result = await db.execute(
                select(WikiPage.slug, WikiPage.title, WikiPage.summary).limit(50)
            )
            return [
                {"slug": r[0], "title": r[1], "summary": r[2] or ""}
                for r in result.all()
            ]
        except Exception:
            return []


async def linker_agent(state):
    existing = await _get_existing_wikis_summary(state)
    if not existing:
        state["suggested_links"] = []
        return state

    prompt_template = load_prompt("linker.md")
    prompt = prompt_template.format(
        current_wiki=state.get("wiki_revised", state["wiki_draft"]),
        existing_wikis=json.dumps(existing, ensure_ascii=False),
    )

    response = await llm_service.chat_completion(
        state["_model_config"],
        messages=[{"role": "system", "content": prompt}],
        response_format={"type": "json_object"},
        timeout=30,
    )
    try:
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("\n```", 1)[0]
        result = json.loads(raw)
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        logger.warning("Linker JSON parse failed: %s", e)
        result = {"suggested_links": []}

    state["suggested_links"] = result.get("suggested_links", [])
    return state
