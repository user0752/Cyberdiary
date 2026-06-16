"""LangGraph multi-agent compilation orchestrator.

Graph topology (L0→L4):
    coordinator → researcher → integrator → writer
        → [reviewer_accuracy, reviewer_readability]  (parallel)
        → arbiter → _decide_next
            ├─ "revise" → editor → (back to reviewers)
            ├─ "link"   → linker → END
            └─ "finish" → END
"""

import logging
import time as _time_module
from typing import Dict

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.models.agent_state import CompilationState, AgentRole
from app.core.agent_error_handler import AgentErrorHandler
from app.services.compile_service import _safe_progress_update

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Ensure graph node logs are visible

# Registry of active tracers: {job_id: CompilationTracer}
_active_tracers: Dict[str, object] = {}
# Creation timestamps for TTL cleanup: {job_id: monotonic_seconds}
_tracer_timestamps: Dict[str, float] = {}

# TTL for stale tracer entries (1 hour)
_TRACER_TTL_SECONDS = 3600


def _gc_stale_tracers() -> int:
    """Remove tracer entries older than _TRACER_TTL_SECONDS.

    This is a synchronous function because _active_tracers is a simple
    dict accessed from the event loop (no async operations needed).

    Returns the number of entries purged.
    """
    now = _time_module.monotonic()
    stale_ids = [
        jid for jid, ts in _tracer_timestamps.items()
        if now - ts > _TRACER_TTL_SECONDS
    ]
    for jid in stale_ids:
        _active_tracers.pop(jid, None)
        _tracer_timestamps.pop(jid, None)
    if stale_ids:
        logger.debug("_gc_stale_tracers: purged %d stale entries", len(stale_ids))
    return len(stale_ids)

# Global error handler with per-agent circuit breakers
agent_error_handler = AgentErrorHandler()


class MultiAgentCompilationGraph:

    def __init__(self, config=None):
        self.config = config or {
            "model": "deepseek/deepseek-chat",
            "max_revisions": 3,
            "parallel_researchers": True,
            "parallel_reviewers": True,
            "pass_threshold": 8.0,
            "enable_human_review": False,
        }
        self.memory = MemorySaver()

    def build(self):
        wf = StateGraph(CompilationState)

        # Register nodes
        wf.add_node("coordinator", _coordinator_node)
        wf.add_node("researcher", _researcher_node)
        wf.add_node("integrator", _integrator_node)
        wf.add_node("writer", _writer_node)
        wf.add_node("reviewer_accuracy", _reviewer_accuracy_node)
        wf.add_node("reviewer_readability", _reviewer_readability_node)
        wf.add_node("arbiter", _arbiter_node)
        wf.add_node("editor", _editor_node)
        wf.add_node("linker", _linker_node)
        wf.add_node("human_review", _human_review_node)

        # L0 → L1
        wf.set_entry_point("coordinator")
        wf.add_edge("coordinator", "researcher")
        wf.add_edge("researcher", "integrator")
        wf.add_edge("integrator", "writer")

        # L2 → L3 (parallel fan-out to 2 reviewers)
        wf.add_edge("writer", "reviewer_accuracy")
        wf.add_edge("writer", "reviewer_readability")

        # L3 convergence
        wf.add_edge("reviewer_accuracy", "arbiter")
        wf.add_edge("reviewer_readability", "arbiter")

        # L3 → L4 routing (sole decision point)
        wf.add_conditional_edges("arbiter", self._decide_next, {
            "revise": "editor",
            "link": "linker",
            "human_review": "human_review",
            "finish": END,
        })

        # HITL gate → linker / editor / END
        wf.add_conditional_edges("human_review", self._decide_after_review, {
            "link": "linker",
            "revise": "editor",
            "finish": END,
        })

        # L4 → L3 (revision loop)
        wf.add_edge("editor", "reviewer_accuracy")
        wf.add_edge("editor", "reviewer_readability")

        # L4 → END
        wf.add_edge("linker", END)

        return wf.compile(checkpointer=self.memory)

    def _decide_next(self, state):
        """Unified routing decision — the ONLY place that controls flow."""
        if state.get("next_action") == "finish":
            return "finish"
        if state.get("review_passed", False):
            if (state.get("compilation_config", {}).get("enable_human_review")
                    and not state.get("human_reviewed", False)):
                return "human_review"
            return "link"
        max_rev = state.get("compilation_config", {}).get("max_revisions", 3)
        if state.get("revision_count", 0) > max_rev:
            return "link"
        return "revise"

    def _decide_after_review(self, state):
        """Route after human review decision."""
        if state.get("next_action") == "finish":
            return "finish"
        if state.get("review_passed", False):
            return "link"
        return "revise"


