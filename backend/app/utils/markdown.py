"""Shared markdown utilities — slugify, front matter parsing, wiki link extraction."""

import re
import uuid

import yaml


def slugify(text: str) -> str:
    """Generate a URL-friendly slug from text. Falls back to UUID prefix."""
    try:
        from slugify import slugify as py_slugify
        return py_slugify(text, allow_unicode=False)
    except ImportError:
        pass

    # Simple fallback slugify
    slug = re.sub(r'[^\w\s-]', '', text.lower().strip())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug[:80] or f"page-{uuid.uuid4().hex[:8]}"


def parse_front_matter(text: str) -> tuple[dict, str]:
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


def extract_wiki_links(content: str) -> list[str]:
    """Extract [[Page Name]] links from content and return as slugs."""
    pattern = r'\[\[([^\]]+)\]\]'
    matches = re.findall(pattern, content)
    slugs = []
    for m in matches:
        slug = slugify(m.strip())
        if slug:
            slugs.append(slug)
    return list(set(slugs))


def normalize_markdown_headings(content: str) -> str:
    """Split Markdown headings that are jammed onto a single line.

    Some LLMs (especially under token pressure) emit output like:
        ### 标题A #### 标题B ### 标题C 正文内容...
    where multiple headings share one line. This breaks rendering
    (everything after the first ``###`` becomes part of the first
    heading's text) and breaks title extraction in
    ``compile_service.parse_compile_output``.

    This normalizer splits any line containing multiple ``#``-prefixed
    headings into separate lines, so standard Markdown parsers and the
    ``^#\\s+(.+)`` title regex both work correctly.
    """
    if not content:
        return content

    lines = content.split('\n')
    result = []
    for line in lines:
        # Skip code block delimiters and their content — don't touch
        # heading-like text inside fenced code blocks.
        stripped = line.strip()
        if stripped.startswith('```'):
            result.append(line)
            continue

        # Find all heading tokens on this line: #{1,6} followed by text.
        # A heading must be followed by at least one non-# character.
        # Pattern matches: ### Title text (up to next ### or end of line)
        matches = list(re.finditer(r'(^|\s)(#{1,6})\s+(.+?)(?=\s+#{1,6}\s+|$)', line))
        if len(matches) <= 1:
            # 0 or 1 heading on this line — leave as is. But still
            # ensure a single heading has no leading whitespace from a
            # preceding space (the `^|\s` alternation captures a leading
            # space that we don't want in the output).
            if len(matches) == 1 and matches[0].group(1) == ' ':
                m = matches[0]
                line = line[:m.start()] + line[m.start() + 1:]
            result.append(line)
            continue

        # Multiple headings on one line — split each into its own line.
        for m in matches:
            hashes = m.group(2)
            text = m.group(3).strip()
            result.append(f'{hashes} {text}')

    return '\n'.join(result)
