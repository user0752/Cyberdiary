# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes, plus project-specific guidance for CyberNote.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

## 5. Project Overview

CyberNote (赛博笔记) is a personal "notes + LLM second brain" system. Users write raw notes (Memos) in a timeline flow, then an LLM "compiles" them into structured Wiki pages (Karpathy Wiki paradigm). Users can also chat with an AI assistant that uses the Wiki as context.

Core data flow: **Memo (raw notes) -> Compile Engine (LLM) -> Wiki (structured knowledge) -> Chat (LLM with Wiki context)**

## Development Commands

### Backend (FastAPI)
```bash
cd backend
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend (Vue 3 + Vite)
```bash
cd frontend
npm install
npm run dev       # dev server at http://localhost:5173
npm run build     # production build (vue-tsc + vite build)
```

### Docker Compose (full stack)
```bash
docker compose up --build    # backend :8000 + nginx :8080
```

Vite dev server proxies `/api` requests to `localhost:8000` (configured in `frontend/vite.config.ts`).

## Tech Stack

- **Frontend**: Vue 3 + Vite + TypeScript + Pinia + Vue Router. No UI library — custom CSS with CSS variables (`frontend/src/styles/variables.css`). Markdown editing via CodeMirror 6, rendering via markdown-it + highlight.js.
- **Backend**: Python FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2. LLM calls via LiteLLM. Auth via python-jose (JWT) + bcrypt. API key encryption via cryptography (AES-256-GCM).
- **Database**: SQLite with aiosqlite (dev), PostgreSQL with asyncpg (prod). Same ORM layer. FTS5 virtual tables for full-text search on memos and wiki pages.
- **LLM Providers**: DeepSeek, Qwen (DashScope), Ollama — all routed through LiteLLM via `backend/app/services/llm_service.py`.

## Architecture

### Backend Layered Structure
```
api/v1/       -> Route handlers (thin, delegate to services)
services/     -> Business logic (memo_service, chat_service, llm_service, etc.)
models/       -> SQLAlchemy ORM models
schemas/      -> Pydantic request/response schemas
core/         -> config.py (env vars), database.py (engine/session), security.py (JWT/AES)
prompts/      -> LLM prompt templates as .md files (compile_system, compile_user, chat_system)
api/deps.py   -> FastAPI dependencies (DB session injection, auth)
```

All routers are registered in `app/main.py` with `app.include_router(router, prefix="/api/v1")`. To add a new module: create a router file in `api/v1/`, then register it in `main.py`.

### API Response Convention
All endpoints return: `{"code": 0, "message": "ok", "data": ...}`. Errors use `code: -1` or HTTP status codes (400/401/404/500).

### Database Session Pattern
`api/deps.py::get_db()` yields an `AsyncSession` per request with auto-commit on success, rollback on exception. This is the standard FastAPI dependency used by all route handlers.

### FTS5 Full-Text Search
`core/database.py::init_db()` creates FTS5 virtual tables (`memos_fts`, `wiki_fts`) and SQLite triggers to keep them in sync. This runs on app startup via the lifespan context manager.

### Auth Modes
Controlled by `AUTH_MODE` env var. `"none"` disables auth entirely (single-user local mode). `"jwt"` enables Bearer token auth. See `api/deps.py::get_current_user`.

### LLM Integration
`services/llm_service.py` is the single entry point for all LLM calls. Model configs are stored encrypted in the `settings` DB table (key `"models"`) and loaded at call time. `build_litellm_kwargs()` translates provider-specific config into LiteLLM call parameters.

### Frontend Pattern
- **API layer** (`src/api/*.ts`): thin fetch/axios wrappers per domain (memo, chat, model). Return typed data.
- **Stores** (`src/stores/*.ts`): Pinia composition-API stores. Each store wraps the corresponding API module and manages UI state.
- **Views** (`src/views/*.vue`): page-level components (MemoFlow, WikiHub, WikiPage, ChatView, Settings).
- **Components** (`src/components/*.vue`): reusable pieces (MarkdownEditor, MarkdownRenderer, ChatWindow).
- Layout: fixed sidebar (App.vue) + main content area via `<RouterView />`.

### SSE Streaming
Chat and compile use Server-Sent Events. Frontend parses SSE via `ReadableStream` reader (see `frontend/src/api/chat.ts::chatStream`). Nginx config disables `proxy_buffering` for SSE support.

### Compile Engine
The LLM compile pipeline reads uncompiled memos (`compiled=false`), assembles prompts from `backend/app/prompts/`, calls the LLM, parses output into Wiki pages with YAML front matter (TheSchema spec), writes to DB + local `.md` files, and marks memos as compiled. Compile jobs are tracked in `compile_jobs` table with SSE progress streaming.

### Wiki Page Types
`concept | entity | comparison | synthesis | source` — defined in the compile prompt template (`prompts/compile_system.md`).

### Bidirectional Links
Wiki pages use `[[Page Name]]` syntax. Parsed on the frontend by a markdown-it plugin. The `wiki_links` table stores the graph edges (from_slug -> to_slug).

## Key Environment Variables
See `backend/.env.example`. Notable: `DATABASE_URL`, `SECRET_KEY`, `AUTH_MODE`, `OLLAMA_BASE_URL`.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