# ---------------------------------------------------------------------------
# LangGraph node wrappers — thin adapters between graph and agent functions
# ---------------------------------------------------------------------------

async def _coordinator_node(state):
    from app.agents.coordinator_agent import CoordinatorAgent
    job_id = state.get("job_id", "")
    tracer = _active_tracers.get(job_id)
    if tracer:
        await tracer.phase_start("Coordinator", "L0", "开始协调层分析")

    await _safe_progress_update(job_id, message="Coordinator: clustering memos...")
    logger.info("[Graph] Job %s: Coordinator starting", job_id)

    async def _run(s):
        agent = CoordinatorAgent()
        return await agent.run(s)

    state = await agent_error_handler.execute("coordinator", _run, state, fallback_value=state)

    if tracer:
        await tracer.phase_end("Coordinator", "L0", "协调层完成",
                               {"groups": len(state.get("memo_groups", []))})
    await _safe_progress_update(job_id, progress=15,
                                message="Coordinator complete, starting research...")
    logger.info("[Graph] Job %s: Coordinator done, %d groups",
                job_id, len(state.get("memo_groups", [])))
    return {"memo_groups": state.get("memo_groups", []),
            "compilation_log": state.get("compilation_log", []),
            "current_layer": state.get("current_layer", "coordinator")}


async def _researcher_node(state):
    from app.agents.researcher_agent import ResearcherPool
    job_id = state.get("job_id", "")
    tracer = _active_tracers.get(job_id)
    pool = ResearcherPool(tracer=tracer)

    await _safe_progress_update(job_id, message="Researcher: gathering facts & references...")
    logger.info("[Graph] Job %s: Researcher starting (3 perspectives)", job_id)

    async def _run(s):
        s["research_results"] = await pool.run_all(s)
        return s

    state = await agent_error_handler.execute("researcher", _run, state, fallback_value=state)
    state["current_agent"] = AgentRole.INTEGRATOR
    await _safe_progress_update(job_id, progress=30,
                                message="Research complete, integrating...")
    logger.info("[Graph] Job %s: Researcher done, %d results",
                job_id, len(state.get("research_results", [])))
    return {"research_results": state.get("research_results", []),
            "current_agent": state["current_agent"]}


async def _integrator_node(state):
    from app.agents.integrator_agent import integrator_agent
    job_id = state.get("job_id", "")
    tracer = _active_tracers.get(job_id)
    if tracer:
        await tracer.phase_start("Integrator", "L1", "开始知识整合")

    await _safe_progress_update(job_id, message="Integrator: synthesizing knowledge graph...")
    logger.info("[Graph] Job %s: Integrator starting", job_id)

    state = await agent_error_handler.execute("integrator", integrator_agent, state, fallback_value=state)

    if tracer:
        await tracer.phase_end("Integrator", "L1", "知识整合完成",
                               {"entities": len(state.get("integrated_knowledge", {}).get("entities", []))})
    await _safe_progress_update(job_id, progress=45,
                                message="Knowledge integrated, writing wiki...")
    logger.info("[Graph] Job %s: Integrator done", job_id)
    return {"integrated_knowledge": state.get("integrated_knowledge", {})}


async def _writer_node(state):
    from app.agents.writer_agent import writer_agent
    job_id = state.get("job_id", "")
    tracer = _active_tracers.get(job_id)
    if tracer:
        await tracer.phase_start("Writer", "L2", "开始撰写 Wiki")

    await _safe_progress_update(job_id, message="Writer: drafting wiki pages...")
    logger.info("[Graph] Job %s: Writer starting", job_id)

    state = await agent_error_handler.execute("writer", writer_agent, state, fallback_value=state)

    if tracer:
        await tracer.phase_end("Writer", "L2", "Wiki 初稿完成",
                               {"chars": len(state.get("wiki_draft", ""))})
    await _safe_progress_update(job_id, progress=60,
                                message="Wiki drafted, reviewing...")
    logger.info("[Graph] Job %s: Writer done, draft=%d chars",
                job_id, len(state.get("wiki_draft", "")))
    return {"wiki_draft": state.get("wiki_draft", "")}


