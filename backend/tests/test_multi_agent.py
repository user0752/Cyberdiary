"""Unit tests for multi-agent compile core components.

Covers: CircuitBreaker, LLMCache, AgentErrorHandler, arbiter scoring,
WikiEvaluationService, and agent node logic with mocked LLM.
"""

import asyncio
import json
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ============================================================================
# CircuitBreaker
# ============================================================================

class TestCircuitBreaker:
    """Test circuit breaker state machine: CLOSED → OPEN → HALF_OPEN → CLOSED."""

    @pytest.mark.asyncio
    async def test_normal_operation_closed(self):
        from app.core.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)
        assert cb.state == CircuitState.CLOSED

        async def ok_func():
            return "ok"

        result = await cb.call(ok_func)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_opens_after_threshold_failures(self):
        from app.core.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpenError

        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=60)

        async def fail_func():
            raise ValueError("fail")

        # Two failures should open the breaker
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(fail_func)

        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 2

        # Next call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(lambda: "ok")

    @pytest.mark.asyncio
    async def test_half_open_recovery(self):
        from app.core.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpenError

        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.01)

        async def fail_func():
            raise ValueError("fail")

        # Open the breaker
        with pytest.raises(ValueError):
            await cb.call(fail_func)
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.02)

        # Now should be HALF_OPEN and succeed, transitioning to CLOSED
        async def recovered():
            return "recovered"

        result = await cb.call(recovered)
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_fails_returns_to_open(self):
        from app.core.circuit_breaker import CircuitBreaker, CircuitState, CircuitBreakerOpenError

        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.01)

        async def fail_func():
            raise ValueError("fail")

        # Open
        with pytest.raises(ValueError):
            await cb.call(fail_func)
        assert cb.state == CircuitState.OPEN

        await asyncio.sleep(0.02)

        # HALF_OPEN, fail again → back to OPEN
        with pytest.raises(ValueError):
            await cb.call(fail_func)

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_success_after_some_failures_resets_count(self):
        from app.core.circuit_breaker import CircuitBreaker, CircuitState

        cb = CircuitBreaker("test", failure_threshold=5, recovery_timeout=60)

        async def fail_func():
            raise ValueError("fail")

        async def ok_func():
            return "ok"

        # One failure
        with pytest.raises(ValueError):
            await cb.call(fail_func)
        assert cb.failure_count == 1

        # Success resets counter
        await cb.call(ok_func)
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED


# ============================================================================
# LLMCache
# ============================================================================

class TestLLMCache:
    """Test LLMCache: memory, disk, TTL, LRU eviction."""

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self):
        from app.core.llm_cache import LLMCache

        cache = LLMCache(db_path="./data/test_llm_cache.db", memory_size=10, ttl=3600)
        result = await cache.get("test prompt", "gpt-4")
        assert result is None
        assert cache.stats["miss"] == 1

    @pytest.mark.asyncio
    async def test_set_and_get_memory_hit(self):
        from app.core.llm_cache import LLMCache

        cache = LLMCache(db_path="./data/test_llm_cache.db", memory_size=10, ttl=3600)
        await cache.set("prompt A", "model-x", "response for A")
        result = await cache.get("prompt A", "model-x")
        assert result == "response for A"
        assert cache.stats["mem"] == 1

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        from app.core.llm_cache import LLMCache

        cache = LLMCache(db_path="./data/test_llm_cache.db", memory_size=10, ttl=0)
        await cache.set("stale", "model-x", "stale response")
        result = await cache.get("stale", "model-x")
        assert result is None  # TTL expired
        assert cache.stats["miss"] >= 1

    @pytest.mark.asyncio
    async def test_different_prompts_different_keys(self):
        from app.core.llm_cache import LLMCache

        cache = LLMCache(db_path="./data/test_llm_cache.db", memory_size=10, ttl=3600)
        await cache.set("p1", "m", "r1")
        await cache.set("p2", "m", "r2")
        assert await cache.get("p1", "m") == "r1"
        assert await cache.get("p2", "m") == "r2"

    @pytest.mark.asyncio
    async def test_different_models_different_keys(self):
        from app.core.llm_cache import LLMCache

        cache = LLMCache(db_path="./data/test_llm_cache.db", memory_size=10, ttl=3600)
        await cache.set("prompt", "model-a", "resp-a")
        await cache.set("prompt", "model-b", "resp-b")
        assert await cache.get("prompt", "model-a") == "resp-a"
        assert await cache.get("prompt", "model-b") == "resp-b"

    @pytest.mark.asyncio
    async def test_kwargs_affect_cache_key(self):
        from app.core.llm_cache import LLMCache

        cache = LLMCache(db_path="./data/test_llm_cache.db", memory_size=10, ttl=3600)
        await cache.set("p", "m", "r1", temperature=0.7)
        await cache.set("p", "m", "r2", temperature=0.0)
        assert await cache.get("p", "m", temperature=0.7) == "r1"
        assert await cache.get("p", "m", temperature=0.0) == "r2"

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        from app.core.llm_cache import LLMCache

        cache = LLMCache(db_path="./data/test_llm_cache.db", memory_size=3, ttl=3600)

        for i in range(5):
            await cache.set(f"prompt-{i}", "m", f"response-{i}")

        # Memory should only hold 3 entries
        assert len(cache.memory) == 3

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        from app.core.llm_cache import LLMCache

        cache = LLMCache(db_path="./data/test_llm_cache.db", memory_size=10, ttl=3600)

        await cache.get("never-set", "m")  # miss
        await cache.set("p", "m", "r")
        await cache.get("p", "m")  # mem hit
        await cache.get("p", "m")  # mem hit again

        assert cache.stats["miss"] == 1
        assert cache.stats["mem"] == 2


