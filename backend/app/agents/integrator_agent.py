"""Integrator Agent — merges multiple research results into unified knowledge."""

import json
import logging
from pathlib import Path

from app.services import llm_service

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "multi_agent"


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


async def integrator_agent(state):
    prompt_template = _load_prompt("integrator.md")

    # Trim research results to avoid enormous prompts that cause API timeouts.
    # Each researcher returns entities, relations, key_topics — keeping only
    # essential fields and capping counts per researcher.
    trimmed = []
    for r in state["research_results"]:
        if isinstance(r, dict):
            trimmed.append({
                "_focus": r.get("_focus", "unknown"),
                "entities": (r.get("entities") or [])[:15],
                "relations": (r.get("relations") or [])[:10],
                "key_topics": (r.get("key_topics") or [])[:10],
            })
    prompt = prompt_template.format(
        research_results=json.dumps(trimmed, ensure_ascii=False),
    )

    response = await llm_service.chat_completion(
        state["_model_config"],
        messages=[{"role": "system", "content": prompt}],
        response_format={"type": "json_object"},
        timeout=90,  # Large merged prompt — needs more time
    )
    try:
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("\n```", 1)[0]
        result = json.loads(raw)
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        logger.error("Integrator JSON parse failed: %s", e)
        result = {"entities": [], "relations": [], "gaps": ["parse_error"]}

    state["integrated_knowledge"] = result
    return state
