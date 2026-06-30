"""Shared prompt loading utility for agent modules."""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "multi_agent"


def load_prompt(name: str) -> str:
    """Load a prompt template from the multi_agent prompts directory."""
    path = PROMPTS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def safe_substitute(template: str, **replacements: str) -> str:
    """Replace ``{placeholder}`` tokens in ``template`` with given values.

    Uses ``str.replace`` instead of ``str.format`` so that curly braces
    inside user-supplied content (code snippets, JSON examples, prompt
    injection attempts) cannot raise ``KeyError``/``IndexError`` and
    crash the agent pipeline. Only the named placeholders listed in
    ``replacements`` are substituted; any other ``{...}`` in the template
    is left intact.
    """
    result = template
    for key, value in replacements.items():
        result = result.replace("{" + key + "}", value)
    return result


def strip_json_fence(raw: str) -> str:
    """Strip a leading ```json (or bare ```) fence and trailing ``` from an
    LLM response so it can be parsed by ``json.loads``.

    P2-23: this logic was duplicated verbatim in 6 agent files
    (arbiter/reviewer/integrator/linker/researcher). Centralizing it keeps
    the fence-stripping rule consistent — e.g. if we ever need to handle
    ```json\\n vs ```\\n differently, there's one place to change.
    """
    text = raw.strip()
    if text.startswith("```"):
        # Drop the opening fence line (``` or ```json) and the closing ```
        text = text.split("\n", 1)[1].rsplit("\n```", 1)[0]
    return text