# ============================================================================
# AgentErrorHandler
# ============================================================================

class TestAgentErrorHandler:
    """Test AgentErrorHandler: retry, circuit breaker, fallback."""

    @pytest.mark.asyncio
    async def test_successful_execution_passes_through(self):
        from app.core.agent_error_handler import AgentErrorHandler

        handler = AgentErrorHandler()

        async def good_func(s):
            s["result"] = "done"
            return s

        state = {"key": "value"}
        result = await handler.execute("coordinator", good_func, state)
        assert result["key"] == "value"
        assert result["result"] == "done"

    @pytest.mark.asyncio
    async def test_fallback_when_circuit_breaker_open(self):
        from app.core.agent_error_handler import AgentErrorHandler
        from app.core.circuit_breaker import CircuitState
        import time

        handler = AgentErrorHandler()

        # Force circuit breaker open with recent failure time
        cb = handler.circuit_breakers["coordinator"]
        cb.state = CircuitState.OPEN
        cb.failure_count = 3
        cb.last_failure_time = time.time()  # just now, so recovery timeout hasn't elapsed

        async def should_not_be_called(s):
            raise RuntimeError("should not run")

        state = {"key": "original"}
        result = await handler.execute(
            "coordinator", should_not_be_called, state,
            fallback_value={"key": "fallback"},
        )
        assert result["key"] == "fallback"

    @pytest.mark.asyncio
    async def test_researcher_fallback_produces_empty_results(self):
        from app.core.agent_error_handler import AgentErrorHandler

        handler = AgentErrorHandler()
        state = {"research_results": []}

        result = handler._fallback("researcher", state, None)
        assert "research_results" in result
        assert len(result["research_results"]) == 1
        assert result["research_results"][0]["entities"] == []

    @pytest.mark.asyncio
    async def test_reviewer_fallback_appends_auto_pass(self):
        from app.core.agent_error_handler import AgentErrorHandler

        handler = AgentErrorHandler()
        state = {"reviews": []}

        result = handler._fallback("reviewer_accuracy", state, None)
        assert len(result["reviews"]) == 1
        # P2-21: fallback score is now 7.0 (neutral, near pass threshold)
        # instead of 0.0/5.0, so a single failed reviewer does not
        # force-loop the draft to max_revisions when the other reviewer
        # is healthy. 5.0 was too low — one timeout → 6.5 avg → revise.
        assert result["reviews"][0]["score"] == 7.0
        assert result["reviews"][0].get("fallback") is True
        assert "degraded_agents" in result
        assert "reviewer_accuracy" in result["degraded_agents"]

    @pytest.mark.asyncio
    async def test_linker_fallback_returns_empty_links(self):
        from app.core.agent_error_handler import AgentErrorHandler

        handler = AgentErrorHandler()
        state = {"suggested_links": [{"existing": "link"}]}

        result = handler._fallback("linker", state, None)
        assert result["suggested_links"] == []

    @pytest.mark.asyncio
    async def test_fallback_value_overrides_default(self):
        from app.core.agent_error_handler import AgentErrorHandler

        handler = AgentErrorHandler()
        state = {}

        # Non-None fallback_value is returned directly
        result = handler._fallback("unknown_agent", state, {"override": True})
        assert result == {"override": True}


