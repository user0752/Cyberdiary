"""Multi-agent compile API — trigger, stream, trace, human review, evaluation."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.database import async_session
from app.models.compile_job import CompileJob
from app.models.memo import Memo
from app.models.multi_agent import HumanReviewTask, SemanticLink
from app.models.agent_state import CompilationState, AgentRole
from app.schemas.compile import MultiAgentCompileRequest, HumanReviewRequest
from app.services import llm_service as _llm_svc
from app.services.compile_service import _compile_progress, _safe_progress_update


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
        pass


router = APIRouter(prefix="/compile", tags=["compile-multi-agent"])
logger = logging.getLogger(__name__)

# [DIAGNOSTIC] Force our logger messages to be visible regardless of
# the global logging configuration. Python's default level is WARNING
# and no logging.basicConfig is called anywhere in this project, so
# all logger.info() calls are silently discarded.
logging.getLogger().setLevel(logging.INFO)

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

    _compile_progress[job.id] = {
        "status": "pending",
        "progress": 0,
        "message": "Queued...",
    }

    task = asyncio.create_task(
        _run_multi_agent_compile(
            job_id=job.id,
            memo_ids=body.memo_ids,
            config=body.config or {},
        )
    )

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
    from app.services.multi_agent_graph import _active_tracers

    async def event_generator():
        trace_queue: asyncio.Queue = asyncio.Queue()

        # Retry tracer registration — the tracer may not be ready yet
        # when the SSE stream connects (race condition fix)
        tracer_registered = False
        for _ in range(10):
            tracer = _active_tracers.get(job_id)
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

            progress = _compile_progress.get(job_id)
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

async def _run_multi_agent_compile(
    job_id: str,
    memo_ids: list[str],
    config: dict,
):
    """Execute the full multi-agent compilation pipeline."""
    from app.services.multi_agent_graph import MultiAgentCompilationGraph, _active_tracers
    from app.core.compilation_tracer import CompilationTracer
    from app.services import wiki_service, compile_service

    # [FIX #5] Explicitly set status to "running" — the setdefault only
    # creates the dict if absent; the API endpoint already set it to "pending".
    _safe_progress_update(job_id, status="running", progress=0, message="Starting...")
    logger.info("[MA-Compile] Job %s started: %d memos, config=%s",
                job_id, len(memo_ids), {k: v for k, v in config.items() if k != "model"})

    try:
        # --- Load memos & build config ---
        logger.info("[MA-Compile] Job %s: loading memos and model config...", job_id)
        async with async_session() as db:
            job = (await db.execute(
                select(CompileJob).where(CompileJob.id == job_id)
            )).scalar_one_or_none()
            if not job:
                logger.error("[MA-Compile] Job %s: job not found in DB", job_id)
                return
            job.status = "running"
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

            result = await db.execute(select(Memo).where(Memo.id.in_(memo_ids)))
            memos = list(result.scalars().all())
            if not memos:
                _safe_progress_update(job_id, status="failed", message="No memos found")
                logger.error("[MA-Compile] Job %s: no memos found for ids %s", job_id, memo_ids)
                return
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
                # Fallback: grab first available model from DB
                model_config = await _get_first_model_config(db)
            if not model_config:
                _safe_progress_update(
                    job_id, status="failed",
                    message="No AI model configured. Please add a model in Settings first.",
                )
                logger.error("[MA-Compile] Job %s: no model configured", job_id)
                return

            logger.info("[MA-Compile] Job %s: using model provider=%s, name=%s",
                        job_id, model_config.get("provider", "?"),
                        model_config.get("model_name", "?"))

        # --- Build initial state ---
        default_config = {
            "model": "deepseek/deepseek-chat",
            "max_revisions": 3,
            "parallel_researchers": 3,
            "pass_threshold": 8.0,
            "fallback_model": "ollama/qwen2.5:7b",
            "enable_human_review": False,
        }
        default_config.update(config)

        # [FIX #4] Create tracer BEFORE starting the graph so the SSE
        # stream can register its callback when it connects.
        tracer = CompilationTracer(job_id=job_id)
        _active_tracers[job_id] = tracer

        # [FIX #6] Include human_reviewed in initial state
        initial_state: CompilationState = {
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
        }

        # --- Run LangGraph pipeline ---
        _safe_progress_update(job_id, progress=5, message="Checking model connectivity...")
        logger.info("[MA-Compile] Job %s: checking model connectivity...", job_id)
        try:
            ping_messages = [{"role": "user", "content": "ping"}]
            await _llm_svc.chat_completion(
                model_config, ping_messages,
                max_tokens=1, timeout=10.0,
            )
            logger.info("[MA-Compile] Job %s: model connectivity OK", job_id)
        except Exception as ping_err:
            logger.error("[MA-Compile] Job %s: model connectivity FAILED: %s", job_id, ping_err)
            _safe_progress_update(
                job_id, status="failed",
                message=f"Model unreachable: {ping_err}",
            )
            return

        _safe_progress_update(job_id, progress=10, message="Launching multi-agent pipeline...")
        logger.info("[MA-Compile] Job %s: building LangGraph pipeline...", job_id)

        graph_builder = MultiAgentCompilationGraph(default_config)
        graph = graph_builder.build()
        run_config = {"configurable": {"thread_id": job_id}}

        # [FIX #1] Wrap graph.ainvoke with a global timeout so the
        # pipeline can never hang indefinitely.
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
            _safe_progress_update(
                job_id, status="failed",
                message=f"Pipeline timed out after {PIPELINE_TIMEOUT}s. "
                        "This may be caused by slow LLM responses or network issues.",
            )
            return
        finally:
            _active_tracers.pop(job_id, None)

        logger.info("[MA-Compile] Job %s: graph completed. final_score=%.1f, review_passed=%s",
                    job_id, final_state.get("final_score", 0),
                    final_state.get("review_passed", False))

        # --- Save results ---
        _safe_progress_update(job_id, progress=80, message="Saving results...")

        async with async_session() as db:
            wiki_content = final_state.get("wiki_revised") or final_state.get("wiki_draft", "")
            pages = compile_service._parse_compile_output(wiki_content, memo_ids)

            for page_data in pages:
                await wiki_service.save_wiki_page(
                    db,
                    slug=page_data["slug"],
                    title=page_data["title"],
                    wiki_type=page_data["wiki_type"],
                    content=page_data["content"],
                    summary=page_data["summary"],
                    tags=page_data["tags"],
                    source_memo_ids=page_data["source_memo_ids"],
                    wiki_links=page_data["wiki_links"],
                )

            # Save semantic links
            for link in final_state.get("suggested_links", []):
                if link.get("confidence", 0) >= 0.7:
                    for page_data in pages:
                        db.add(SemanticLink(
                            source_slug=page_data["slug"],
                            target_slug=link["target_slug"],
                            relation_type=link["relation_type"],
                            confidence=link["confidence"],
                            reason=link.get("reason", ""),
                        ))

            # Mark memos as compiled
            await db.execute(
                update(Memo)
                .where(Memo.id.in_(memo_ids))
                .values(compiled=True, updated_at=datetime.now(timezone.utc))
            )

            # Update job
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

            _safe_progress_update(
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

    except Exception as e:
        logger.exception("[MA-Compile] Job %s FAILED: %s", job_id, e)
        _safe_progress_update(job_id, status="failed", message=f"Error: {str(e)}")
        try:
            async with async_session() as db:
                job = (await db.execute(
                    select(CompileJob).where(CompileJob.id == job_id)
                )).scalar_one_or_none()
                if job:
                    job.status = "failed"
                    job.error_msg = str(e)
                    job.finished_at = datetime.now(timezone.utc)
                    await db.commit()
        except Exception:
            pass
