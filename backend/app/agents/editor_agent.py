"""Editor Agent — revises Wiki based on reviewer feedback."""

import logging

from app.services import llm_service
from app.utils.prompts import load_prompt, safe_substitute

logger = logging.getLogger(__name__)


async def editor_agent(state):
    state["revision_count"] = state.get("revision_count", 0) + 1

    if state["revision_count"] > state["compilation_config"].get("max_revisions", 3):
        state["review_passed"] = True
        return state

    # Guard: if the writer produced empty/garbage output, revising it is
    # pointless — the editor would see an empty "原始 Wiki" section and
    # reply with conversational text like "请提供原文", which then leaks
    # into the Wiki as the final content. Skip revision and let the
    # caller fall back to wiki_draft (or empty) instead.
    wiki_content = state.get("wiki_revised") or state.get("wiki_draft") or ""
    if not wiki_content.strip():
        logger.warning(
            "Editor: wiki_content is empty (revision #%d) — skipping revision",
            state["revision_count"],
        )
        state["wiki_revised"] = state.get("wiki_draft", "")
        state["review_passed"] = True
        return state

    prompt_template = load_prompt("editor.md")
    prompt = safe_substitute(
        prompt_template,
        wiki_content=wiki_content,
        feedback=state["arbitration_result"].get("summary", ""),
        suggestions="\n".join(
            state["arbitration_result"].get("priority_suggestions", [])
        ),
    )

    response = await llm_service.chat_completion(
        state["_model_config"],
        # "user" role — see writer_agent.py for rationale.
        messages=[{"role": "user", "content": prompt}],
        timeout=45,
    )
    state["wiki_revised"] = response.choices[0].message.content
    return state
