"""Sanitize error messages before exposing them to clients."""

import re

# Patterns that may leak secrets or internal details
_SECRET_PATTERNS = [
    (re.compile(r'(sk-[a-zA-Z0-9]{8,})'), 'sk-***'),
    (re.compile(r'(Bearer\s+[a-zA-Z0-9._-]{8,})', re.IGNORECASE), 'Bearer ***'),
    (re.compile(r'(api[_-]?key\s*[=:]\s*["\']?[a-zA-Z0-9]{8,})', re.IGNORECASE), 'api_key=***'),
    (re.compile(r'(token\s*[=:]\s*["\']?[a-zA-Z0-9]{8,})', re.IGNORECASE), 'token=***'),
    (re.compile(r'(https?://[^\s:/]+:[^\s@/]+@)'), 'https://***:***@'),
]

_MAX_MSG_LEN = 500


def sanitize_error_message(msg: str) -> str:
    """Mask potential secrets (API keys, tokens, credentials) in error messages."""
    sanitized = msg
    for pattern, replacement in _SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    if len(sanitized) > _MAX_MSG_LEN:
        sanitized = sanitized[:_MAX_MSG_LEN] + "...(truncated)"
    return sanitized
