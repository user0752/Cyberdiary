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