async def _reviewer_accuracy_node(state):
    """Accuracy reviewer — returns ONLY the new review (delta) for the
    operator.add reducer to merge correctly in parallel fan-out."""
    from app.agents.reviewer_agent import reviewer_accuracy_agent
    job_id = state.get("job_id", "")
    tracer = _active_tracers.get(job_id)
    if tracer:
        await tracer.phase_start("Reviewer(accuracy)", "L3", "准确性评审中")

    await _safe_progress_update(job_id, message="Reviewer: checking factual accuracy...")
    logger.info("[Graph] Job %s: Reviewer(accuracy) starting", job_id)

    # [FIX #3] Track how many reviews exist BEFORE this agent runs.
    # The agent appends to state["reviews"] in place. We must return
    # only the delta (new review) because the `reviews` field uses
    # Annotated[List[Dict], operator.add] — returning the full list
    # would cause duplicates when the reducer adds old+new together.
    old_review_count = len(state.get("reviews", []))

    state = await agent_error_handler.execute(
        "reviewer_accuracy", reviewer_accuracy_agent, state, fallback_value=state,
    )

    new_reviews = state.get("reviews", [])[old_review_count:]

    if tracer:
        await tracer.phase_end("Reviewer(accuracy)", "L3", "准确性评审完成")
    logger.info("[Graph] Job %s: Reviewer(accuracy) done, produced %d new reviews",
                job_id, len(new_reviews))
    return {"reviews": new_reviews}


async def _reviewer_readability_node(state):
    """Readability reviewer — returns ONLY the new review (delta)."""
    from app.agents.reviewer_agent import reviewer_readability_agent
    job_id = state.get("job_id", "")
    tracer = _active_tracers.get(job_id)
    if tracer:
        await tracer.phase_start("Reviewer(readability)", "L3", "可读性评审中")

    await _safe_progress_update(job_id, message="Reviewer: checking readability & style...")
    logger.info("[Graph] Job %s: Reviewer(readability) starting", job_id)

    # [FIX #3] Same delta-pattern as accuracy reviewer
    old_review_count = len(state.get("reviews", []))

    state = await agent_error_handler.execute(
        "reviewer_readability", reviewer_readability_agent, state, fallback_value=state,
    )

    new_reviews = state.get("reviews", [])[old_review_count:]

    if tracer:
        await tracer.phase_end("Reviewer(readability)", "L3", "可读性评审完成")
    logger.info("[Graph] Job %s: Reviewer(readability) done, produced %d new reviews",
                job_id, len(new_reviews))
    return {"reviews": new_reviews}


async def _arbiter_node(state):
    from app.agents.arbiter_agent import arbiter_agent
    job_id = state.get("job_id", "")
    tracer = _active_tracers.get(job_id)
    if tracer:
        await tracer.phase_start("Arbiter", "L3", "仲裁决策中")

    await _safe_progress_update(job_id, message="Arbiter: evaluating review results...")
    logger.info("[Graph] Job %s: Arbiter starting (reviews=%d)",
                job_id, len(state.get("reviews", [])))

    state = await agent_error_handler.execute("arbiter", arbiter_agent, state, fallback_value=state)

    final_score = state.get("final_score", 0)
    review_passed = state.get("review_passed", False)
    if tracer:
        await tracer.phase_end("Arbiter", "L3", "仲裁完成",
                               {"final_score": final_score,
                                "passed": review_passed})
    await _safe_progress_update(job_id, progress=70,
                                message=f"Arbitration: score={final_score}, {'PASS' if review_passed else 'REVISE'}")
    logger.info("[Graph] Job %s: Arbiter done, score=%.1f, passed=%s",
                job_id, final_score, review_passed)
    return {"final_score": final_score,
            "review_passed": review_passed,
            "arbitration_result": state.get("arbitration_result", {})}


