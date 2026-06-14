"""Human-in-the-Loop review manager — pause/resume compilation for human decisions."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import async_session
from app.models.multi_agent import HumanReviewTask

logger = logging.getLogger(__name__)


class HumanReviewManager:
    """Manages human review tasks with Event-based pause/resume and 5-min timeout."""

    def __init__(self):
        self._events: dict[str, asyncio.Event] = {}
        self._results: dict[str, dict] = {}
        self._sse_callbacks: dict[str, callable] = {}
        self.timeout = 60  # 1 minute — sufficient for manual approval during testing

    def set_sse_callback(self, job_id: str, callback):
        self._sse_callbacks[job_id] = callback

    async def create_review_task(self, job_id: str, review_data: dict) -> dict:
        """Create a review task, notify frontend, and wait for human decision.

        Blocks until the user submits a decision or the timeout expires.
        Returns the decision result dict.
        """
        task_id = str(uuid.uuid4())

        async with async_session() as db:
            task = HumanReviewTask(
                id=task_id,
                job_id=job_id,
                wiki_content=review_data.get("wiki_draft", ""),
                final_score=review_data.get("final_score", 0),
                reviews=json.dumps(review_data.get("reviews", []), ensure_ascii=False),
                status="pending",
            )
            db.add(task)
            await db.commit()

        event = asyncio.Event()
        self._events[task_id] = event

        # Notify frontend via SSE
        sse_cb = self._sse_callbacks.get(job_id)
        if sse_cb:
            try:
                await sse_cb(json.dumps({
                    "event": "needs_review",
                    "data": {
                        "task_id": task_id,
                        "final_score": review_data.get("final_score", 0),
                        "review_feedback": [
                            r.get("feedback", "") for r in review_data.get("reviews", [])
                        ],
                        "wiki_draft": review_data.get("wiki_draft", ""),
                        "message": "Human review required",
                    },
                }, ensure_ascii=False))
            except Exception:
                logger.exception("SSE notification failed for job %s", job_id)

        # Wait for decision with timeout
        try:
            await asyncio.wait_for(event.wait(), timeout=self.timeout)
            result = self._results.pop(task_id, {"decision": "approve"})
        except asyncio.TimeoutError:
            logger.warning("Review task %s timed out, auto-approving", task_id)
            result = {"decision": "approve", "edited_wiki": None}
        finally:
            self._events.pop(task_id, None)
            self._sse_callbacks.pop(job_id, None)

        # Update DB
        async with async_session() as db:
            t = await db.get(HumanReviewTask, task_id)
            if t:
                t.status = "resolved"
                t.decision = result.get("decision", "approve")
                if result.get("edited_wiki"):
                    t.edited_wiki = result["edited_wiki"]
                t.resolved_at = datetime.now(timezone.utc)
                await db.commit()

        result["task_id"] = task_id
        return result

    async def submit_decision(
        self, task_id: str, decision: str, edited_wiki=None,
    ) -> dict:
        """Submit human review decision. Resumes the paused compilation."""
        result = {
            "decision": decision,
            "edited_wiki": edited_wiki,
            "review_passed": decision == "approve",
            "next_action": (
                "link" if decision == "approve"
                else "revise" if decision == "revise"
                else "finish"
            ),
        }
        self._results[task_id] = result

        event = self._events.get(task_id)
        if event:
            event.set()
        else:
            logger.warning("No waiting event for task %s", task_id)

        async with async_session() as db:
            t = await db.get(HumanReviewTask, task_id)
            if t:
                t.status = "resolved"
                t.decision = decision
                if edited_wiki:
                    t.edited_wiki = edited_wiki
                t.resolved_at = datetime.now(timezone.utc)
                await db.commit()

        return result

    def get_pending_task_ids(self) -> list[str]:
        return list(self._events.keys())


human_review_manager = HumanReviewManager()