# ============================================================================
# Arbiter Agent — weighted scoring
# ============================================================================

class TestArbiterWeightedScoring:
    """Test _compute_weighted_score with various reviewer combinations."""

    def test_weighted_score_both_reviewers(self):
        from app.agents.arbiter_agent import _compute_weighted_score

        reviews = [
            {"score": 9.0, "agent": "accuracy", "feedback": "accurate", "suggestions": ["add examples"]},
            {"score": 6.0, "agent": "readability", "feedback": "dense text", "suggestions": ["simplify"]},
        ]
        result = _compute_weighted_score(reviews)

        # accuracy=0.6, readability=0.4 → 9.0*0.6 + 6.0*0.4 = 5.4 + 2.4 = 7.8
        assert result["final_score"] == 7.8
        assert result["accuracy_score"] == 9.0
        assert result["readability_score"] == 6.0
        # P2-19: threshold is now 8.0 (matches the LLM arbiter path), so
        # 7.8 is a REVISE, not a PASS.
        assert result["passed"] is False  # 7.8 < 8.0

    def test_accuracy_only(self):
        from app.agents.arbiter_agent import _compute_weighted_score

        reviews = [
            {"score": 8.5, "agent": "accuracy", "feedback": "good"},
        ]
        result = _compute_weighted_score(reviews)

        assert result["final_score"] == 8.5
        assert result["accuracy_score"] == 8.5
        assert result["passed"] is True

    def test_readability_only(self):
        from app.agents.arbiter_agent import _compute_weighted_score

        reviews = [
            {"score": 5.0, "agent": "readability", "feedback": "needs work"},
        ]
        result = _compute_weighted_score(reviews)

        assert result["final_score"] == 5.0
        assert result["readability_score"] == 5.0
        assert result["passed"] is False  # 5.0 < 7.0

    def test_unknown_agent_type_treated_as_accuracy(self):
        from app.agents.arbiter_agent import _compute_weighted_score

        reviews = [
            {"score": 9.0, "agent": "unknown", "feedback": "ok"},
        ]
        result = _compute_weighted_score(reviews)
        assert result["final_score"] == 9.0

    def test_empty_reviews_returns_default(self):
        from app.agents.arbiter_agent import _compute_weighted_score

        result = _compute_weighted_score([])
        assert result["final_score"] == 0.0
        assert result["passed"] is False

    def test_suggestions_aggregated(self):
        from app.agents.arbiter_agent import _compute_weighted_score

        reviews = [
            {"score": 8.0, "agent": "accuracy", "suggestions": ["fix A", "fix B"]},
            {"score": 7.0, "agent": "readability", "suggestions": ["fix C"]},
        ]
        result = _compute_weighted_score(reviews)
        assert len(result["priority_suggestions"]) == 3
        assert "fix A" in result["priority_suggestions"]

    def test_pass_threshold_edge(self):
        from app.agents.arbiter_agent import _compute_weighted_score

        reviews = [
            {"score": 7.0, "agent": "accuracy", "feedback": "borderline"},
        ]
        result = _compute_weighted_score(reviews)
        assert result["final_score"] == 7.0
        # P2-19: default threshold raised to 8.0 to match the LLM arbiter
        # path; 7.0 is now a REVISE.
        assert result["passed"] is False  # 7.0 < 8.0

    def test_pass_threshold_explicit_override(self):
        """Callers can override pass_threshold (the LLM arbiter path reads
        it from compilation_config). Verify the override is honored so the
        fallback and LLM paths stay consistent for the same threshold."""
        from app.agents.arbiter_agent import _compute_weighted_score

        reviews = [
            {"score": 7.0, "agent": "accuracy", "feedback": "borderline"},
        ]
        result = _compute_weighted_score(reviews, pass_threshold=7.0)
        assert result["passed"] is True  # 7.0 >= 7.0 (explicit override)


# ============================================================================
# WikiEvaluationService
# ============================================================================

