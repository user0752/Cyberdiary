"""Reviewer Agents — accuracy and readability dimension reviewers."""

import json
import logging

from pydantic import BaseModel, ValidationError, Field

from app.services import llm_service
from app.utils.prompts import load_prompt, safe_substitute, strip_json_fence

logger = logging.getLogger(__name__)


class ReviewerResult(BaseModel):
    """Validated schema for reviewer LLM output. Coerces/validates score
    to float in [0, 10] so the arbiter's weighted average cannot crash
    with TypeError on strings like "high"."""
    score: float = Field(ge=0, le=10)
    feedback: str = ""
    issues: list = Field(default_factory=list)
    suggestions: list = Field(default_factory=list)


def _coerce_review(raw: dict, agent_name: str) -> dict:
    """Apply ReviewerResult schema, falling back to a safe default."""
    try:
        return ReviewerResult.model_validate(raw).model_dump()
    except (ValidationError, TypeError) as e:
        logger.error("Reviewer(%s) output invalid, using fallback: %s", agent_name, e)
        return {"score": 8.0, "feedback": "auto-pass", "issues": [], "suggestions": []}


async def reviewer_accuracy_agent(state):
    prompt_template = load_prompt("reviewer_accuracy.md")
    prompt = safe_substitute(
        prompt_template,
        memos_content="\n\n".join(state["memos_content"]),
        wiki_content=state.get("wiki_revised", state["wiki_draft"]),
    )

    response = await llm_service.chat_completion(
        state["_model_config"],
        # "user" role — see writer_agent.py for rationale.
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        timeout=60,
    )
    try:
        raw = strip_json_fence(response.choices[0].message.content)
        parsed = json.loads(raw)
        result = _coerce_review(parsed, "accuracy")
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        logger.error("Reviewer accuracy JSON parse failed: %s", e)
        result = _coerce_review({}, "accuracy")

    result["agent"] = "accuracy"
    state.setdefault("reviews", []).append(result)
    return state


async def reviewer_readability_agent(state):
    prompt_template = load_prompt("reviewer_readability.md")
    prompt = safe_substitute(
        prompt_template,
        wiki_content=state.get("wiki_revised", state["wiki_draft"]),
    )

    response = await llm_service.chat_completion(
        state["_model_config"],
        # "user" role — see writer_agent.py for rationale.
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        timeout=60,
    )
    try:
        raw = strip_json_fence(response.choices[0].message.content)
        parsed = json.loads(raw)
        result = _coerce_review(parsed, "readability")
    except (json.JSONDecodeError, KeyError, AttributeError) as e:
        logger.error("Reviewer readability JSON parse failed: %s", e)
        result = _coerce_review({}, "readability")

    result["agent"] = "readability"
    state.setdefault("reviews", []).append(result)
    return state
