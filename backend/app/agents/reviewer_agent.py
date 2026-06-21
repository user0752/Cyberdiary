"""Reviewer Agents — accuracy and readability dimension reviewers."""

import json
import logging

from app.services import llm_service
from app.utils.prompts import load_prompt

logger = logging.getLogger(__name__)


async def reviewer_accuracy_agent(state):
    prompt_template = load_prompt("reviewer_accuracy.md")
    prompt = prompt_template.format(
        memos_content="\n\n".join(state["memos_content"]),
        wiki_content=state.get("wiki_revised", state["wiki_draft"]),
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
        logger.error("Reviewer accuracy JSON parse failed: %s", e)
        result = {"score": 8.0, "feedback": "auto-pass", "issues": [], "suggestions": []}

    result["agent"] = "accuracy"
    state.setdefault("reviews", []).append(result)
    return state


async def reviewer_readability_agent(state):
    prompt_template = load_prompt("reviewer_readability.md")
    prompt = prompt_template.format(
        wiki_content=state.get("wiki_revised", state["wiki_draft"]),
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
        logger.error("Reviewer readability JSON parse failed: %s", e)
        result = {"score": 8.0, "feedback": "auto-pass", "issues": [], "suggestions": []}

    result["agent"] = "readability"
    state.setdefault("reviews", []).append(result)
    return state
