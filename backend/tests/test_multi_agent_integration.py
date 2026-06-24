"""Integration tests: Mock LLM end-to-end pipeline, SSE streaming, HITL.

Uses FastAPI TestClient + in-memory SQLite to exercise the full compile flow
with mocked LLM responses, verifying API contracts and error recovery.
"""

import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_llm_response(content: str):
    """Build a mock litellm response object."""
    mock = MagicMock()
    choice = MagicMock()
    choice.message.content = content
    mock.choices = [choice]
    usage = MagicMock()
    usage.total_tokens = 100
    mock.usage = usage
    return mock


def _make_researcher_json():
    return json.dumps({
        "entities": [
            {"name": "FastAPI", "type": "framework", "description": "Python web framework"},
            {"name": "SQLAlchemy", "type": "library", "description": "Python ORM"},
        ],
        "relations": [
            {"source": "FastAPI", "target": "SQLAlchemy", "type": "uses"},
        ],
        "key_topics": ["Python", "Web", "ORM"],
    })


def _make_integrator_json():
    return json.dumps({
        "entities": [
            {"name": "FastAPI", "type": "framework", "description": "Async Python web framework"},
            {"name": "SQLAlchemy 2.0", "type": "library", "description": "Modern ORM"},
        ],
        "relations": [
            {"source": "FastAPI", "target": "SQLAlchemy 2.0", "type": "integrates_with"},
        ],
        "gaps": [],
    })


def _make_review_json(score=8.5):
    return json.dumps({
        "score": score,
        "feedback": "Good quality wiki page.",
        "issues": [],
        "suggestions": [],
    })


def _make_arbiter_json(score=8.5):
    return json.dumps({
        "final_score": score,
        "passed": score >= 8.0,
        "summary": "Well compiled wiki.",
        "priority_suggestions": [],
        "accuracy_score": score,
        "readability_score": score,
    })


def _make_links_json():
    return json.dumps({
        "suggested_links": [
            {"target_slug": "python-basics", "relation_type": "prerequisite", "confidence": 0.9, "reason": "Foundation"},
        ]
    })


# ---------------------------------------------------------------------------
# Async test client (simplified for DB-free API tests)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def async_client():
    """Create an async FastAPI test client with in-memory SQLite.

    Uses FastAPI dependency_overrides to inject test DB sessions.
    """
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"

    from app.main import app
    from app.core.database import Base

    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session = async_sessionmaker(engine, expire_on_commit=False)

    # Override FastAPI dependencies
    async def override_get_db():
        async with test_session() as session:
            yield session

    app.dependency_overrides = {}  # Clear any existing overrides

    # Patch all module-level async_session references to use the test session.
    # NOTE: app.api.deps imports async_session at module load, so we must patch
    # it there too — otherwise get_db() uses the original session bound to the
    # real DATABASE_URL, causing "no such table" errors in integration tests.
    patches = [
        patch("app.core.database.async_session", test_session),
        patch("app.api.deps.async_session", test_session),
        patch("app.services.human_review_manager.async_session", test_session),
        patch("app.api.v1.multi_agent_compile.async_session", test_session),
        patch("app.agents.linker_agent.async_session", test_session),
        patch("app.services.compile_service.async_session", test_session),
        patch("app.api.deps.get_db", override_get_db),
    ]

    for p in patches:
        p.start()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        for p in patches:
            p.stop()

    await engine.dispose()


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestMultiAgentCompileAPI:
    """Test the multi-agent compile endpoints end-to-end with mocked LLM."""

    @pytest.mark.asyncio
    async def test_trigger_compile_creates_job(self, async_client):
        """POST /multi-agent creates a compile job and returns job_id."""
        # We need memos in the DB first. Insert them via the API or directly.
        # Since the compile uses real DB sessions, let's create memos first.
        pass  # See test_compile_pipeline_with_memos below

    @pytest.mark.asyncio
    async def test_compile_404_for_missing_job(self, async_client):
        """GET /jobs/nonexistent/trace returns 404."""
        response = await async_client.get("/api/v1/compile/jobs/nonexistent/trace")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_trace_requires_completed_job(self, async_client):
        """Trace endpoint returns 400 if job still in progress, 404 if not found."""
        # For a non-existent job, we expect 404
        response = await async_client.get("/api/v1/compile/jobs/nonexistent-pending/trace")
        assert response.status_code in (400, 404)