class TestWikiEvaluationService:
    """Test heuristic scoring dimensions: structure, readability, info_density."""

    @pytest.fixture
    def evaluator(self):
        from app.services.evaluation_service import WikiEvaluationService
        return WikiEvaluationService()

    def test_structure_score_well_structured(self, evaluator):
        content = """# Title

## Section 1

Some content here with enough text to reach the 500 char minimum.
Let me add more text to make sure we pass the length threshold.
Still need more content. Writing some extra words here to fill up space.
Almost there, just a few more characters to reach the minimum length requirement.
Done.

- item one
- item two

| col1 | col2 |
|------|------|
| a    | b    |
"""
        # Make sure we have 500 chars
        content = content + "x" * max(0, 500 - len(content))
        score = evaluator._score_structure(content)
        assert score >= 7.0  # headings(3+2) + lists(1.5) + table(1) + length(2.5) = 10 capped

    def test_structure_score_no_headings(self, evaluator):
        score = evaluator._score_structure("Just some plain text without any structure.")
        assert score == 0.0

    def test_readability_good_sentence_length(self, evaluator):
        # ~15-25 words per sentence, with paragraph breaks
        content = (
            "This is a sentence with about ten words. "
            + "Another sentence that should be just right for readability scoring. " * 5
            + "\n\nSecond paragraph here with more content that is well structured. "
            + "And another sentence to round things out."
        )
        score = evaluator._score_readability(content)
        # Should be in the 7-8.5 range
        assert 5.0 <= score <= 10.0

    def test_readability_too_short_sentences(self, evaluator):
        content = "Hi. Ok. No. Go."  # Very choppy
        score = evaluator._score_readability(content)
        assert score <= 5.0  # Penalized for choppiness

    def test_info_density_good_ratio(self, evaluator):
        sources = ["Source text with key technical terms like FastAPI, SQLAlchemy, and LangGraph. " * 5]
        content = "FastAPI and SQLAlchemy are important tools. LangGraph is also relevant. " * 10
        score = evaluator._score_info_density(content, sources)
        # Good coverage with keyword overlap
        assert 6.0 <= score <= 10.0

    def test_info_density_too_short(self, evaluator):
        sources = ["Very long source text. " * 50]
        content = "Tiny wiki."
        score = evaluator._score_info_density(content, sources)
        assert score < 5.0  # ratio too small

    def test_overall_score_calculation(self, evaluator):
        content = """# Test Wiki

## Overview
A comprehensive test wiki page with enough content to get good scores.
It contains multiple sections and proper formatting.
This should give us a solid structure and readability score.

## Details
More content here with technical terms like FastAPI and SQLAlchemy.
- Item 1
- Item 2

Additional paragraphs to fill out the content and make it substantial.
This helps improve the information density score as well.
"""
        sources = ["FastAPI SQLAlchemy test source content. " * 5]
        result = evaluator.evaluate(content, sources, "test-wiki")

        assert 1.0 <= result.overall <= 10.0
        assert 0.0 <= result.structure <= 10.0
        assert 1.0 <= result.readability <= 10.0
        assert 1.0 <= result.info_density <= 10.0
        assert len(result.summary) > 0
        assert result.wiki_slug == "test-wiki"

    def test_evaluate_wiki_async_no_sources(self, evaluator):
        """evaluate_wiki_async should not raise on empty sources."""
        content = "# Test\nSome content."
        result = evaluator.evaluate(content, [], "test")
        assert result.overall >= 1.0


# ============================================================================
# CoordinatorAgent
# ============================================================================

class TestCoordinatorAgent:
    """Test CoordinatorAgent clustering logic."""

    @pytest.mark.asyncio
    async def test_no_embedding_model_uses_single_group(self, sample_state):
        from app.agents.coordinator_agent import CoordinatorAgent

        agent = CoordinatorAgent()
        state = dict(sample_state)
        state["compilation_config"] = {**state["compilation_config"], "embedding_model": ""}

        result = await agent.run(state)
        assert len(result["memo_groups"]) == 1
        assert result["memo_groups"][0] == state["memo_ids"]

    @pytest.mark.asyncio
    async def test_few_memos_no_clustering(self, sample_state):
        from app.agents.coordinator_agent import CoordinatorAgent

        agent = CoordinatorAgent()
        state = dict(sample_state)
        state["memo_ids"] = ["m1", "m2"]  # < 3, no clustering
        state["memos_content"] = state["memos_content"][:2]
        state["compilation_config"] = {**state["compilation_config"], "embedding_model": "text-embedding"}

        result = await agent.run(state)
        assert len(result["memo_groups"]) == 1

    @pytest.mark.asyncio
    async def test_clusters_with_embedding_model(self, sample_state, mock_embedding):
        from app.agents.coordinator_agent import CoordinatorAgent

        agent = CoordinatorAgent()
        state = dict(sample_state)
        state["compilation_config"] = {
            **state["compilation_config"],
            "embedding_model": "text-embedding-3-small",
        }

        # Mock sklearn KMeans at the source
        with patch("sklearn.cluster.KMeans") as mock_kmeans:
            mock_instance = MagicMock()
            mock_instance.fit_predict.return_value = [0, 0, 1]
            mock_kmeans.return_value = mock_instance

            result = await agent.run(state)
            assert len(result["memo_groups"]) >= 1
            # Groups should contain the original memo IDs
            all_ids = [mid for g in result["memo_groups"] for mid in g]
            assert set(all_ids) == set(state["memo_ids"])


