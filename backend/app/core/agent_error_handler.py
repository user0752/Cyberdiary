import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from litellm.exceptions import Timeout, RateLimitError, APIConnectionError
from app.core.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

logger = logging.getLogger(__name__)


class AgentErrorHandler:
    def __init__(self):
        self.circuit_breakers = {
            k: CircuitBreaker(k)
            for k in [
                "coordinator", "researcher", "integrator", "writer",
                "reviewer_accuracy", "reviewer_readability",
                "arbiter", "editor", "linker",
            ]
        }

    async def execute(self, agent_name, func, state, fallback_value=None):
        cb = self.circuit_breakers.get(agent_name)
        if cb:
            try:
                return await cb.call(func, state)
            except CircuitBreakerOpenError:
                logger.warning("%s circuit breaker open, using fallback", agent_name)
                return self._fallback(agent_name, state, fallback_value)
            except Exception:
                logger.exception("%s failed with unhandled error, using fallback", agent_name)
                return self._fallback(agent_name, state, fallback_value)

        try:
            return await self._retry(func, state)
        except Exception:
            logger.exception("%s failed after retries, using fallback", agent_name)
            return self._fallback(agent_name, state, fallback_value)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((Timeout, RateLimitError, APIConnectionError)),
    )
    async def _retry(self, func, state):
        return await func(state)

    def _fallback(self, agent, state, fb):
        if fb is not None:
            return fb
        state.setdefault("degraded_agents", [])
        state["degraded_agents"].append(agent)
        if "researcher" in agent:
            state["research_results"] = [{"entities": [], "relations": [], "key_topics": []}]
        if "reviewer" in agent:
            state.setdefault("reviews", [])
            state["reviews"].append({
                "score": 0.0,
                "feedback": "reviewer unavailable (fallback) — quality not verified",
                "fallback": True,
            })
        if agent == "linker":
            state["suggested_links"] = []
        return state
