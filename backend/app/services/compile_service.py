"""Compile service - LLM-powered note compilation into structured Wiki pages."""

import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.models.compile_job import CompileJob
from app.models.memo import Memo
from app.services import llm_service
from app.services import wiki_service

# In-memory progress tracker for SSE streaming
# Key: job_id, Value: dict with status, progress, message, output
_compile_progress: dict[str, dict] = {}

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def get_progress(job_id: str) -> dict | None:
    """Get current progress for a compile job."""
    return _compile_progress.get(job_id)


def _slugify(text: str) -> str:
    """Generate a URL-friendly slug from text. Falls back to UUID prefix."""
    try:
        from slugify import slugify
        return slugify(text, allow_unicode=False)
    except ImportError:
        pass

    # Simple fallback slugify
    slug = re.sub(r'[^\w\s-]', '', text.lower().strip())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug[:80] or f"page-{uuid.uuid4().hex[:8]}"


def _parse_front_matter(text: str) -> tuple[dict, str]:
    """Parse YAML front matter from markdown text. Returns (metadata, content)."""
    text = text.strip()
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1]) or {}
                content = parts[2].strip()
                return metadata, content
            except yaml.YAMLError:
                pass
    return {}, text


def _extract_wiki_links(content: str) -> list[str]:
    """Extract [[Page Name]] links from content and return as slugs."""
    pattern = r'\[\[([^\]]+)\]\]'
    matches = re.findall(pattern, content)
    slugs = []
    for m in matches:
        slug = _slugify(m.strip())
        if slug:
            slugs.append(slug)
    return list(set(slugs))


def _parse_compile_output(output: str, source_memo_ids: list[str]) -> list[dict]:
    """Parse LLM compile output into structured wiki page dicts.

    Expected format: pages separated by '===', each with YAML front matter.
    """
    sections = re.split(r'\n\s*===\s*\n', output.strip())
    pages = []

    for section in sections:
        section = section.strip()
        if not section:
            continue

        metadata, content = _parse_front_matter(section)
        if not metadata and not content:
            continue

        title = metadata.get('title', '').strip()
        if not title:
            # Try to extract title from first heading
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
        slug = _slugify(title)

        # Remove front matter from content if it wasn't cleanly separated
        if content.startswith('---'):
            end_idx = content.find('---', 3)
            if end_idx > 0:
                content = content[end_idx + 3:].strip()

        wiki_links = _extract_wiki_links(content)

        pages.append({
            'slug': slug,
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
    """Background compile task. Uses its own DB session."""
    progress = _compile_progress.setdefault(job_id, {
        'status': 'running', 'progress': 0, 'message': 'Starting...',
    })

    try:
        async with async_session() as db:
            # Update job status
            job = (await db.execute(
                select(CompileJob).where(CompileJob.id == job_id)
            )).scalar_one_or_none()
            if not job:
                return
            job.status = 'running'
            job.started_at = datetime.now(timezone.utc)
            await db.commit()

            # Get memos
            if memo_ids:
                result = await db.execute(
                    select(Memo).where(Memo.id.in_(memo_ids))
                )
                memos = list(result.scalars().all())
            else:
                memos = await get_uncompiled_memos(db)

            if not memos:
                progress.update(status='done', progress=100, message='No uncompiled memos found')
                job.status = 'done'
                job.result_summary = 'No uncompiled memos found'
                job.finished_at = datetime.now(timezone.utc)
                await db.commit()
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
                raise ValueError('LLM output could not be parsed into wiki pages')

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

            # Mark memos as compiled
            await _mark_memos_compiled(db, actual_memo_ids)

            # Update job
            summary = f'Compiled {len(memos)} memos into {len(pages)} wiki pages'
            job.status = 'done'
            job.result_summary = summary
            job.finished_at = datetime.now(timezone.utc)
            await db.commit()

            progress.update(status='done', progress=100, message=summary)

    except Exception as e:
        error_msg = str(e)
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
            pass


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
    }

    # Launch background task (uses its own DB session)
    asyncio.create_task(_do_compile(job.id, memo_ids, model_id))

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
