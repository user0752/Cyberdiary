"""Integrator Agent — merges multiple research results into unified knowledge."""

import json
import logging

from app.services import llm_service
from app.utils.prompts import load_prompt, safe_substitute, strip_json_fence

logger = logging.getLogger(__name__)


async def integrator_agent(state):
    prompt_template = load_prompt("integrator.md")

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
    prompt = safe_substitute(
        prompt_template,
        research_results=json.dumps(trimmed, ensure_ascii=False),
    )

    response = await llm_service.chat_completion(
        state["_model_config"],
        # "user" role — see writer_agent.py for rationale.
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        timeout=90,  # Large merged prompt — needs more time
    )
    try:
        raw = strip_json_fence(response.choices[0].message.content)
        result = json.loads(raw)
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        logger.error("Integrator JSON parse failed: %s", e)
        result = {"entities": [], "relations": [], "gaps": ["parse_error"]}

    state["integrated_knowledge"] = result
    return state
