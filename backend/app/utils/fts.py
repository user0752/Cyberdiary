"""Shared FTS5 query sanitization for SQLite full-text search."""

import re


def sanitize_fts5_query(query: str) -> str:
    """Sanitize user input for SQLite FTS5 MATCH queries.

    Strips FTS5 operators and special characters that could cause
    syntax errors or unintended matching behavior.
    """
    # Remove FTS5 column filters like "title :"
    query = re.sub(r'\w+\s*:', '', query)
    # Remove FTS5 operators
    query = re.sub(r'\b(AND|OR|NOT|NEAR)\b', '', query, flags=re.IGNORECASE)
    # Remove special characters that FTS5 interprets as operators
    query = re.sub(r'[*"()^:{}]', ' ', query)
    # Collapse whitespace and strip
    query = ' '.join(query.split())
    return query
