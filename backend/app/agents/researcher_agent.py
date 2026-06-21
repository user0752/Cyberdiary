"""Researcher Agent — multi-perspective parallel research pool."""

import asyncio
import json
import logging

from app.services import llm_service
from app.utils.prompts import load_prompt

logger = logging.getLogger(__name__)

FOCUS_CONFIG = [
    {"name": "technical", "label": "技术视角", "prompt_extra": "关注技术细节、架构设计、代码实现"},
    {"name": "practical", "label": "实践视角", "prompt_extra": "关注应用场景、案例、最佳实践"},
    {"name": "theoretical", "label": "理论视角", "prompt_extra": "关注基础理论、核心原理、方法论"},
]


class ResearcherPool:

    def __init__(self, tracer=None, max_concurrency=3):
        self.tracer = tracer
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def run_all(self, state):
        if self.tracer:
            await self.tracer.phase_start(
                "ResearcherPool", "L1", "启动多视角并行研究",
                f"{len(FOCUS_CONFIG)} 视角: 技术|实践|理论",
            )
        tasks = [self.run_single(state, fc) for fc in FOCUS_CONFIG]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        successful = [r for r in results if not isinstance(r, Exception)]
        failed = len(results) - len(successful)
        if failed > 0 and self.tracer:
            await self.tracer.warning("ResearcherPool", "L1",
                                      f"{failed}/{len(results)} Researcher 失败")
        if self.tracer:
            await self.tracer.phase_end("ResearcherPool", "L1", "多视角研究完成", {
                "success": len(successful), "failed": failed,
                "entities": sum(len(r.get("entities", [])) for r in successful),
                "relations": sum(len(r.get("relations", [])) for r in successful),
            })
        if successful:
            return successful
        return [{"entities": [], "relations": [], "key_topics": [], "_focus": "fallback"}]

    async def run_single(self, state, focus):
        async with self.semaphore:
            prompt_template = load_prompt("researcher.md")
            prompt = prompt_template.format(
                focus=focus["label"],
                focus_desc=focus["prompt_extra"],
                memos_content="\n\n---\n\n".join(state["memos_content"]),
            )
            if self.tracer:
                await self.tracer.llm_request(
                    f"Researcher({focus['name']})", "L1",
                    f"LLM 请求 -- {focus['label']}", prompt[:600],
                    state["compilation_config"]["model"],
                    full_prompt_len=len(prompt),
                )
            response = await llm_service.chat_completion(
                state["_model_config"],
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"},
                timeout=30.0,
            )
            try:
                raw = response.choices[0].message.content.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1].rsplit("\n```", 1)[0]
                result = json.loads(raw)
            except (json.JSONDecodeError, KeyError, AttributeError):
                logger.error("Researcher(%s) JSON parse failed", focus["name"])
                result = {"entities": [], "relations": [], "key_topics": []}

            if self.tracer:
                preview = json.dumps(result, ensure_ascii=False)[:600]
                tokens = response.usage.total_tokens if response.usage else None
                await self.tracer.llm_response(
                    f"Researcher({focus['name']})", "L1",
                    f"LLM 响应 -- {focus['label']}", preview, tokens,
                )
            result["_focus"] = focus["name"]
            return result
