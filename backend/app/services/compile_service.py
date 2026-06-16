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
from app.models.compile_job import CompileJob
from app.models.memo import Memo
from app.models.wiki import WikiLink, WikiPage
from app.services import llm_service
from app.services import wiki_service
from app.utils.markdown import slugify, parse_front_matter, extract_wiki_links

# In-memory progress tracker for SSE streaming
# Key: job_id, Value: dict with status, progress, message, output
_compile_progress: dict[str, dict] = {}
# asyncio.Lock (not threading.Lock) — all accesses happen inside the event
# loop. Using a threading.Lock in async code risks blocking the loop and
# deadlocks once run_in_executor / thread-pool dispatch is introduced.
_progress_lock = asyncio.Lock()

# TTL for stale progress entries (1 hour)
_PROGRESS_TTL_SECONDS = 3600


async def _gc_stale_progress() -> int:
    """Remove compile progress entries older than _PROGRESS_TTL_SECONDS.

    Returns the number of entries purged.
    """
    now = _time_module.monotonic()
    purged = 0
    async with _progress_lock:
        stale_ids = [
            jid for jid, entry in _compile_progress.items()
            if now - entry.get('_created_at', 0) > _PROGRESS_TTL_SECONDS
        ]
        for jid in stale_ids:
            del _compile_progress[jid]
            purged += 1
    if purged:
        logging.getLogger(__name__).debug(
            "_gc_stale_progress: purged %d stale entries", purged,
        )
    return purged

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def get_progress(job_id: str) -> dict | None:
    """Get current progress for a compile job.

    Returns in-memory progress if available (fast path for SSE polling).
    Returns None if not found in memory — callers should fall back to DB.
    """
    return _compile_progress.get(job_id)


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


async def _safe_progress_update(job_id: str, **kwargs):
    """Async-safe progress update under asyncio.Lock.

    Updates both the in-memory cache and the database so that progress
    survives process restarts.

    Calls _gc_stale_progress before acquiring the lock to clean up
    completed/failed entries older than the TTL.
    """
    await _gc_stale_progress()
    async with _progress_lock:
        if job_id in _compile_progress:
            _compile_progress[job_id].update(**kwargs)

    # Persist key fields to database (best-effort, non-blocking)
    _db_fields = {}
    if 'status' in kwargs:
        _db_fields['status'] = kwargs['status']
    if 'progress' in kwargs:
        _db_fields['progress'] = kwargs['progress']
    if 'message' in kwargs and 'status' in kwargs and kwargs['status'] in ('done', 'failed'):
        # Store message as result_summary/error_msg for terminal states
        if kwargs['status'] == 'done':
            _db_fields['result_summary'] = kwargs['message']
        elif kwargs['status'] == 'failed':
            _db_fields['error_msg'] = kwargs['message']

    if _db_fields:
        try:
            async with async_session() as db:
                await db.execute(
                    update(CompileJob)
                    .where(CompileJob.id == job_id)
                    .values(**_db_fields)
                )
                await db.commit()
        except Exception:
            pass  # DB write is best-effort; in-memory cache is the primary source


def _parse_compile_output(output: str, source_memo_ids: list[str]) -> list[dict]:
    """Parse LLM compile output into structured wiki page dicts.

    Attempts JSON parsing first (preferred structured format):
      {"pages": [{"slug": "...", "title": "...", "content": "...",
                   "summary": "...", "tags": [...]}]}
    Falls back to legacy ``===``-separated format with YAML front matter.
    """
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


