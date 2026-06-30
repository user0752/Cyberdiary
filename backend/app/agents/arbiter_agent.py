"""Arbiter Agent — synthesizes reviewer opinions into PASS/REVISE decisions."""

import json
import logging

from pydantic import BaseModel, ValidationError, Field

from app.services import llm_service
from app.utils.prompts import load_prompt, safe_substitute, strip_json_fence

logger = logging.getLogger(__name__)


class ArbiterResult(BaseModel):
    """Strongly-typed schema for LLM arbiter output.

    Prevents ``TypeError`` downstream when the LLM returns e.g.
    ``{"score": "high"}`` (string instead of float) — Pydantic will
    coerce or reject, then we fall back to the heuristic scorer.
    """
    final_score: float = Field(ge=0, le=10)
    passed: bool
    summary: str = ""
    priority_suggestions: list[str] = Field(default_factory=list)
    accuracy_score: float | None = Field(default=None, ge=0, le=10)
    readability_score: float | None = Field(default=None, ge=0, le=10)


def _compute_weighted_score(reviews: list[dict], pass_threshold: float = 8.0) -> dict:
    """Compute weighted final score from reviewer outputs.

    Weights: accuracy 0.6, readability 0.4 (accuracy carries more weight).
    Falls back to equal average if agent type cannot be determined.

    P2-19: pass_threshold now defaults to 8.0 to match the LLM arbiter path
    (which reads compilation_config.pass_threshold, default 8.0). The
    previous hardcoded 7.0 here meant the fallback could PASS while the
    LLM path with the same scores would REVISE — inconsistent decisions
    for the same input depending on whether the LLM call succeeded.
    """
    accuracy_scores = []
    readability_scores = []
    all_feedback = []
    all_suggestions = []

    for r in reviews:
        score = r.get("score", 7.0)
        agent = r.get("agent", "")
        if "accuracy" in agent:
            accuracy_scores.append(score)
        elif "readability" in agent:
            readability_scores.append(score)
        else:
            accuracy_scores.append(score)

        fb = r.get("feedback", "")
        if fb:
            all_feedback.append(fb)
        suggestions = r.get("suggestions", [])
        if suggestions:
            all_suggestions.extend(suggestions if isinstance(suggestions, list) else [suggestions])

    acc_avg = sum(accuracy_scores) / max(len(accuracy_scores), 1)
    read_avg = sum(readability_scores) / max(len(readability_scores), 1)

    if accuracy_scores and readability_scores:
        final_score = round(acc_avg * 0.6 + read_avg * 0.4, 1)
    elif accuracy_scores:
        final_score = round(acc_avg, 1)
    else:
        final_score = round(read_avg, 1)

    return {
        "final_score": final_score,
        "passed": final_score >= pass_threshold,
        "summary": "; ".join(all_feedback[:3]),
        "priority_suggestions": all_suggestions[:5],
        "accuracy_score": round(acc_avg, 1),
        "readability_score": round(read_avg, 1),
    }


async def arbiter_agent(state):
    prompt_template = load_prompt("arbiter.md")
    pass_threshold = float(state["compilation_config"].get("pass_threshold", 8.0))
    prompt = safe_substitute(
        prompt_template,
        reviews=json.dumps(state["reviews"], ensure_ascii=False),
        pass_threshold=str(pass_threshold),
    )

    response = await llm_service.chat_completion(
        state["_model_config"],
        # "user" role — see writer_agent.py for rationale.
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        timeout=30,
    )
    try:
        raw = strip_json_fence(response.choices[0].message.content)
        parsed = json.loads(raw)
        # Validate types/required fields — LLM may return "score": "high"
        # or missing "passed" field, which would crash downstream consumers.
        result = ArbiterResult.model_validate(parsed).model_dump()
    except (json.JSONDecodeError, KeyError, AttributeError, ValidationError, TypeError) as e:
        logger.error("Arbiter output invalid, using heuristic scorer: %s", e)
        # Use only the latest round of reviews for the same reason as the
        # divergence guard below — full history would average in stale
        # scores from earlier revision loops.
        all_reviews_fb = state.get("reviews", [])
        latest_acc_fb = next((r for r in reversed(all_reviews_fb) if "accuracy" in r.get("agent", "")), None)
        latest_read_fb = next((r for r in reversed(all_reviews_fb) if "readability" in r.get("agent", "")), None)
        latest_reviews_fb = [r for r in [latest_acc_fb, latest_read_fb] if r is not None]
        result = _compute_weighted_score(
            latest_reviews_fb or all_reviews_fb,
            pass_threshold=pass_threshold,
        )

    state["final_score"] = result["final_score"]
    state["review_passed"] = result["passed"]
    state["arbitration_result"] = result

    # P2: Guard against LLM returning a hardcoded/anchored score (e.g.
    # always 8.2 because the prompt example used 8.2). If the LLM's
    # final_score diverges from the heuristic weighted average by more
    # than 0.5, the LLM likely didn't actually compute from reviews —
    # override with the heuristic score so pass/revise decisions are
    # consistent with the actual review content.
    #
    # Use only the LATEST round of reviews (last accuracy + last
    # readability) so the heuristic reflects the current revision, not
    # the full history accumulated across revision loops.
    all_reviews = state.get("reviews", [])
    latest_acc = next((r for r in reversed(all_reviews) if "accuracy" in r.get("agent", "")), None)
    latest_read = next((r for r in reversed(all_reviews) if "readability" in r.get("agent", "")), None)
    latest_reviews = [r for r in [latest_acc, latest_read] if r is not None]
    if latest_reviews:
        heuristic = _compute_weighted_score(latest_reviews, pass_threshold=pass_threshold)
        if abs(result["final_score"] - heuristic["final_score"]) > 0.5:
            logger.warning(
                "Arbiter LLM score %.1f diverges from heuristic %.1f — overriding with heuristic",
                result["final_score"], heuristic["final_score"],
            )
            result["final_score"] = heuristic["final_score"]
            result["passed"] = heuristic["passed"]
            state["final_score"] = result["final_score"]
            state["review_passed"] = result["passed"]
            state["arbitration_result"] = result

    return state
