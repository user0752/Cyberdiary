"""Coordinator Agent — multi-agent system entry and exit point."""

import asyncio
import logging

logger = logging.getLogger(__name__)

# Limit concurrent embedding API calls to avoid provider rate limits
_EMBED_CONCURRENCY = 5


class CoordinatorAgent:

    async def run(self, state):
        memo_ids = state["memo_ids"]
        embedding_model = state["compilation_config"].get("embedding_model", "")

        if embedding_model and len(memo_ids) >= 3:
            try:
                state["memo_groups"] = await self.cluster_memos(
                    memo_ids, embedding_model,
                    n_clusters=min(3, len(memo_ids) // 2 + 1),
                )
            except Exception:
                logger.exception("Clustering failed, falling back to single group")
                state["memo_groups"] = [memo_ids]
        else:
            state["memo_groups"] = [memo_ids]

        state.setdefault("compilation_log", []).append({
            "agent": "coordinator", "action": "clustered",
            "groups": [{"id": i, "size": len(g)} for i, g in enumerate(state["memo_groups"])],
        })
        state["current_layer"] = "research"
        return state

    async def cluster_memos(self, memo_ids, embedding_model, n_clusters):
        if n_clusters <= 1:
            return [memo_ids]
        embeddings = await self._batch_embed(memo_ids, embedding_model)
        from sklearn.cluster import KMeans
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = kmeans.fit_predict(embeddings)
        groups = [[] for _ in range(n_clusters)]
        for i, label in enumerate(labels):
            groups[label].append(memo_ids[i])
        return [g for g in groups if g]

    async def _batch_embed(self, memo_ids, embedding_model):
        from app.core.database import async_session
        from sqlalchemy import select
        from app.models.memo import Memo
        from litellm import aembedding
        import os

        async with async_session() as db:
            result = await db.execute(select(Memo.content).where(Memo.id.in_(memo_ids)))
            contents = [row[0] for row in result.all()]

        sem = asyncio.Semaphore(_EMBED_CONCURRENCY)

        async def embed_one(content):
            async with sem:
                resp = await aembedding(
                    model=embedding_model, input=content[:8000],
                    api_key=os.getenv("EMBEDDING_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or "",
                )
                return resp.data[0]["embedding"]

        return await asyncio.gather(*[embed_one(c) for c in contents])