async def _editor_node(state):
    from app.agents.editor_agent import editor_agent
    job_id = state.get("job_id", "")
    rev = state.get("revision_count", 0) + 1
    max_rev = state.get("compilation_config", {}).get("max_revisions", 3)
    tracer = _active_tracers.get(job_id)
    if tracer:
        await tracer.phase_start("Editor", "L4", f"第{rev}次修订")

    await _safe_progress_update(job_id,
                                message=f"Editor: revision {rev}/{max_rev}...")
    logger.info("[Graph] Job %s: Editor starting (revision %d/%d)",
                job_id, rev, max_rev)

    state = await agent_error_handler.execute("editor", editor_agent, state, fallback_value=state)

    if tracer:
        await tracer.phase_end("Editor", "L4", "修订完成",
                               {"revision": state.get("revision_count", 0)})
    await _safe_progress_update(job_id, progress=75,
                                message=f"Revision {rev}/{max_rev}, re-reviewing...")
    logger.info("[Graph] Job %s: Editor done, revision_count=%d",
                job_id, state.get("revision_count", 0))
    return {"wiki_revised": state.get("wiki_revised", ""),
            "revision_count": state.get("revision_count", 0),
            "review_passed": state.get("review_passed", False)}


async def _linker_node(state):
    from app.agents.linker_agent import linker_agent
    job_id = state.get("job_id", "")
    tracer = _active_tracers.get(job_id)
    if tracer:
        await tracer.phase_start("Linker", "L4", "语义链接发现中")

    await _safe_progress_update(job_id, message="Linker: discovering semantic connections...")
    logger.info("[Graph] Job %s: Linker starting", job_id)

    state = await agent_error_handler.execute("linker", linker_agent, state, fallback_value=state)

    if tracer:
        await tracer.phase_end("Linker", "L4", "链接发现完成",
                               {"links": len(state.get("suggested_links", []))})
    await _safe_progress_update(job_id, progress=78,
                                message="Semantic links discovered, finalizing...")
    logger.info("[Graph] Job %s: Linker done, %d links",
                job_id, len(state.get("suggested_links", [])))
    return {"suggested_links": state.get("suggested_links", [])}


async def _human_review_node(state):
    """HITL gate — pauses compilation until human provides a decision."""
    from app.services.human_review_manager import human_review_manager
    from app.services.compile_service import _compile_progress

    job_id = state.get("job_id", "")
    enable_hr = state.get("compilation_config", {}).get("enable_human_review", False)

    # Safety: if HITL is disabled, auto-approve immediately without blocking
    if not enable_hr:
        logger.info("[Graph] Job %s: HITL disabled in config, auto-approving", job_id)
        state["human_reviewed"] = True
        state["review_passed"] = True
        state["next_action"] = "continue"
        await _safe_progress_update(job_id, message="HITL skipped (disabled), linking...")
        return {
            "human_reviewed": True,
            "review_passed": True,
            "next_action": "continue",
        }

    tracer = _active_tracers.get(job_id)
    if tracer:
        await tracer.phase_start("HumanReview", "HITL", "等待人工审核 (60s timeout)")

    review_data = {
        "wiki_draft": state.get("wiki_revised", state.get("wiki_draft", "")),
        "final_score": state.get("final_score", 0),
        "reviews": state.get("reviews", []),
    }

    logger.info("[Graph] Job %s: HITL waiting for human decision (60s timeout)...", job_id)
    try:
        result = await human_review_manager.create_review_task(job_id, review_data)
    except Exception:
        logger.exception("Human review creation failed, auto-approving")
        result = {"decision": "approve"}

    # Store task_id in progress so SSE polling can relay it to frontend
    progress = _compile_progress.get(job_id, {})
    progress["status"] = "needs_review"
    progress["progress"] = 75
    progress["message"] = "Human review required"
    progress["task_id"] = result.get("task_id", "")
    progress["final_score"] = review_data["final_score"]
    progress["review_feedback"] = [
        r.get("feedback", "") for r in review_data["reviews"]
    ]
    progress["wiki_draft"] = review_data["wiki_draft"]

    state["human_reviewed"] = True
    decision = result.get("decision", "approve")

    if decision == "approve":
        state["review_passed"] = True
        state["next_action"] = "continue"
    elif decision == "revise":
        state["review_passed"] = False
        state["next_action"] = "revise"
        if result.get("edited_wiki"):
            state["wiki_revised"] = result["edited_wiki"]
    else:
        state["next_action"] = "finish"

    if tracer:
        await tracer.phase_end("HumanReview", "HITL", f"审核完成: {decision}",
                               {"decision": decision})

    await _safe_progress_update(job_id, status="running", progress=78,
                                message=f"Review decision: {decision}")

    return {
        "human_reviewed": True,
        "review_passed": state.get("review_passed", False),
        "next_action": state.get("next_action", "continue"),
        "wiki_revised": state.get("wiki_revised", ""),
    }
