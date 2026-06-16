"""Writer Agent — converts structured knowledge into Markdown Wiki pages."""

import json
from pathlib import Path

from app.services import llm_service

PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "multi_agent"


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


async def writer_agent(state):
    prompt_template = _load_prompt("writer.md")

    # Cap memo content size to avoid enormous prompts (>64K tokens cause issues)
    memo_texts = state["memos_content"]
    total_chars = sum(len(m) for m in memo_texts)
    if total_chars > 12000:
        # Truncate each memo proportionally
        ratio = 10000 / total_chars
        memo_texts = [m[:max(200, int(len(m) * ratio))] + "…(truncated)" for m in memo_texts]

    prompt = prompt_template.format(
        integrated_knowledge=json.dumps(state["integrated_knowledge"], ensure_ascii=False),
        memos_content="\n\n".join(memo_texts),
    )

    response = await llm_service.chat_completion(
        state["_model_config"],
        messages=[{"role": "system", "content": prompt}],
        timeout=90,  # Large merged prompt needs more time
    )
    state["wiki_draft"] = response.choices[0].message.content
    return state
