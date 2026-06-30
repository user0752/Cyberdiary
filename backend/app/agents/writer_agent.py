"""Writer Agent — converts structured knowledge into Markdown Wiki pages."""

import json

from app.services import llm_service
from app.utils.prompts import load_prompt, safe_substitute


async def writer_agent(state):
    prompt_template = load_prompt("writer.md")

    # Cap memo content size to avoid enormous prompts (>64K tokens cause issues)
    memo_texts = state["memos_content"]
    total_chars = sum(len(m) for m in memo_texts)
    if total_chars > 12000:
        # Truncate each memo proportionally
        ratio = 10000 / total_chars
        memo_texts = [m[:max(200, int(len(m) * ratio))] + "…(truncated)" for m in memo_texts]

    prompt = safe_substitute(
        prompt_template,
        integrated_knowledge=json.dumps(state["integrated_knowledge"], ensure_ascii=False),
        memos_content="\n\n".join(memo_texts),
    )

    response = await llm_service.chat_completion(
        state["_model_config"],
        # Use "user" role, not "system": the prompt is a task spec with
        # embedded input data, not a behavioral directive. Some chat models
        # (DeepSeek/Qwen/Mimo) respond to a system-only turn by asking the
        # user for the actual content ("请提供原文..."), which leaks into
        # the Wiki as conversational text. A user turn triggers actual
        # generation.
        messages=[{"role": "user", "content": prompt}],
        timeout=90,  # Large merged prompt needs more time
    )
    state["wiki_draft"] = response.choices[0].message.content
    return state
