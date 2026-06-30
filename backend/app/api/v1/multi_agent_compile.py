"""Multi-agent compile API — trigger, stream, trace, human review, evaluation."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.database import async_session
from app.models.compile_job import CompileJob
from app.models.memo import Memo
from app.models.multi_agent import HumanReviewTask
from app.models.agent_state import CompilationState, AgentRole
from app.schemas.compile import MultiAgentCompileRequest, HumanReviewRequest
from app.services import llm_service as _llm_svc
from app.services.progress_tracker import safe_progress_update
from app.core.progress_store import init_progress, get_progress, update_progress
from app.utils.sanitize import sanitize_error_message


async def _get_first_model_config(db) -> dict | None:
    """Get the first available model config from the database."""
    import json
    from sqlalchemy import select
    from app.models.settings import Setting

    result = await db.execute(select(Setting).where(Setting.key == "models"))
    row = result.scalar_one_or_none()
    if not row:
        return None
    try:
        models = json.loads(row.value)
        if models:
            return models[0]
    except (json.JSONDecodeError, TypeError):
        pass
    return None


async def _evaluate_page(slug: str, content: str, source_texts: list[str]):
    """Background task: evaluate wiki quality after compilation."""
    try:
        from app.services.evaluation_service import evaluate_wiki_async
        await evaluate_wiki_async(slug, content, source_texts)
    except Exception:
        logger.exception("Background wiki evaluation failed for slug=%s", slug)


router = APIRouter(
    prefix="/compile",
    tags=["compile-multi-agent"],
    dependencies=[Depends(get_current_user)],
)
logger = logging.getLogger(__name__)
# Global timeout for the entire multi-agent pipeline (seconds)
PIPELINE_TIMEOUT = 600  # 10 minutes — enough for all agents even with some timeouts


# ---------------------------------------------------------------------------
# POST /compile/multi-agent
# ---------------------------------------------------------------------------

@router.post("/multi-agent")
async def trigger_multi_agent_compile(
    body: MultiAgentCompileRequest,
    db: AsyncSession = Depends(get_db),
):
    job = CompileJob(
        id=str(uuid.uuid4()),
        status="pending",
        compile_type="multi_agent",
        memo_ids=json.dumps(body.memo_ids, ensure_ascii=False),
        model_id=body.config.get("model", "") if body.config else "",
    )
    db.add(job)
    await db.commit()

    await init_progress(
        job.id,
        status="pending", progress=0, message="Queued...",
    )

    task = asyncio.create_task(
        _run_multi_agent_compile(
            job_id=job.id,
            memo_ids=body.memo_ids,
            config=body.config or {},
        )
    )

    # Always log uncaught exceptions from background tasks
    def _log_task_exception(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            logger.exception("Background multi-agent compile task failed [job_id=%s]: %s", job.id, exc, exc_info=exc)

    task.add_done_callback(_log_task_exception)

    try:
        from app.main import app as _app
        if hasattr(_app.state, "background_tasks"):
            _app.state.background_tasks.add(task)
            task.add_done_callback(_app.state.background_tasks.discard)
    except Exception:
        pass

    return {
        "code": 0,
        "message": "ok",
        "data": {
            "job_id": job.id,
            "status": "pending",
            "estimated_time": "~2min",
        },
    }


# ---------------------------------------------------------------------------
# GET /compile/jobs/{job_id}/stream  (SSE)
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}/multi-stream")
async def stream_compile_progress(job_id: str, request: Request):
    from app.services.multi_agent_graph import tracer_registry

    async def event_generator():
        trace_queue: asyncio.Queue = asyncio.Queue()

        # Retry tracer registration — the tracer may not be ready yet
        # when the SSE stream connects (race condition fix)
        tracer_registered = False
        for _ in range(10):
            tracer = tracer_registry.get(job_id)
            if tracer:
                tracer.set_sse_callback(
                    lambda msg: asyncio.ensure_future(trace_queue.put(msg))
                )
                tracer_registered = True
                break
            await asyncio.sleep(0.2)

        if not tracer_registered:
            logger.debug("SSE stream for job %s started before tracer was ready", job_id)

        while True:
            if await request.is_disconnected():
                break

            # Emit any pending trace events
            try:
                msg = trace_queue.get_nowait()
                yield f"data: {msg}\n\n"
                continue
            except asyncio.QueueEmpty:
                pass

            progress = await get_progress(job_id)
            if not progress:
                yield f"data: {json.dumps({'event': 'error', 'data': {'message': 'Job not found'}})}\n\n"
                break

            status = progress.get("status")
            if status == "completed":
                yield f"data: {json.dumps({'event': 'complete', 'data': progress}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                break
            elif status == "failed":
                yield f"data: {json.dumps({'event': 'error', 'data': progress}, ensure_ascii=False)}\n\n"
                break
            elif status == "needs_review":
                yield f"data: {json.dumps({'event': 'needs_review', 'data': progress}, ensure_ascii=False)}\n\n"
                # Don't break — keep polling until review is resolved
            else:
                yield f"data: {json.dumps({'event': 'progress', 'data': progress}, ensure_ascii=False)}\n\n"

            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# GET /compile/jobs/{job_id}/trace
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}/trace")
async def get_compile_trace(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await db.get(CompileJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.status not in ("done", "failed"):
        raise HTTPException(400, "Still in progress")
    try:
        trace = json.loads(job.compilation_log or "[]")
    except json.JSONDecodeError:
        trace = []
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "job_id": job_id,
            "status": job.status,
            "trace": trace,
            "total_events": len(trace),
        },
    }


# ---------------------------------------------------------------------------
# POST /compile/human-review/{task_id}/submit
# ---------------------------------------------------------------------------

@router.post("/human-review/{task_id}/submit")
async def submit_human_review(
    task_id: str,
    body: HumanReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    from app.services.human_review_manager import human_review_manager
    result = await human_review_manager.submit_decision(
        task_id, body.decision, body.edited_wiki
    )
    return {"code": 0, "message": "ok", "data": result}


# ---------------------------------------------------------------------------
# Background compile task
# ---------------------------------------------------------------------------

async def _load_ma_job_and_model(
    job_id: str, memo_ids: list[str], config: dict,
) -> tuple[list[Memo], list[str], dict] | None:
    """Load job, memos, and resolve model config for multi-agent compile.

    Returns (memos, memo_contents, model_config) or None on failure
    (progress already updated with the error).
    """
    async with async_session() as db:
        job = (await db.execute(
            select(CompileJob).where(CompileJob.id == job_id)
        )).scalar_one_or_none()
        if not job:
            logger.error("[MA-Compile] Job %s: job not found in DB", job_id)
            return None
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()

        result = await db.execute(select(Memo).where(Memo.id.in_(memo_ids)))
        memos = list(result.scalars().all())
        if not memos:
            await safe_progress_update(job_id, status="failed", message="No memos found")
            logger.error("[MA-Compile] Job %s: no memos found for ids %s", job_id, memo_ids)
            return None
        memo_contents = [m.content for m in memos]
        logger.info("[MA-Compile] Job %s: loaded %d memos", job_id, len(memos))

        # Build model config — prefer explicit model, then job model, then first DB model
        model_key = config.get("model", "")
        model_config = None
        if model_key:
            model_config = await _llm_svc.get_model_config_from_db(db, model_key)
        if not model_config and job.model_id:
            model_config = await _llm_svc.get_model_config_from_db(db, job.model_id)
        if not model_config:
            model_config = await _get_first_model_config(db)
        if not model_config:
            await safe_progress_update(
                job_id, status="failed",
                message="No AI model configured. Please add a model in Settings first.",
            )
            logger.error("[MA-Compile] Job %s: no model configured", job_id)
            return None

        logger.info("[MA-Compile] Job %s: using model provider=%s, name=%s",
                    job_id, model_config.get("provider", "?"),
                    model_config.get("model_name", "?"))

    return memos, memo_contents, model_config


def _build_ma_initial_state(
    job_id: str, memo_ids: list[str], memo_contents: list[str],
    model_config: dict, config: dict,
) -> CompilationState:
    """Build the initial LangGraph state for multi-agent compilation."""
    default_config = {
        "model": "deepseek/deepseek-chat",
        "max_revisions": 3,
        "parallel_researchers": 3,
        "pass_threshold": 8.0,
        "fallback_model": "ollama/qwen2.5:7b",
        "enable_human_review": False,
    }
    default_config.update(config)

    return {
        "memo_ids": memo_ids,
        "memos_content": memo_contents,
        "compilation_config": default_config,
        "_model_config": model_config,
        "job_id": job_id,
        "memo_groups": [],
        "group_results": [],
        "research_results": [],
        "integrated_knowledge": {},
        "wiki_draft": "",
        "wiki_structure": {},
        "reviews": [],
        "arbitration_result": {},
        "final_score": 0.0,
        "review_passed": False,
        "revision_count": 0,
        "wiki_revised": "",
        "suggested_links": [],
        "final_wiki": "",
        "compilation_log": [],
        "current_layer": "coordinator",
        "current_agent": AgentRole.COORDINATOR,
        "next_action": "continue",
        "human_reviewed": False,
    }, default_config


async def _run_ma_graph(
    job_id: str, initial_state: CompilationState, default_config: dict,
) -> dict | None:
    """Run the LangGraph pipeline with timeout. Returns final_state or None on failure."""
    from app.services.multi_agent_graph import MultiAgentCompilationGraph, tracer_registry
    from app.core.compilation_tracer import CompilationTracer

    # Create tracer BEFORE starting the graph so the SSE stream can register
    tracer_registry.gc_stale()
    tracer = CompilationTracer(job_id=job_id)
    tracer_registry.register(job_id, tracer)

    # Check model connectivity
    await safe_progress_update(job_id, progress=5, message="Checking model connectivity...")
    model_config = initial_state.get("_model_config", {})
    try:
        await _llm_svc.chat_completion(
            model_config, [{"role": "user", "content": "ping"}],
            max_tokens=1, timeout=10.0,
        )
    except Exception as ping_err:
        logger.error("[MA-Compile] Job %s: model connectivity FAILED: %s", job_id, ping_err)
        # Sanitize — provider exceptions may leak endpoint/api-key fragments.
        from app.utils.sanitize import sanitize_error_message
        await safe_progress_update(
            job_id, status="failed",
            message=f"Model unreachable: {sanitize_error_message(str(ping_err))}",
        )
        tracer_registry.pop(job_id)
        return None

    await safe_progress_update(job_id, progress=10, message="Launching multi-agent pipeline...")
    logger.info("[MA-Compile] Job %s: building LangGraph pipeline...", job_id)

    graph_builder = MultiAgentCompilationGraph(default_config)
    graph = graph_builder.build()
    run_config = {"configurable": {"thread_id": job_id}}

    logger.info("[MA-Compile] Job %s: invoking graph.ainvoke (timeout=%ds)...",
                job_id, PIPELINE_TIMEOUT)
    try:
        final_state = await asyncio.wait_for(
            graph.ainvoke(initial_state, run_config),
            timeout=PIPELINE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.error("[MA-Compile] Job %s: pipeline timed out after %ds",
                     job_id, PIPELINE_TIMEOUT)
        await safe_progress_update(
            job_id, status="failed",
            message=f"Pipeline timed out after {PIPELINE_TIMEOUT}s. "
                    "This may be caused by slow LLM responses or network issues.",
        )
        return None
    finally:
        tracer_registry.pop(job_id)

    logger.info("[MA-Compile] Job %s: graph completed. final_score=%.1f, review_passed=%s",
                job_id, final_state.get("final_score", 0),
                final_state.get("review_passed", False))
    return final_state


async def _save_ma_results(
    job_id: str, final_state: dict, memo_ids: list[str],
    memos: list[Memo], memo_contents: list[str],
) -> None:
    """Save multi-agent compile results: wiki pages, links, job status."""
    from app.services import compile_service

    await safe_progress_update(job_id, progress=80, message="Saving results...")

    async with async_session() as db:
        wiki_content = final_state.get("wiki_revised") or final_state.get("wiki_draft", "")
        pages = compile_service.parse_compile_output(wiki_content, memo_ids)

        await compile_service.save_compile_results(
            db, pages, memo_ids,
            semantic_links=final_state.get("suggested_links", []),
        )

        job = (await db.execute(
            select(CompileJob).where(CompileJob.id == job_id)
        )).scalar_one_or_none()
        if job:
            job.status = "done"
            job.result_summary = f"Compiled {len(memos)} memos into {len(pages)} pages"
            job.finished_at = datetime.now(timezone.utc)
            job.final_score = final_state.get("final_score", 0)
            job.compilation_log = json.dumps(
                final_state.get("compilation_log", []), ensure_ascii=False
            )
            job.integrated_knowledge = json.dumps(
                final_state.get("integrated_knowledge", {}), ensure_ascii=False
            )
        await db.commit()

        await safe_progress_update(
            job_id, status="completed", progress=100,
            message=f"Compiled {len(memos)} memos into {len(pages)} pages",
            final_score=final_state.get("final_score", 0),
            wiki_draft=final_state.get("wiki_draft", ""),
            wiki_revised=final_state.get("wiki_revised", ""),
            suggested_links=final_state.get("suggested_links", []),
        )

        logger.info("[MA-Compile] Job %s: completed successfully — %d memos → %d pages, score=%.1f",
                    job_id, len(memos), len(pages), final_state.get("final_score", 0))

        # Trigger async quality evaluation (non-blocking)
        for page_data in pages:
            asyncio.create_task(
                _evaluate_page(page_data["slug"], page_data["content"], memo_contents)
            )


async def _run_multi_agent_compile(
    job_id: str,
    memo_ids: list[str],
    config: dict,
):
    """Execute the full multi-agent compilation pipeline."""
    await safe_progress_update(job_id, status="running", progress=0, message="Starting...")
    logger.info("[MA-Compile] Job %s started: %d memos, config=%s",
                job_id, len(memo_ids), {k: v for k, v in config.items() if k != "model"})

    try:
        # --- Load memos & model config ---
        loaded = await _load_ma_job_and_model(job_id, memo_ids, config)
        if loaded is None:
            return
        memos, memo_contents, model_config = loaded

        # --- Build initial state ---
        initial_state, default_config = _build_ma_initial_state(
            job_id, memo_ids, memo_contents, model_config, config,
        )

        # --- Run LangGraph pipeline ---
        final_state = await _run_ma_graph(job_id, initial_state, default_config)
        if final_state is None:
            return

        # --- Save results ---
        await _save_ma_results(job_id, final_state, memo_ids, memos, memo_contents)

    except Exception as e:
        raw_msg = str(e)
        logger.exception("[MA-Compile] Job %s FAILED: %s", job_id, raw_msg)
        safe_msg = sanitize_error_message(raw_msg)
        await safe_progress_update(job_id, status="failed", message=f"Error: {safe_msg}")
        from app.services.compile_service import record_compile_failure
        await record_compile_failure(job_id, safe_msg)