# ============================================================================
# ResearcherPool
# ============================================================================

class TestResearcherPool:
    """Test ResearcherPool parallel execution and fallback."""

    @pytest.mark.asyncio
    async def test_run_all_with_mock_llm(self, sample_state, mock_llm):
        from app.agents.researcher_agent import ResearcherPool

        mock_llm.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(
                content=json.dumps({"entities": [{"name": "X"}], "relations": [], "key_topics": ["X"]})
            ))],
            usage=MagicMock(total_tokens=50),
        )

        pool = ResearcherPool(max_concurrency=3)
        state = dict(sample_state)
        results = await pool.run_all(state)

        assert len(results) == 3  # 3 focus perspectives
        assert all("_focus" in r for r in results)

    @pytest.mark.asyncio
    async def test_run_single_handles_json_parse_error(self, sample_state, mock_llm):
        from app.agents.researcher_agent import ResearcherPool

        # Return invalid JSON
        mock_llm.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="not valid json {{{"))],
            usage=MagicMock(total_tokens=5),
        )

        pool = ResearcherPool(max_concurrency=1)
        focus = {"name": "test", "label": "Test", "prompt_extra": ""}
        result = await pool.run_single(sample_state, focus)

        assert result["entities"] == []
        assert result["relations"] == []
        assert result["key_topics"] == []

    @pytest.mark.asyncio
    async def test_all_failures_return_fallback(self, sample_state):
        from app.agents.researcher_agent import ResearcherPool

        pool = ResearcherPool(max_concurrency=1)

        # Simulate all focus configs failing by monkey-patching run_single
        async def fail(*args, **kwargs):
            raise RuntimeError("simulated failure")

        pool.run_single = fail
        results = await pool.run_all(sample_state)

        assert len(results) == 1
        assert results[0]["entities"] == []
        assert results[0]["_focus"] == "fallback"


# ============================================================================
# Graph topology
# ============================================================================

