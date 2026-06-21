import asyncio
import hashlib
import json
import os
import time
import aiosqlite
from collections import OrderedDict

from app.core.redis import get_redis


class LLMCache:
    def __init__(self, db_path="./data/llm_cache.db", memory_size=100, ttl=86400):
        self.memory = OrderedDict()
        self.memory_size = memory_size
        self.ttl = ttl
        self.db_path = os.path.expanduser(db_path)
        self.stats = {"mem": 0, "disk": 0, "miss": 0}
        self._conn = None
        # Serializes connection init and all DB writes so that concurrent
        # coroutines cannot (a) create duplicate aiosqlite connections or
        # (b) trigger SQLite "database is locked" by interleaved writes.
        self._lock = asyncio.Lock()

    def _make_key(self, prompt, model, kw):
        try:
            kw_str = json.dumps(kw, sort_keys=True)
        except (TypeError, ValueError):
            kw_str = repr(kw)
        return hashlib.sha256(
            f"{prompt}|{model}|{kw_str}".encode()
        ).hexdigest()

    async def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute(
            "CREATE TABLE IF NOT EXISTS llm_cache("
            "cache_key TEXT PRIMARY KEY, prompt_hash TEXT, model TEXT, "
            "response TEXT, created_at REAL)"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_ts ON llm_cache(created_at)"
        )
        await self._conn.commit()

    async def _ensure_db(self):
        """Must be called while holding self._lock."""
        need_init = False
        if self._conn is None:
            need_init = True
        else:
            try:
                await self._conn.execute("SELECT 1")
            except Exception:
                need_init = True
        if need_init:
            await self._init_db()

    async def get(self, prompt, model, **kw):
        redis = get_redis()
        if redis is not None:
            key = self._make_key(prompt, model, kw)
            v = await redis.get(f"llm:cache:{key}")
            if v is not None:
                self.stats["disk"] += 1
                return v
            self.stats["miss"] += 1
            return None
        async with self._lock:
            await self._ensure_db()
            key = self._make_key(prompt, model, kw)
            if key in self.memory:
                v, ts = self.memory[key]
                if time.time() - ts < self.ttl:
                    self.memory.move_to_end(key)
                    self.stats["mem"] += 1
                    return v
                del self.memory[key]
            cur = await self._conn.execute(
                "SELECT response, created_at FROM llm_cache WHERE cache_key=?", (key,)
            )
            row = await cur.fetchone()
            if row and time.time() - row[1] < self.ttl:
                self.memory[key] = (row[0], row[1])
                self.stats["disk"] += 1
                return row[0]
            self.stats["miss"] += 1
            return None

    async def set(self, prompt, model, response, **kw):
        redis = get_redis()
        if redis is not None:
            key = self._make_key(prompt, model, kw)
            await redis.set(f"llm:cache:{key}", response, ex=self.ttl)
            return
        async with self._lock:
            await self._ensure_db()
            key = self._make_key(prompt, model, kw)
            ts = time.time()
            ph = hashlib.sha256(prompt.encode()).hexdigest()
            self.memory[key] = (response, ts)
            while len(self.memory) > self.memory_size:
                self.memory.popitem(last=False)
            await self._conn.execute(
                "INSERT OR REPLACE INTO llm_cache VALUES(?,?,?,?,?)",
                (key, ph, model, response, ts),
            )
            await self._conn.commit()

    def get_stats(self) -> dict:
        """Return cache hit rate and usage statistics for monitoring."""
        total = self.stats["mem"] + self.stats["disk"] + self.stats["miss"]
        hit_rate = round((self.stats["mem"] + self.stats["disk"]) / max(total, 1) * 100, 1)
        return {
            "memory_hits": self.stats["mem"],
            "disk_hits": self.stats["disk"],
            "misses": self.stats["miss"],
            "total_queries": total,
            "hit_rate_pct": hit_rate,
            "memory_size": self.memory_size,
            "memory_used": len(self.memory),
            "ttl_seconds": self.ttl,
        }

    async def close(self):
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
