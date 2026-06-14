"""Editor Agent — revises Wiki based on reviewer feedback."""

from pathlib import Path

from app.services import llm_service

PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "multi_agent"


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


async def editor_agent(state):
    state["revision_count"] = state.get("revision_count", 0) + 1

    if state["revision_count"] > state["compilation_config"].get("max_revisions", 3):
        state["review_passed"] = True
        return state

    prompt_template = _load_prompt("editor.md")
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