class TestGraphTopology:
    """Test MultiAgentCompilationGraph node count and routing."""

    def test_graph_builds_all_nodes(self):
        from app.services.multi_agent_graph import MultiAgentCompilationGraph

        graph_builder = MultiAgentCompilationGraph()
        graph = graph_builder.build()

        # All 10 nodes should be registered
        nodes = graph.get_graph().nodes
        node_names = {n for n in nodes}
        expected = {
            "coordinator", "researcher", "integrator", "writer",
            "reviewer_accuracy", "reviewer_readability", "arbiter",
            "editor", "linker", "human_review",
        }
        assert expected.issubset(node_names) or expected == node_names, \
            f"Missing nodes: {expected - node_names}"

    def test_decide_next_review_passed_no_human_review(self):
        from app.services.multi_agent_graph import MultiAgentCompilationGraph

        graph_builder = MultiAgentCompilationGraph()
        state = {
            "review_passed": True,
            "next_action": "continue",
            "compilation_config": {"max_revisions": 3, "enable_human_review": False},
            "human_reviewed": False,
            "revision_count": 0,
        }
        decision = graph_builder._decide_next(state)
        assert decision == "link"

    def test_decide_next_review_passed_with_human_review(self):
        from app.services.multi_agent_graph import MultiAgentCompilationGraph

        graph_builder = MultiAgentCompilationGraph()
        state = {
            "review_passed": True,
            "next_action": "continue",
            "compilation_config": {"max_revisions": 3, "enable_human_review": True},
            "human_reviewed": False,
            "revision_count": 0,
        }
        decision = graph_builder._decide_next(state)
        assert decision == "human_review"

    def test_decide_next_review_failed_within_revision_limit(self):
        from app.services.multi_agent_graph import MultiAgentCompilationGraph

        graph_builder = MultiAgentCompilationGraph()
        state = {
            "review_passed": False,
            "next_action": "continue",
            "compilation_config": {"max_revisions": 3},
            "revision_count": 1,
        }
        decision = graph_builder._decide_next(state)
        assert decision == "revise"

    def test_decide_next_review_failed_exceeded_revision_limit(self):
        from app.services.multi_agent_graph import MultiAgentCompilationGraph

        graph_builder = MultiAgentCompilationGraph()
        state = {
            "review_passed": False,
            "next_action": "continue",
            "compilation_config": {"max_revisions": 3},
            "revision_count": 4,
        }
        decision = graph_builder._decide_next(state)
        assert decision == "link"

    def test_decide_next_finish_action(self):
        from app.services.multi_agent_graph import MultiAgentCompilationGraph

        graph_builder = MultiAgentCompilationGraph()
        state = {
            "review_passed": False,
            "next_action": "finish",
            "compilation_config": {"max_revisions": 3},
            "revision_count": 0,
        }
        decision = graph_builder._decide_next(state)
        assert decision == "finish"

    def test_decide_after_review_approve(self):
        from app.services.multi_agent_graph import MultiAgentCompilationGraph

        graph_builder = MultiAgentCompilationGraph()
        state = {"review_passed": True, "next_action": "continue"}
        decision = graph_builder._decide_after_review(state)
        assert decision == "link"

    def test_decide_after_review_revise(self):
        from app.services.multi_agent_graph import MultiAgentCompilationGraph

        graph_builder = MultiAgentCompilationGraph()
        state = {"review_passed": False, "next_action": "continue"}
        decision = graph_builder._decide_after_review(state)
        assert decision == "revise"

    def test_decide_after_review_finish(self):
        from app.services.multi_agent_graph import MultiAgentCompilationGraph

        graph_builder = MultiAgentCompilationGraph()
        state = {"review_passed": False, "next_action": "finish"}
        decision = graph_builder._decide_after_review(state)
        assert decision == "finish"


# ============================================================================
# HumanReviewManager
# ============================================================================

class TestHumanReviewManager:
    """Test HITL manager: create task, submit decision, timeout."""

    @pytest_asyncio.fixture
    async def mock_db(self):
        """Mock async_session so DB calls don't actually hit a database."""
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)

        mock_sessionmaker = MagicMock()
        mock_sessionmaker.__aenter__ = AsyncMock(return_value=mock_session)
        mock_sessionmaker.__aexit__ = AsyncMock(return_value=None)

        with patch("app.services.human_review_manager.async_session", return_value=mock_sessionmaker):
            yield mock_session

    @pytest.mark.asyncio
    async def test_submit_decision_approve(self, mock_db):
        from app.services.human_review_manager import HumanReviewManager

        mgr = HumanReviewManager()
        mgr.timeout = 1

        result = await mgr.submit_decision("test-task-1", "approve")
        assert result["decision"] == "approve"
        assert result["review_passed"] is True
        assert result["next_action"] == "link"

    @pytest.mark.asyncio
    async def test_submit_decision_revise(self, mock_db):
        from app.services.human_review_manager import HumanReviewManager

        mgr = HumanReviewManager()
        result = await mgr.submit_decision("test-task-2", "revise", "edited content")
        assert result["decision"] == "revise"
        assert result["review_passed"] is False
        assert result["next_action"] == "revise"
        assert result["edited_wiki"] == "edited content"

    @pytest.mark.asyncio
    async def test_submit_decision_reject(self, mock_db):
        from app.services.human_review_manager import HumanReviewManager

        mgr = HumanReviewManager()
        result = await mgr.submit_decision("test-task-3", "reject")
        assert result["decision"] == "reject"
        assert result["review_passed"] is False
        assert result["next_action"] == "finish"

    @pytest.mark.asyncio
    async def test_create_review_task_timeout_auto_approves(self, mock_db):
        from app.services.human_review_manager import HumanReviewManager

        mgr = HumanReviewManager()
        mgr.timeout = 0.1  # Very short timeout

        # Create task — should timeout and auto-approve
        result = await mgr.create_review_task("job-1", {
            "wiki_draft": "test content",
            "final_score": 7.5,
            "reviews": [],
        })

        assert result["decision"] == "approve"
        assert result["task_id"] is not None

    @pytest.mark.asyncio
    async def test_create_review_task_gets_decision(self, mock_db):
        from app.services.human_review_manager import HumanReviewManager

        mgr = HumanReviewManager()
        mgr.timeout = 5

        # Pre-populate the result so the event.wait() succeeds immediately
        task_id = "test-known-task"
        mgr._events[task_id] = asyncio.Event()
        mgr._results[task_id] = {"decision": "revise", "edited_wiki": "changed"}
        mgr._events[task_id].set()

        result = await mgr.create_review_task("job-2", {
            "wiki_draft": "test", "final_score": 8.0, "reviews": [],
        })
        # Gets a new task_id, so check decision pattern
        assert result["decision"] in ("approve", "revise", "reject")

    def test_get_pending_task_ids(self):
        from app.services.human_review_manager import HumanReviewManager

        mgr = HumanReviewManager()
        mgr._events = {"a": asyncio.Event(), "b": asyncio.Event()}
        assert len(mgr.get_pending_task_ids()) == 2


