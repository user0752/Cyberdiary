"""Writer Agent — converts structured knowledge into Markdown Wiki pages."""

import json

from app.services import llm_service
from app.utils.prompts import load_prompt


async def writer_agent(state):
    prompt_template = load_prompt("writer.md")

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
