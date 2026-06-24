"""Arbiter Agent — synthesizes reviewer opinions into PASS/REVISE decisions."""

import json
import logging

from app.services import llm_service
from app.utils.prompts import load_prompt

logger = logging.getLogger(__name__)


def _compute_weighted_score(reviews: list[dict]) -> dict:
    """Compute weighted final score from reviewer outputs.

    Weights: accuracy 0.6, readability 0.4 (accuracy carries more weight).
    Falls back to equal average if agent type cannot be determined.
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

    pass_threshold = 7.0
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
    prompt = prompt_template.format(
        reviews=json.dumps(state["reviews"], ensure_ascii=False),
        pass_threshold=state["compilation_config"].get("pass_threshold", 8.0),
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
        logger.error("Arbiter JSON parse failed: %s", e)
        result = _compute_weighted_score(state.get("reviews", []))

    state["final_score"] = result["final_score"]
    state["review_passed"] = result["passed"]
    state["arbitration_result"] = result
    return state
