import asyncio
import time
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    pass


class CircuitBreaker:
    """Per-process circuit breaker for agent LLM calls.

    NOTE: State is held in-process only. In multi-instance deployments
    (gunicorn -w N, or horizontal scaling), each worker maintains its
    own breaker state — a breaker OPEN on worker A does not prevent
    worker B from calling the same agent. For cross-instance coordination,
    migrate the failure counter and OPEN timestamp to Redis. This is
    acceptable for the current single-process deployment model.
    """

    def __init__(self, name, failure_threshold=3, recovery_timeout=60.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        # Serializes state transitions across concurrent coroutines so that
        # only one request is admitted in HALF_OPEN (the core CB invariant).
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        # --- Admission check under lock ---
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpenError(
                        f"CircuitBreaker [{self.name}] is OPEN"
                    )
            # Snapshot state for the success/failure handler below.
            admitted_state = self.state

        # --- Execute outside the lock (don't block other callers) ---
        try:
            result = await func(*args, **kwargs)
        except Exception:
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if (self.state == CircuitState.HALF_OPEN
                        or self.failure_count >= self.failure_threshold):
                    self.state = CircuitState.OPEN
            raise

        # --- Success path under lock ---
        async with self._lock:
            self.failure_count = 0
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
        return result
