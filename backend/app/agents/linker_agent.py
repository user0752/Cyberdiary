"""Linker Agent — discovers semantic links between current and existing Wiki pages."""

import json
import logging
from pathlib import Path

from sqlalchemy import select

from app.core.database import async_session
from app.services import llm_service

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "multi_agent"


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


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

    prompt_template = _load_prompt("linker.md")
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