async def _do_compile(job_id: str, memo_ids: list[str] | None, model_id: str):
    """Background compile task. Uses its own DB session.

    All business operations (wiki page saves, link creation, memo marking)
    are performed within a single transaction so that a failure at any
    point rolls back *all* partial writes, preventing data inconsistency.
    """
    progress = _compile_progress.setdefault(job_id, {
        'status': 'running', 'progress': 0, 'message': 'Starting...',
        '_created_at': _time_module.monotonic(),
    })

    try:
        async with async_session() as db:
            async with db.begin():
                # Update job status
                job = (await db.execute(
                    select(CompileJob).where(CompileJob.id == job_id)
                )).scalar_one_or_none()
                if not job:
                    return
                job.status = 'running'
                job.started_at = datetime.now(timezone.utc)

                # Get memos
                if memo_ids:
                    result = await db.execute(
                        select(Memo).where(Memo.id.in_(memo_ids))
                    )
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
                            progress['message'] = f'Resetting {len(orphaned)} orphaned memos...'
                            await db.execute(
                                update(Memo)
                                .where(Memo.id.in_([m.id for m in orphaned]))
                                .values(compiled=False, updated_at=datetime.now(timezone.utc))
                            )
                            memos = await get_uncompiled_memos(db)

                if not memos:
                    progress.update(status='done', progress=100, message='No uncompiled memos found')
                    job.status = 'done'
                    job.result_summary = 'No uncompiled memos found'
                    job.finished_at = datetime.now(timezone.utc)
                    return

                actual_memo_ids = [m.id for m in memos]
                progress['message'] = f'Compiling {len(memos)} memos...'
                progress['progress'] = 10

                # Build prompt
                memo_content = '\n\n---\n\n'.join([
                    f'### Memo {i+1}\n{m.content}' for i, m in enumerate(memos)
                ])

                system_prompt_path = PROMPTS_DIR / 'compile_system.md'
                user_template_path = PROMPTS_DIR / 'compile_user.md'
                system_prompt = system_prompt_path.read_text(encoding='utf-8')
                user_template = user_template_path.read_text(encoding='utf-8')
                user_prompt = user_template.format(
                    memo_count=len(memos),
                    memo_content=memo_content,
                )

                # Get model config
                model_config = await llm_service.get_model_config_from_db(db, model_id)
                if not model_config:
                    raise ValueError(f'Model {model_id} not configured')

                progress['message'] = 'Calling LLM...'
                progress['progress'] = 20

                # Call LLM with streaming
                messages = [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ]

                full_output = ''
                chunk_count = 0
                response = await llm_service.chat_completion(model_config, messages, stream=True)

                async for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        token = chunk.choices[0].delta.content
                        full_output += token
                        chunk_count += 1
                        if chunk_count % 20 == 0:
                            progress['progress'] = min(20 + (chunk_count // 20) * 2, 70)
                            progress['message'] = f'Generating... ({len(full_output)} chars)'

                progress.update(progress=75, message='Parsing output...')

                # Parse output into wiki pages
                pages = _parse_compile_output(full_output, actual_memo_ids)

                if not pages:
                    preview = full_output[:100].replace('\n', '\\n') if full_output else '(empty)'
                    raise ValueError(
                        f'LLM output could not be parsed into wiki pages. '
                        f'Raw output preview (first 100 chars): {preview}'
                    )

                progress['message'] = f'Saving {len(pages)} wiki pages...'
                progress['progress'] = 80

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
                tag_to_slugs: dict[str, list[str]] = {}
                for p in pages:
                    for tag in p['tags']:
                        tag_to_slugs.setdefault(tag, []).append(p['slug'])

                # Collect all link pairs that need to be created
                link_pairs_to_create: list[tuple[str, str]] = []
                for tag, slugs in tag_to_slugs.items():
                    if len(slugs) < 2:
                        continue
                    for i in range(len(slugs)):
                        for j in range(i + 1, len(slugs)):
                            link_pairs_to_create.append((slugs[i], slugs[j]))
                            link_pairs_to_create.append((slugs[j], slugs[i]))

                # Also link new pages to existing pages that share tags
                existing_pages_by_tag: dict[str, list[str]] = {}
                if tag_to_slugs:
                    all_tags = list(tag_to_slugs.keys())
                    for tag in all_tags:
                        existing_result = await db.execute(
                            select(WikiPage.slug).where(
                                WikiPage.tags.like(f'%"{tag}"%'),
                                WikiPage.slug.notin_(new_slugs),
                            )
                        )
                        existing_pages_by_tag[tag] = [row[0] for row in existing_result.all()]
                        for new_slug in tag_to_slugs[tag]:
                            for ext_slug in existing_pages_by_tag[tag]:
                                link_pairs_to_create.append((new_slug, ext_slug))
                                link_pairs_to_create.append((ext_slug, new_slug))

                # Batch check existing links
                if link_pairs_to_create:
                    from sqlalchemy import or_
                    existing_links_result = await db.execute(
                        select(WikiLink.from_slug, WikiLink.to_slug).where(
                            or_(*[
                                (WikiLink.from_slug == pair[0]) & (WikiLink.to_slug == pair[1])
                                for pair in link_pairs_to_create
                            ])
                        )
                    )
                    existing_link_set = {(row[0], row[1]) for row in existing_links_result.all()}

                    # Insert only new links
                    for from_slug, to_slug in link_pairs_to_create:
                        if (from_slug, to_slug) not in existing_link_set:
                            db.add(WikiLink(from_slug=from_slug, to_slug=to_slug))

                # Mark memos as compiled
                await _mark_memos_compiled(db, actual_memo_ids)

                # Update job
                summary = f'Compiled {len(memos)} memos into {len(pages)} wiki pages'
                job.status = 'done'
                job.result_summary = summary
                job.finished_at = datetime.now(timezone.utc)

                progress.update(status='done', progress=100, message=summary)
            # db.begin() auto-commits on success, auto-rolls back on exception

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        error_msg = str(e)
        logger.exception("Compile job %s failed: %s", job_id, error_msg)
        progress.update(status='failed', progress=0, message=f'Error: {error_msg}')

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
    _compile_progress[job.id] = {
        'status': 'pending',
        'progress': 0,
        'message': 'Queued...',
        '_created_at': _time_module.monotonic(),
    }

    # Launch background task (uses its own DB session)
    task = asyncio.create_task(_do_compile(job.id, memo_ids, model_id))

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
