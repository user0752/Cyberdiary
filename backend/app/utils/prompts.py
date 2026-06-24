"""Shared prompt loading utility for agent modules."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "multi_agent"


def load_prompt(name: str) -> str:
    """Load a prompt template from the multi_agent prompts directory."""
    path = PROMPTS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""
