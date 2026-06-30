"""Compile service - LLM-powered note compilation into structured Wiki pages."""

import asyncio
import json
import logging
import re
import time as _time_module
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.progress_store import (
    get_progress as _get_progress,
    init_progress,
    update_progress,
    gc_stale_progress,
)
from app.models.compile_job import CompileJob
from app.models.memo import Memo
from app.models.wiki import WikiLink, WikiPage
from app.services import llm_service
from app.services import wiki_service
from app.services.progress_tracker import safe_progress_update
from app.utils.markdown import slugify, parse_front_matter, extract_wiki_links, normalize_markdown_headings
from app.utils.db import tag_contains
from app.utils.sanitize import sanitize_error_message

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


async def get_progress(job_id: str) -> dict | None:
    """Get current progress for a compile job.

    Returns Redis/in-memory progress if available (fast path for SSE polling).
    Returns None if not found — callers should fall back to DB.
    """
    return await _get_progress(job_id)


async def get_progress_from_db(job_id: str) -> dict | None:
    """Fallback: read progress from the compile_jobs table.

    Used when the in-memory cache has been lost (e.g. process restart)
    so that SSE streams can still report terminal states.
    """
    try:
        async with async_session() as db:
            job = (await db.execute(
                select(CompileJob).where(CompileJob.id == job_id)
            )).scalar_one_or_none()
            if not job:
                return None
            return {
                'status': job.status,
                'progress': job.progress or 0,
                'message': job.result_summary or job.error_msg or '',
            }
    except Exception:
        return None