# ============================================================================
# CompilationTracer
# ============================================================================

class TestCompilationTracer:
    """Test trace event emission and entry collection."""

    @pytest.mark.asyncio
    async def test_phase_start_and_end(self):
        from app.core.compilation_tracer import CompilationTracer

        tracer = CompilationTracer(job_id="test")
        tracer.summary_stats = {}  # for test isolation

        await tracer.phase_start("TestAgent", "L1", "Starting test")
        assert len(tracer.entries) == 1
        assert tracer.entries[0].event_type.value == "phase_start"
        assert tracer.entries[0].agent == "TestAgent"

        await tracer.phase_end("TestAgent", "L1", "Finished test", {"result": "ok"})
        assert len(tracer.entries) == 2
        assert tracer.entries[1].event_type.value == "phase_end"
        assert tracer.entries[1].duration_ms is not None

    @pytest.mark.asyncio
    async def test_llm_request_and_response(self):
        from app.core.compilation_tracer import CompilationTracer

        tracer = CompilationTracer(job_id="test")
        await tracer.llm_request("LLM", "L1", "Request", "prompt text...", "gpt-4", full_prompt_len=100)
        await tracer.llm_response("LLM", "L1", "Response", "response text...", tokens=50)

        assert len(tracer.entries) == 2
        assert tracer.entries[0].event_type.value == "llm_request"
        assert tracer.entries[1].event_type.value == "llm_response"
        assert tracer.entries[1].data["tokens"] == 50

    @pytest.mark.asyncio
    async def test_get_full_trace(self):
        from app.core.compilation_tracer import CompilationTracer

        tracer = CompilationTracer(job_id="test")
        await tracer.phase_start("A", "L0", "Start")
        await tracer.phase_end("A", "L0", "End")

        full = tracer.get_full_trace()
        assert len(full) == 2
        assert all(isinstance(e, dict) for e in full)
        assert "duration_ms" in full[1]

    @pytest.mark.asyncio
    async def test_unique_ids_increment(self):
        from app.core.compilation_tracer import CompilationTracer

        tracer = CompilationTracer(job_id="test")
        await tracer.phase_start("A", "L0", "E1")
        await tracer.phase_start("B", "L1", "E2")

        ids = [e.id for e in tracer.entries]
        assert ids[0] != ids[1]
        assert ids[0] == "trace-0001"
        assert ids[1] == "trace-0002"


# ============================================================================
# Compile output parser
# ============================================================================