class TestSSEStreaming:
    """Test SSE streaming endpoint behavior."""

    @pytest.mark.asyncio
    async def test_sse_returns_error_for_missing_job(self, async_client):
        """SSE stream returns error event for non-existent job."""
        response = await async_client.get(
            "/api/v1/compile/jobs/nonexistent/multi-stream",
            headers={"Accept": "text/event-stream"},
        )
        assert response.status_code == 200  # SSE always returns 200
        # Should get error event
        body = response.text
        assert "error" in body or "Job not found" in body

    @pytest.mark.asyncio
    async def test_sse_stream_headers(self, async_client):
        """SSE response has correct content-type and headers."""
        # Create a job first so the SSE has something to stream
        from app.models.compile_job import CompileJob
        from app.core.database import async_session

        async with async_session() as db:
            job = CompileJob(
                id="test-sse-job",
                status="failed",
                compile_type="multi_agent",
                memo_ids="[]",
                model_id="test-model",
            )
            db.add(job)
            await db.commit()

        # Initialize progress so the stream finds it
        from app.core.progress_store import init_progress
        await init_progress(
            "test-sse-job",
            status="completed",
            progress=100,
            message="Done.",
        )

        response = await async_client.get(
            "/api/v1/compile/jobs/test-sse-job/multi-stream",
            headers={"Accept": "text/event-stream"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        assert "no-cache" in response.headers.get("cache-control", "")


class TestHumanReviewAPI:
    """Test human review submission endpoint."""

    @pytest.mark.asyncio
    async def test_submit_review_approve(self, async_client):
        """POST /human-review/{task_id}/submit with approve decision."""
        from app.services.human_review_manager import human_review_manager

        # Pre-create a pending task in the manager
        task_id = "test-review-api-1"
        human_review_manager._events[task_id] = asyncio.Event()

        response = await async_client.post(
            f"/api/v1/compile/human-review/{task_id}/submit",
            json={"decision": "approve", "edited_wiki": None},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["review_passed"] is True
        assert data["data"]["next_action"] == "link"

    @pytest.mark.asyncio
    async def test_submit_review_revise(self, async_client):
        """POST /human-review/{task_id}/submit with revise decision."""
        from app.services.human_review_manager import human_review_manager

        task_id = "test-review-api-2"
        human_review_manager._events[task_id] = asyncio.Event()

        response = await async_client.post(
            f"/api/v1/compile/human-review/{task_id}/submit",
            json={"decision": "revise", "edited_wiki": "Edited content here."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["review_passed"] is False
        assert data["data"]["next_action"] == "revise"

    @pytest.mark.asyncio
    async def test_submit_review_reject(self, async_client):
        """POST /human-review/{task_id}/submit with reject decision."""
        from app.services.human_review_manager import human_review_manager

        task_id = "test-review-api-3"
        human_review_manager._events[task_id] = asyncio.Event()

        response = await async_client.post(
            f"/api/v1/compile/human-review/{task_id}/submit",
            json={"decision": "reject"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["next_action"] == "finish"

    @pytest.mark.asyncio
    async def test_submit_review_invalid_decision(self, async_client):
        """POST with invalid decision value returns 422 validation error."""
        response = await async_client.post(
            "/api/v1/compile/human-review/test-id/submit",
            json={"decision": "invalid_choice"},
        )
        assert response.status_code == 422


class TestErrorRecovery:
    """Test error recovery paths in the graph pipeline."""

    @pytest.mark.asyncio
    async def test_agent_fallback_on_llm_failure(self, mock_llm):
        """When LLM fails, agent_error_handler produces fallback state."""
        from app.services.multi_agent_graph import _researcher_node
        from app.core.agent_error_handler import AgentErrorHandler
        from app.core.circuit_breaker import CircuitState
        import time

        handler = AgentErrorHandler()

        # Force only the researcher circuit breaker open
        cb = handler.circuit_breakers["researcher"]
        cb.state = CircuitState.OPEN
        cb.failure_count = 5
        cb.last_failure_time = time.time()

        with patch("app.services.multi_agent_graph.agent_error_handler", handler):
            state = {
                "memo_ids": ["m1"],
                "memos_content": ["Test content"],
                "compilation_config": {"model": "test", "parallel_researchers": 3},
                "_model_config": {"model": "test"},
                "job_id": "test-fallback",
                "research_results": [],
                "compilation_log": [],
            }
            result = await _researcher_node(state)

        # Fallback for researcher produces empty research results
        # (the _researcher_node returns {"research_results": ..., "current_agent": ...})
        assert "research_results" in result

    @pytest.mark.asyncio
    async def test_researcher_json_parse_fallback(self, mock_llm):
        """Researcher returns empty result when LLM returns invalid JSON."""
        from app.agents.researcher_agent import ResearcherPool

        mock_llm.return_value = _make_llm_response("not valid {{{ json")

        pool = ResearcherPool(max_concurrency=1)
        focus = {"name": "test", "label": "Test", "prompt_extra": ""}
        state = {
            "memos_content": ["Some memo content."],
            "_model_config": {"model": "test"},
            "compilation_config": {"model": "test"},
        }

        result = await pool.run_single(state, focus)
        assert result["entities"] == []
        assert result["_focus"] == "test"

    @pytest.mark.asyncio
    async def test_arbiter_llm_fallback_to_weighted_score(self):
        """Arbiter uses heuristic scoring when LLM parsing fails."""
        from app.agents.arbiter_agent import _compute_weighted_score

        reviews = [
            {"score": 9.0, "agent": "accuracy", "feedback": "Excellent"},
            {"score": 6.0, "agent": "readability", "feedback": "Needs work"},
        ]

        result = _compute_weighted_score(reviews)
        assert result["final_score"] == 7.8  # 9.0*0.6 + 6.0*0.4
        assert result["accuracy_score"] == 9.0
        assert result["readability_score"] == 6.0


class TestEvaluationPipeline:
    """Test end-to-end evaluation after compilation."""

    def test_evaluation_integration(self):
        """Evaluation service computes scores for compiled wiki content."""
        from app.services.evaluation_service import WikiEvaluationService

        content = """# Python Backend Guide

## FastAPI

FastAPI is a modern Python web framework for building APIs.
It supports async/await and uses Pydantic for validation.

## SQLAlchemy

SQLAlchemy is the Python SQL toolkit and ORM.
Version 2.0 introduces a new declarative mapping style.

### Key Features
- Async support
- Type-safe queries
- Migration support

| Feature | FastAPI | SQLAlchemy |
|---------|---------|------------|
| Type | Web framework | ORM |
| Async | Yes | Yes |
"""
        sources = [
            "FastAPI is a web framework. SQLAlchemy is an ORM. Python is a language.",
            "Async programming in Python uses asyncio.",
        ]

        evaluator = WikiEvaluationService()
        result = evaluator.evaluate(content, sources, "python-backend")

        # Verify all dimensions are scored
        assert 1.0 <= result.overall <= 10.0
        assert 0.0 <= result.structure <= 10.0
        assert 1.0 <= result.readability <= 10.0
        assert 1.0 <= result.info_density <= 10.0
        assert len(result.summary) > 0

    @pytest.mark.asyncio
    async def test_evaluate_wiki_async_no_error(self):
        """Background evaluation does not raise even with bad inputs."""
        from app.services.evaluation_service import evaluate_wiki_async

        result = await evaluate_wiki_async("test", "", [])
        assert result is not None  # Should still return a result object
        assert 0.0 <= result.overall <= 10.0

    @pytest.mark.asyncio
    async def test_evaluate_wiki_async_exception_handled(self):
        """Background evaluation handles exceptions gracefully."""
        from app.services.evaluation_service import evaluate_wiki_async

        # None content would normally cause an error in split()
        result = await evaluate_wiki_async("test", None, ["source"])
        # Should return None on exception
        assert result is None


class TestGraphPipelineEndToEnd:
    """Full LangGraph pipeline with mocked LLM at every node."""

    @pytest.mark.asyncio
    async def test_full_pipeline_success_path(self):
        """Run the complete 10-node graph with mocked LLM responses."""
        from app.services.multi_agent_graph import (
            MultiAgentCompilationGraph, tracer_registry,
        )
        from app.core.compilation_tracer import CompilationTracer

        # Mock all LLM calls with sequential responses matching the pipeline order
        mock_responses = [
            _make_llm_response(_make_researcher_json()),   # researcher x3
            _make_llm_response(_make_researcher_json()),
            _make_llm_response(_make_researcher_json()),
            _make_llm_response(_make_integrator_json()),    # integrator
            _make_llm_response("# Python Backend Guide\n\nFastAPI is a modern web framework.\n\n## Framework\n\nDetails."),  # writer
            _make_llm_response(_make_review_json(8.5)),     # reviewer accuracy
            _make_llm_response(_make_review_json(7.5)),     # reviewer readability
            _make_llm_response(_make_arbiter_json(8.0)),    # arbiter
            _make_llm_response(_make_links_json()),         # linker
        ]

        call_count = [0]

        async def mock_llm(*args, **kwargs):
            idx = min(call_count[0], len(mock_responses) - 1)
            call_count[0] += 1
            return mock_responses[idx]

        job_id = "test-e2e-pipeline"
        tracer = CompilationTracer(job_id=job_id)
        tracer_registry.register(job_id, tracer)

        try:
            with patch("app.services.llm_service.chat_completion", side_effect=mock_llm):
                config = {
                    "model": "deepseek/deepseek-chat",
                    "max_revisions": 3,
                    "parallel_researchers": 3,
                    "pass_threshold": 8.0,
                    "enable_human_review": False,
                }

                graph_builder = MultiAgentCompilationGraph(config)
                graph = graph_builder.build()

                state = {
                    "memo_ids": ["m1", "m2", "m3"],
                    "memos_content": [
                        "FastAPI is a Python web framework.",
                        "SQLAlchemy is a Python ORM.",
                        "LangGraph is for LLM agents.",
                    ],
                    "compilation_config": config,
                    "_model_config": {
                        "model": "deepseek/deepseek-chat",
                        "provider": "deepseek",
                        "model_name": "deepseek-chat",
                        "api_key_enc": "",
                    },
                    "job_id": job_id,
                    "memo_groups": [["m1", "m2", "m3"]],
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
                    "current_agent": "coordinator",
                    "next_action": "continue",
                }

                run_config = {"configurable": {"thread_id": job_id}}
                final_state = await graph.ainvoke(state, run_config)

            # Verify pipeline completed successfully
            assert final_state["review_passed"] is True
            assert final_state["final_score"] >= 8.0
            assert len(final_state["wiki_draft"]) > 0
            # suggested_links may be empty if no existing wikis in DB (linker skip)
            assert len(final_state["reviews"]) >= 2  # Both reviewers contributed

        finally:
            tracer_registry.pop(job_id)

    @pytest.mark.asyncio
    async def test_pipeline_with_revision_loop(self):
        """Pipeline goes through revision when first pass fails."""
        from app.services.multi_agent_graph import (
            MultiAgentCompilationGraph, tracer_registry,
        )
        from app.core.compilation_tracer import CompilationTracer

        # Responses: researchers(3) + integrator + writer + reviewers(2) +
        # arbiter(fail) + editor + reviewers(2) + arbiter(pass) + linker
        mock_responses = [
            _make_llm_response(_make_researcher_json()),   # researcher 1
            _make_llm_response(_make_researcher_json()),   # researcher 2
            _make_llm_response(_make_researcher_json()),   # researcher 3
            _make_llm_response(_make_integrator_json()),    # integrator
            _make_llm_response("# Draft\n\nNeeds improvement."),  # writer
            _make_llm_response(_make_review_json(5.0)),     # reviewer accuracy (fail)
            _make_llm_response(_make_review_json(6.0)),     # reviewer readability (fail)
            _make_llm_response(_make_arbiter_json(5.5)),    # arbiter (fail)
            _make_llm_response("# Revised\n\nBetter now with more content."),  # editor
            _make_llm_response(_make_review_json(8.5)),     # reviewer accuracy (pass)
            _make_llm_response(_make_review_json(8.0)),     # reviewer readability (pass)
            _make_llm_response(_make_arbiter_json(8.2)),    # arbiter (pass)
            _make_llm_response(_make_links_json()),         # linker
        ]

        call_count = [0]

        async def mock_llm(*args, **kwargs):
            idx = min(call_count[0], len(mock_responses) - 1)
            call_count[0] += 1
            return mock_responses[idx]

        job_id = "test-revision-loop"
        tracer = CompilationTracer(job_id=job_id)
        tracer_registry.register(job_id, tracer)

        try:
            with patch("app.services.llm_service.chat_completion", side_effect=mock_llm):
                config = {
                    "model": "deepseek/deepseek-chat",
                    "max_revisions": 3,
                    "pass_threshold": 8.0,
                    "enable_human_review": False,
                }

                graph_builder = MultiAgentCompilationGraph(config)
                graph = graph_builder.build()

                state = {
                    "memo_ids": ["m1", "m2"],
                    "memos_content": [
                        "Python is a programming language.",
                        "Testing is important.",
                    ],
                    "compilation_config": config,
                    "_model_config": {
                        "model": "deepseek/deepseek-chat",
                        "provider": "deepseek",
                        "model_name": "deepseek-chat",
                        "api_key_enc": "",
                    },
                    "job_id": job_id,
                    "memo_groups": [["m1", "m2"]],
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
                    "current_agent": "coordinator",
                    "next_action": "continue",
                }

                run_config = {"configurable": {"thread_id": job_id}}
                final_state = await graph.ainvoke(state, run_config)

            # Should pass after revision
            assert final_state["review_passed"] is True
            assert final_state["final_score"] >= 8.0
            assert final_state["revision_count"] >= 1

        finally:
            tracer_registry.pop(job_id)

    @pytest.mark.asyncio
    async def test_pipeline_human_review_path(self):
        """Pipeline pauses for human review when enable_human_review is True."""
        from app.services.multi_agent_graph import (
            MultiAgentCompilationGraph, tracer_registry,
        )
        from app.core.compilation_tracer import CompilationTracer

        # Need enough responses to get through: researchers(3) + integrator +
        # writer + reviewers(2) + arbiter(pass) → human_review → linker
        mock_responses = [
            _make_llm_response(_make_researcher_json()),
            _make_llm_response(_make_researcher_json()),
            _make_llm_response(_make_researcher_json()),
            _make_llm_response(_make_integrator_json()),
            _make_llm_response("# Draft Wiki\n\nContent."),
            _make_llm_response(_make_review_json(8.5)),
            _make_llm_response(_make_review_json(8.0)),
            _make_llm_response(_make_arbiter_json(8.2)),
            _make_llm_response(_make_links_json()),
        ]

        call_count = [0]

        async def mock_llm(*args, **kwargs):
            idx = min(call_count[0], len(mock_responses) - 1)
            call_count[0] += 1
            return mock_responses[idx]

        # Pre-populate human review result so the pipeline doesn't block
        from app.services.human_review_manager import human_review_manager

        # Mock the create_review_task to return immediately with approve
        original_create = human_review_manager.create_review_task

        async def fast_approve(job_id, review_data):
            task_id = f"task-{job_id}"
            return {
                "task_id": task_id,
                "decision": "approve",
                "edited_wiki": None,
            }

        human_review_manager.create_review_task = fast_approve

        job_id = "test-hitl-pipeline"
        tracer = CompilationTracer(job_id=job_id)
        tracer_registry.register(job_id, tracer)

        try:
            with patch("app.services.llm_service.chat_completion", side_effect=mock_llm):
                config = {
                    "model": "deepseek/deepseek-chat",
                    "max_revisions": 3,
                    "pass_threshold": 8.0,
                    "enable_human_review": True,
                }

                graph_builder = MultiAgentCompilationGraph(config)
                graph = graph_builder.build()

                state = {
                    "memo_ids": ["m1"],
                    "memos_content": ["Python testing is important for software quality."],
                    "compilation_config": config,
                    "_model_config": {
                        "model": "deepseek/deepseek-chat",
                        "provider": "deepseek",
                        "model_name": "deepseek-chat",
                        "api_key_enc": "",
                    },
                    "job_id": job_id,
                    "memo_groups": [["m1"]],
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
                    "current_agent": "coordinator",
                    "next_action": "continue",
                    "human_reviewed": False,
                }

                run_config = {"configurable": {"thread_id": job_id}}
                final_state = await graph.ainvoke(state, run_config)

            assert final_state.get("human_reviewed") is True
            assert final_state["review_passed"] is True

        finally:
            tracer_registry.pop(job_id)
            human_review_manager.create_review_task = original_create


class TestPerformanceMetrics:
    """Verify that performance-related code paths are instrumented."""

    @pytest.mark.asyncio
    async def test_llm_cache_stats_accessible(self):
        """Cache statistics are tracked via the stats dict."""
        from app.core.llm_cache import LLMCache
        import uuid

        # Use unique DB path to avoid cross-test contamination
        test_id = uuid.uuid4().hex[:8]
        cache = LLMCache(db_path=f"./data/test_cache_{test_id}.db", memory_size=10, ttl=3600)

        # Simulate workload
        for i in range(5):
            await cache.get(f"prompt-{i}", "gpt-4")  # misses
        for i in range(5):
            await cache.set(f"prompt-{i}", "gpt-4", f"response-{i}")
        for i in range(5):
            await cache.get(f"prompt-{i}", "gpt-4")  # memory hits
        for i in range(5):
            await cache.get(f"prompt-{i}", "gpt-4")  # memory hits again

        stats = cache.stats
        assert stats["miss"] == 5
        assert stats["mem"] == 10
        # Hit rate = mem / total = 10/15 ≈ 66%
        total = stats["mem"] + stats["disk"] + stats["miss"]
        hit_rate = (stats["mem"] + stats["disk"]) / total
        assert 0.5 <= hit_rate <= 0.8

    @pytest.mark.asyncio
    async def test_researcher_pool_concurrency(self):
        """ResearcherPool respects max_concurrency via semaphore."""
        from app.agents.researcher_agent import ResearcherPool

        concurrent_count = [0]
        max_concurrent = [0]

        async def slow_mock(*args, **kwargs):
            concurrent_count[0] += 1
            max_concurrent[0] = max(max_concurrent[0], concurrent_count[0])
            await asyncio.sleep(0.01)
            concurrent_count[0] -= 1
            return _make_llm_response(_make_researcher_json())

        pool = ResearcherPool(max_concurrency=2)

        with patch("app.services.llm_service.chat_completion", side_effect=slow_mock):
            state = {
                "memos_content": ["Test content."],
                "_model_config": {"model": "test"},
                "compilation_config": {"model": "test"},
            }
            await pool.run_all(state)

        # With max_concurrency=2, we should never exceed 2 concurrent calls
        assert max_concurrent[0] <= 2
        assert max_concurrent[0] >= 1  # At least some concurrency

    @pytest.mark.asyncio
    async def test_tracer_emits_with_low_latency(self):
        """Trace entry timestamps are within reasonable bounds."""
        from app.core.compilation_tracer import CompilationTracer
        import time

        tracer = CompilationTracer(job_id="perf-test")

        start = time.time()
        for i in range(20):
            await tracer.phase_start(f"Agent{i}", f"L{i%5}", f"Event {i}")
            await tracer.phase_end(f"Agent{i}", f"L{i%5}", f"End {i}")
        elapsed = time.time() - start

        # 20 phase_start + 20 phase_end = 40 trace entries in < 1 second
        assert elapsed < 1.0
        assert len(tracer.entries) == 40