def parse_compile_output(output: str, source_memo_ids: list[str]) -> list[dict]:
    """Parse LLM compile output into structured wiki page dicts.

    Attempts JSON parsing first (preferred structured format):
      {"pages": [{"slug": "...", "title": "...", "content": "...",
                   "summary": "...", "tags": [...]}]}
    Falls back to legacy ``===``-separated format with YAML front matter.
    """
    # Normalize: split headings jammed onto a single line (LLM artifact)
    # so title extraction and Markdown rendering both work correctly.
    output = normalize_markdown_headings(output)

    # 1) Try JSON parsing first
    try:
        parsed = json.loads(output.strip())
        if isinstance(parsed, dict) and 'pages' in parsed:
            pages = []
            for p in parsed['pages']:
                slug_val = slugify(p.get('title', ''))
                wiki_type = p.get('type', 'concept')
                if wiki_type not in ('concept', 'entity', 'comparison', 'synthesis', 'source'):
                    wiki_type = 'concept'
                tags = p.get('tags', [])
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(',') if t.strip()]
                content = p.get('content', '')
                pages.append({
                    'slug': slug_val,
                    'title': p.get('title', '').strip(),
                    'wiki_type': wiki_type,
                    'content': content,
                    'summary': p.get('summary', ''),
                    'tags': tags,
                    'source_memo_ids': source_memo_ids,
                    'wiki_links': extract_wiki_links(content),
                })
            return pages
    except (json.JSONDecodeError, TypeError, KeyError):
        pass

    # 2) Fallback: legacy ``===``-separated format with YAML front matter
    sections = re.split(r'\n\s*===\s*\n', output.strip())
    pages = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        metadata, content = parse_front_matter(section)
        if not metadata and not content:
            continue

        title = metadata.get('title', '').strip()
        if not title:
            heading_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
            if heading_match:
                title = heading_match.group(1).strip()
            else:
                title = content[:50].strip()

        wiki_type = metadata.get('type', 'concept')
        if wiki_type not in ('concept', 'entity', 'comparison', 'synthesis', 'source'):
            wiki_type = 'concept'

        tags = metadata.get('tags', [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]

        summary = metadata.get('summary', '')
        slug_val = slugify(title)

        # Remove front matter from content if it wasn't cleanly separated
        if content.startswith('---'):
            end_idx = content.find('---', 3)
            if end_idx > 0:
                content = content[end_idx + 3:].strip()

        wiki_links = extract_wiki_links(content)

        pages.append({
            'slug': slug_val,
            'title': title,
            'wiki_type': wiki_type,
            'content': content,
            'summary': summary,
            'tags': tags,
            'source_memo_ids': source_memo_ids,
            'wiki_links': wiki_links,
        })

    return pages


async def get_uncompiled_memos(db: AsyncSession) -> list[Memo]:
    """Get all memos that haven't been compiled yet."""
    result = await db.execute(
        select(Memo)
        .where(Memo.compiled == False, Memo.archived == False)
        .order_by(Memo.created_at.asc())
    )
    return list(result.scalars().all())


async def _mark_memos_compiled(db: AsyncSession, memo_ids: list[str]):
    """Mark memos as compiled."""
    await db.execute(
        update(Memo)
        .where(Memo.id.in_(memo_ids))
        .values(compiled=True, updated_at=datetime.now(timezone.utc))
    )


async def save_compile_results(
    db: AsyncSession,
    pages: list[dict],
    memo_ids: list[str],
    semantic_links: list[dict] | None = None,
) -> list[str]:
    """Save compiled wiki pages, semantic links, and mark memos as compiled.

    Shared by both single-agent and multi-agent compile pipelines.

    Returns the list of saved page slugs.
    """
    # Deduplicate by slug, merging source_memo_ids
    seen_slugs: dict[str, dict] = {}
    for p in pages:
        slug = p['slug']
        if slug in seen_slugs:
            existing_ids = set(seen_slugs[slug]['source_memo_ids'])
            existing_ids.update(p['source_memo_ids'])
            seen_slugs[slug]['source_memo_ids'] = list(existing_ids)
            seen_slugs[slug]['content'] += '\n\n' + p['content']
        else:
            seen_slugs[slug] = p
    pages = list(seen_slugs.values())

    # Save wiki pages
    new_slugs = []
    for page_data in pages:
        await wiki_service.save_wiki_page(
            db,
            slug=page_data['slug'],
            title=page_data['title'],
            wiki_type=page_data['wiki_type'],
            content=page_data['content'],
            summary=page_data['summary'],
            tags=page_data['tags'],
            source_memo_ids=page_data['source_memo_ids'],
            wiki_links=page_data['wiki_links'],
        )
        new_slugs.append(page_data['slug'])

    # Tag-based fallback links: batch query existing links to avoid N+1
    MAX_LINKS_PER_TAG = 20  # Cap slugs per tag to avoid O(N²) pair explosion
    tag_to_slugs: dict[str, list[str]] = {}
    for p in pages:
        for tag in p['tags']:
            tag_to_slugs.setdefault(tag, []).append(p['slug'])

    link_pairs_to_create: list[tuple[str, str]] = []
    for tag, slugs in tag_to_slugs.items():
        if len(slugs) < 2:
            continue
        capped = slugs[:MAX_LINKS_PER_TAG]
        for i in range(len(capped)):
            for j in range(i + 1, len(capped)):
                link_pairs_to_create.append((capped[i], capped[j]))
                link_pairs_to_create.append((capped[j], capped[i]))

    # Link new pages to existing pages that share tags
    if tag_to_slugs:
        for tag in list(tag_to_slugs.keys()):
            existing_result = await db.execute(
                select(WikiPage.slug).where(
                    tag_contains(WikiPage.tags, tag),
                    WikiPage.slug.notin_(new_slugs),
                )
            )
            for ext_slug in [row[0] for row in existing_result.all()]:
                for new_slug in tag_to_slugs[tag][:MAX_LINKS_PER_TAG]:
                    link_pairs_to_create.append((new_slug, ext_slug))
                    link_pairs_to_create.append((ext_slug, new_slug))

    # Batch check existing links via IN clause (avoids OR-chain explosion)
    if link_pairs_to_create:
        # Deduplicate pairs
        unique_pairs = set(link_pairs_to_create)
        all_slugs = {s for pair in unique_pairs for s in pair}
        existing_links_result = await db.execute(
            select(WikiLink.from_slug, WikiLink.to_slug).where(
                WikiLink.from_slug.in_(all_slugs)
            )
        )
        existing_link_set = {(row[0], row[1]) for row in existing_links_result.all()}
        for from_slug, to_slug in unique_pairs:
            if (from_slug, to_slug) not in existing_link_set:
                db.add(WikiLink(from_slug=from_slug, to_slug=to_slug))

    # Save semantic links (multi-agent only)
    if semantic_links:
        from app.models.multi_agent import SemanticLink
        for link in semantic_links:
            if link.get("confidence", 0) >= 0.7:
                source_slug = link.get("source_slug")
                target_slug = link.get("target_slug")
                if source_slug and target_slug:
                    db.add(SemanticLink(
                        source_slug=source_slug,
                        target_slug=target_slug,
                        relation_type=link.get("relation_type", "related"),
                        confidence=link["confidence"],
                        reason=link.get("reason", ""),
                    ))

    # Mark memos as compiled
    await _mark_memos_compiled(db, memo_ids)

    return new_slugs


async def _load_compile_memos(
    db: AsyncSession, job_id: str, memo_ids: list[str] | None,
) -> tuple[list[Memo], list[str]]:
    """Load memos for compilation. Resets orphaned compiled memos if needed.

    Returns (memos, actual_memo_ids). Empty list if no memos to compile.
    """
    if memo_ids:
        result = await db.execute(select(Memo).where(Memo.id.in_(memo_ids)))
        memos = list(result.scalars().all())
    else:
        memos = await get_uncompiled_memos(db)

        # Safety: reset orphaned compiled memos (compiled=True but wiki pages deleted)
        if not memos:
            result = await db.execute(
                select(Memo).where(Memo.compiled == True, Memo.archived == False)
            )
            orphaned = list(result.scalars().all())
            if orphaned:
                await update_progress(job_id, message=f'Resetting {len(orphaned)} orphaned memos...')
                await db.execute(
                    update(Memo)
                    .where(Memo.id.in_([m.id for m in orphaned]))
                    .values(compiled=False, updated_at=datetime.now(timezone.utc))
                )
                memos = await get_uncompiled_memos(db)

    return memos, [m.id for m in memos]


async def _stream_compile_llm(
    job_id: str, model_config: dict, messages: list[dict],
) -> str:
    """Call LLM with streaming and return the full output text."""
    full_output = ''
    chunk_count = 0
    response = await llm_service.chat_completion(model_config, messages, stream=True)

    async for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            token = chunk.choices[0].delta.content
            full_output += token
            chunk_count += 1
            if chunk_count % 20 == 0:
                await update_progress(
                    job_id,
                    progress=min(20 + (chunk_count // 20) * 2, 70),
                    message=f'Generating... ({len(full_output)} chars)',
                )
    return full_output


async def record_compile_failure(job_id: str, error_msg: str) -> None:
    """Mark a compile job as failed in the database (shared by both pipelines)."""
    try:
        async with async_session() as db:
            job = (await db.execute(
                select(CompileJob).where(CompileJob.id == job_id)
            )).scalar_one_or_none()
            if job:
                job.status = 'failed'
                job.error_msg = error_msg
                job.finished_at = datetime.now(timezone.utc)
                await db.commit()
    except Exception:
        logger.exception("Failed to record compile job failure for %s", job_id)


async def _resolve_compile_model(db: AsyncSession, model_id: str) -> dict:
    """Fetch and validate the LLM model config for compilation.  Raises
    ValueError if the model is not configured."""
    model_config = await llm_service.get_model_config_from_db(db, model_id)
    if not model_config:
        raise ValueError(f'Model {model_id} not configured')
    return model_config


def _build_compile_messages(memos: list[Memo]) -> list[dict]:
    """Build the system + user messages for the compilation LLM call.

    Uses str.replace for placeholder substitution instead of str.format so
    that curly braces inside user memo content (e.g. code snippets,
    templating examples) cannot raise KeyError/IndexError and crash the
    whole compile pipeline. The memo content is also wrapped in an
    explicit content fence so the LLM is told to treat it as data, not
    instructions — a basic prompt-injection mitigation.
    """
    memo_content = '\n\n---\n\n'.join([
        f'### Memo {i+1}\n{m.content}' for i, m in enumerate(memos)
    ])
    system_prompt = (PROMPTS_DIR / 'compile_system.md').read_text(encoding='utf-8')
    user_template = (PROMPTS_DIR / 'compile_user.md').read_text(encoding='utf-8')
    # Safe substitution: user content may contain {placeholders} or JSON
    # braces — str.format would crash. Replace named tokens only.
    user_prompt = (
        user_template
        .replace('{memo_count}', str(len(memos)))
        .replace(
            '{memo_content}',
            f'<user_content>\n{memo_content}\n</user_content>',
        )
    )
    return [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt},
    ]


async def _do_compile(job_id: str, memo_ids: list[str] | None, model_id: str):
    """Background compile task. Uses its own DB session.

    All business operations (wiki page saves, link creation, memo marking)
    are performed within a single transaction so that a failure at any
    point rolls back *all* partial writes, preventing data inconsistency.
    """
    await init_progress(job_id, status='running', progress=0, message='Starting...')

    try:
        async with async_session() as db:
            async with db.begin():
                # 1) Load & validate job
                job = (await db.execute(
                    select(CompileJob).where(CompileJob.id == job_id)
                )).scalar_one_or_none()
                if not job:
                    return
                job.status = 'running'
                job.started_at = datetime.now(timezone.utc)

                # 2) Load memos
                memos, actual_memo_ids = await _load_compile_memos(db, job_id, memo_ids)
                if not memos:
                    await update_progress(job_id, status='done', progress=100, message='No uncompiled memos found')
                    job.status = 'done'
                    job.result_summary = 'No uncompiled memos found'
                    job.finished_at = datetime.now(timezone.utc)
                    return

                await update_progress(job_id, message=f'Compiling {len(memos)} memos...', progress=10)

                # 3) Build prompt & resolve model
                messages = _build_compile_messages(memos)
                model_config = await _resolve_compile_model(db, model_id)

                # 4) Call LLM + parse results
                await update_progress(job_id, message='Calling LLM...', progress=20)
                full_output = await _stream_compile_llm(job_id, model_config, messages)

                await update_progress(job_id, progress=75, message='Parsing output...')
                pages = parse_compile_output(full_output, actual_memo_ids)
                if not pages:
                    preview = full_output[:100].replace('\n', '\\n') if full_output else '(empty)'
                    raise ValueError(
                        f'LLM output could not be parsed into wiki pages. '
                        f'Raw output preview (first 100 chars): {preview}'
                    )

                # 5) Persist results
                await update_progress(job_id, message=f'Saving {len(pages)} wiki pages...', progress=80)
                await save_compile_results(db, pages, actual_memo_ids)

                # 6) Finalize job
                summary = f'Compiled {len(memos)} memos into {len(pages)} wiki pages'
                job.status = 'done'
                job.result_summary = summary
                job.finished_at = datetime.now(timezone.utc)
                await update_progress(job_id, status='done', progress=100, message=summary)
            # db.begin() auto-commits on success, auto-rolls back on exception

    except Exception as e:
        raw_msg = str(e)
        logger.exception("Compile job %s failed: %s", job_id, raw_msg)
        error_msg = sanitize_error_message(raw_msg)
        await update_progress(job_id, status='failed', progress=0, message=f'Error: {error_msg}')
        await record_compile_failure(job_id, error_msg)


async def trigger_compile(
    db: AsyncSession,
    memo_ids: list[str] | None,
    model_id: str,
) -> CompileJob:
    """Create a compile job and start it as a background task. Returns the job."""
    job = CompileJob(
        id=str(uuid.uuid4()),
        status='pending',
        memo_ids=json.dumps(memo_ids or [], ensure_ascii=False),
        model_id=model_id,
    )
    db.add(job)
    await db.flush()
    await db.refresh(job)

    # Initialize progress tracker
    await init_progress(
        job.id,
        status='pending', progress=0, message='Queued...',
    )

    # Launch background task (uses its own DB session)
    task = asyncio.create_task(_do_compile(job.id, memo_ids, model_id))

    # Always log uncaught exceptions from background tasks
    def _log_task_exception(t: asyncio.Task) -> None:
        if t.cancelled():
            return
        exc = t.exception()
        if exc:
            logger.exception("Background compile task failed [job_id=%s]: %s", job.id, exc, exc_info=exc)

    task.add_done_callback(_log_task_exception)

    # Register with app state for graceful shutdown (if available)
    try:
        from app.main import app as _app
        if hasattr(_app.state, 'background_tasks'):
            _app.state.background_tasks.add(task)
            task.add_done_callback(_app.state.background_tasks.discard)
    except Exception:
        pass  # running outside FastAPI context (e.g. tests)

    return job


async def list_jobs(db: AsyncSession) -> list[CompileJob]:
    """List all compile jobs, newest first."""
    result = await db.execute(
        select(CompileJob).order_by(CompileJob.created_at.desc())
    )
    return list(result.scalars().all())


async def get_job(db: AsyncSession, job_id: str) -> CompileJob | None:
    """Get a compile job by ID."""
    result = await db.execute(
        select(CompileJob).where(CompileJob.id == job_id)
    )
    return result.scalar_one_or_none()