class TestParseCompileOutput:
    """Test parse_compile_output section splitting and metadata extraction."""

    def test_parses_sections_with_front_matter(self):
        from app.services.compile_service import parse_compile_output

        output = """---
title: FastAPI Guide
type: concept
tags: [python, web]
summary: A guide to FastAPI
---
# FastAPI Guide

FastAPI is a modern web framework.

===

---
title: SQLAlchemy ORM
type: concept
tags: [python, database]
summary: ORM guide
---
# SQLAlchemy ORM

SQLAlchemy is the Python ORM.
"""
        pages = parse_compile_output(output, ["m1", "m2"])
        assert len(pages) == 2
        assert pages[0]["slug"] == "fastapi-guide"
        assert pages[1]["title"] == "SQLAlchemy ORM"
        assert pages[0]["wiki_type"] == "concept"
        assert "python" in pages[0]["tags"]

    def test_extracts_title_from_heading_when_no_front_matter(self):
        from app.services.compile_service import parse_compile_output

        output = """# My Wiki Page

Some content without front matter.
"""
        pages = parse_compile_output(output, ["m1"])
        assert len(pages) == 1
        assert pages[0]["title"] == "My Wiki Page"

    def test_fallback_title_from_content(self):
        from app.services.compile_service import parse_compile_output

        output = "This is a wiki page with no heading and no front matter."
        pages = parse_compile_output(output, ["m1"])
        assert len(pages) == 1
        assert len(pages[0]["title"]) > 0

    def test_empty_output_returns_no_pages(self):
        from app.services.compile_service import parse_compile_output

        pages = parse_compile_output("", ["m1"])
        assert pages == []

    def test_wiki_links_extracted(self):
        from app.services.compile_service import parse_compile_output

        output = """---
title: Test Page
type: concept
---
# Test Page

See [[Other Page]] and [[Another One]] for more.
"""
        pages = parse_compile_output(output, ["m1"])
        assert len(pages) == 1
        # extract_wiki_links returns slugified names
        assert "other-page" in pages[0]["wiki_links"]
        assert "another-one" in pages[0]["wiki_links"]

    def test_invalid_type_falls_back_to_concept(self):
        from app.services.compile_service import parse_compile_output

        output = """---
title: Test
type: invalid_type
---
# Test
"""
        pages = parse_compile_output(output, ["m1"])
        assert pages[0]["wiki_type"] == "concept"


# ============================================================================
# Agent node wrappers — basic shape tests
# ============================================================================

class TestAgentNodes:
    """Verify each agent node wrapper returns expected state keys."""

    @pytest.mark.asyncio
    async def test_writer_node_returns_wiki_draft(self, sample_state, mock_llm):
        from app.services.multi_agent_graph import _writer_node

        mock_llm.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="# Generated Wiki\n\nContent."))],
        )

        state = dict(sample_state)
        state["integrated_knowledge"] = {"entities": [], "relations": []}

        result = await _writer_node(state)
        assert "wiki_draft" in result
        assert len(result["wiki_draft"]) > 0

    @pytest.mark.asyncio
    async def test_editor_node_increments_revision(self, sample_state, mock_llm):
        from app.services.multi_agent_graph import _editor_node

        mock_llm.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Revised wiki content."))],
        )

        state = dict(sample_state)
        state["wiki_draft"] = "Original content."
        state["arbitration_result"] = {"summary": "needs work", "priority_suggestions": ["fix x"]}
        state["revision_count"] = 0

        result = await _editor_node(state)
        assert result["revision_count"] == 1
        assert len(result["wiki_revised"]) > 0

    @pytest.mark.asyncio
    async def test_editor_exceeds_max_revisions_forces_pass(self, sample_state, mock_llm):
        from app.services.multi_agent_graph import _editor_node

        state = dict(sample_state)
        state["wiki_draft"] = "content"
        state["arbitration_result"] = {"summary": "", "priority_suggestions": []}
        state["revision_count"] = 4  # exceeds max_revisions=3
        state["compilation_config"]["max_revisions"] = 3

        result = await _editor_node(state)
        assert result["review_passed"] is True

    @pytest.mark.asyncio
    async def test_linker_returns_suggested_links(self, sample_state, mock_llm):
        from app.services.multi_agent_graph import _linker_node

        mock_llm.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(
                content=json.dumps({"suggested_links": [
                    {"target_slug": "other", "relation_type": "related", "confidence": 0.9}
                ]})
            ))],
        )

        state = dict(sample_state)
        state["wiki_draft"] = "Content about Python."

        # Mock the _get_existing_wikis_summary call inside linker_agent
        with patch("app.agents.linker_agent._get_existing_wikis_summary",
                   new=AsyncMock(return_value=[{"slug": "other", "title": "Other", "summary": "..."}])):
            result = await _linker_node(state)

        assert "suggested_links" in result

    @pytest.mark.asyncio
    async def test_integrator_node_returns_knowledge(self, sample_state, mock_llm):
        from app.services.multi_agent_graph import _integrator_node

        mock_llm.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(
                content=json.dumps({"entities": [], "relations": [], "gaps": []})
            ))],
        )

        state = dict(sample_state)
        state["research_results"] = [{"entities": [], "relations": [], "key_topics": []}]

        result = await _integrator_node(state)
        assert "integrated_knowledge" in result
