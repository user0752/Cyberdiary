import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, List, Callable


class TraceEventType(str, Enum):
    PHASE_START = "phase_start"
    PHASE_END = "phase_end"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    DECISION = "decision"
    WARNING = "warning"
    ERROR = "error"
    RESULT = "result"


@dataclass
class TraceEntry:
    id: str
    timestamp: float
    agent: str
    layer: str
    event_type: TraceEventType
    title: str
    detail: Optional[str] = None
    data: Optional[Dict] = None
    duration_ms: Optional[float] = None


class CompilationTracer:
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.entries: List[TraceEntry] = []
        self._seq = 0
        self._phase_starts: Dict[str, float] = {}
        self._sse_cb: Optional[Callable] = None

    def set_sse_callback(self, cb):
        self._sse_cb = cb

    async def _emit(self, entry: TraceEntry):
        self.entries.append(entry)
        try:
            from app.services.compile_service import _compile_progress, _progress_lock
            async with _progress_lock:
                p = _compile_progress.get(self.job_id, {})
                log = p.get("compilation_log", [])
                log.append({
                    "agent": entry.agent,
                    "layer": entry.layer,
                    "event": entry.event_type.value,
                    "title": entry.title,
                })
                p["compilation_log"] = log
                p["current_agent"] = entry.agent
                p["current_layer"] = entry.layer
        except Exception:
            pass
        if self._sse_cb:
            try:
                self._sse_cb(json.dumps({
                    "event": "trace",
                    "data": {
                        "id": entry.id, "timestamp": entry.timestamp,
                        "agent": entry.agent, "layer": entry.layer,
                        "event_type": entry.event_type.value,
                        "title": entry.title, "detail": entry.detail,
                        "data": entry.data, "duration_ms": entry.duration_ms,
                    },
                }, ensure_ascii=False))
            except Exception:
                pass

    def _next_id(self):
        self._seq += 1
        return f"trace-{self._seq:04d}"

    async def phase_start(self, agent, layer, title, detail=None):
        self._phase_starts[agent] = time.time()
        await self._emit(TraceEntry(
            id=self._next_id(), timestamp=time.time(),
            agent=agent, layer=layer, event_type=TraceEventType.PHASE_START,
            title=title, detail=detail,
        ))

    async def phase_end(self, agent, layer, title, data=None):
        start = self._phase_starts.pop(agent, time.time())
        await self._emit(TraceEntry(
            id=self._next_id(), timestamp=time.time(),
            agent=agent, layer=layer, event_type=TraceEventType.PHASE_END,
            title=title, data=data,
            duration_ms=round((time.time() - start) * 1000, 1),
        ))

    async def llm_request(self, agent, layer, title, prompt_preview, model, full_prompt_len=0):
        await self._emit(TraceEntry(
            id=self._next_id(), timestamp=time.time(),
            agent=agent, layer=layer, event_type=TraceEventType.LLM_REQUEST,
            title=title, detail=prompt_preview[:600],
            data={"model": model, "prompt_len": full_prompt_len or len(prompt_preview)},
        ))

    async def llm_response(self, agent, layer, title, preview, tokens=None):
        await self._emit(TraceEntry(
            id=self._next_id(), timestamp=time.time(),
            agent=agent, layer=layer, event_type=TraceEventType.LLM_RESPONSE,
            title=title, detail=preview[:600],
            data={"tokens": tokens},
        ))

    async def decision(self, agent, layer, title, data):
        await self._emit(TraceEntry(
            id=self._next_id(), timestamp=time.time(),
            agent=agent, layer=layer, event_type=TraceEventType.DECISION,
            title=title, data=data,
        ))

    async def warning(self, agent, layer, title, detail=None):
        await self._emit(TraceEntry(
            id=self._next_id(), timestamp=time.time(),
            agent=agent, layer=layer, event_type=TraceEventType.WARNING,
            title=title, detail=detail,
        ))

    def get_full_trace(self):
        return [
            {
                "id": e.id, "timestamp": e.timestamp,
                "agent": e.agent, "layer": e.layer,
                "event_type": e.event_type.value,
                "title": e.title, "detail": e.detail,
                "data": e.data, "duration_ms": e.duration_ms,
            }
            for e in self.entries
        ]
