"""Editor Agent — revises Wiki based on reviewer feedback."""

from app.services import llm_service
from app.utils.prompts import load_prompt


async def editor_agent(state):
    state["revision_count"] = state.get("revision_count", 0) + 1

    if state["revision_count"] > state["compilation_config"].get("max_revisions", 3):
        state["review_passed"] = True
        return state

    prompt_template = load_prompt("editor.md")
    prompt = prompt_template.format(
        wiki_content=state.get("wiki_revised", state["wiki_draft"]),
        feedback=state["arbitration_result"].get("summary", ""),
        suggestions="\n".join(
            state["arbitration_result"].get("priority_suggestions", [])
        ),
    )

    response = await llm_service.chat_completion(
        state["_model_config"],
        messages=[{"role": "system", "content": prompt}],
        timeout=45,
    )
    state["wiki_revised"] = response.choices[0].message.content
    return state
