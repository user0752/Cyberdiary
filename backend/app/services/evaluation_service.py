"""Wiki quality evaluation — heuristic multi-dimensional scoring.

ROUGE-L and BERTScore are stubbed out (require heavy NLP deps).
Structure, readability, and information density use fast heuristics.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.database import async_session

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    wiki_slug: str
    overall: float
    structure: float
    readability: float
    info_density: float
    rouge_l: float = 0.0
    bert_score: float = 0.0
    summary: str = ""
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WikiEvaluationService:

    def evaluate(self, content: str, source_texts: list[str], wiki_slug: str = "") -> EvalResult:
        structure = self._score_structure(content)
        readability = self._score_readability(content)
        info_density = self._score_info_density(content, source_texts)
        rouge_l = self._stub_rouge_l(content, source_texts)
        bert = self._stub_bert_score(content, source_texts)

        overall = round(
            structure * 0.25
            + readability * 0.20
            + info_density * 0.30
            + rouge_l * 0.15
            + bert * 0.10,
            1,
        )

        return EvalResult(
            wiki_slug=wiki_slug,
            overall=overall,
            structure=structure,
            readability=readability,
            info_density=info_density,
            rouge_l=rouge_l,
            bert_score=bert,
            summary=self._summarize(structure, readability, info_density),
        )

    def _score_structure(self, content: str) -> float:
        """Score structural completeness: headings, sections, lists, length."""
        score = 0.0

        # Has at least one heading
        if re.search(r"^#{1,3}\s", content, re.MULTILINE):
            score += 3.0

        # Has multiple sections (2+ headings)
        headings = re.findall(r"^#{1,3}\s", content, re.MULTILINE)
        if len(headings) >= 2:
            score += 2.0

        # Has lists
        if re.search(r"^\s*[-*]\s", content, re.MULTILINE):
            score += 1.5

        # Has table
        if re.search(r"\|.*\|.*\|", content):
            score += 1.0

        # Adequate length (500+ chars)
        if len(content) >= 500:
            score += 1.5
        if len(content) >= 1500:
            score += 1.0

        return min(score, 10.0)

    def _score_readability(self, content: str) -> float:
        """Estimate readability via sentence/word complexity heuristics."""
        sentences = re.split(r"[。.!?\n]+", content)
        sentences = [s.strip() for s in sentences if s.strip()]
        if not sentences:
            return 5.0

        words = content.split()
        if not words:
            return 5.0

        avg_sentence_len = len(words) / len(sentences)

        # Ideal range: 10-25 words per sentence
        score = 7.0
        if avg_sentence_len < 5:
            score -= 2.0  # too choppy
        elif avg_sentence_len > 40:
            score -= 3.0  # too long
        elif avg_sentence_len < 10:
            score -= 1.0
        elif 15 <= avg_sentence_len <= 25:
            score += 1.5

        # Paragraph breaks
        if "\n\n" in content:
            score += 1.0

        # Code blocks (acceptable for tech content)
        if "```" in content:
            score += 0.5

        return min(max(score, 1.0), 10.0)

    def _score_info_density(self, content: str, sources: list[str]) -> float:
        """Score how well the wiki covers source material."""
        score = 5.0

        # Length ratio (wiki vs sources)
        source_len = sum(len(s) for s in sources)
        if source_len > 0:
            ratio = len(content) / source_len
            if 0.3 <= ratio <= 1.5:
                score += 2.0  # good compression ratio
            elif ratio < 0.1:
                score -= 2.0  # too short
            elif ratio > 3.0:
                score -= 1.0  # potentially bloated

        # Key term overlap
        wiki_lower = content.lower()
        source_lower = " ".join(sources).lower()

        # Extract significant words (4+ chars)
        source_terms = set(re.findall(r"\b[a-zA-Z一-鿿]{4,}\b", source_lower))
        if source_terms:
            matched = sum(1 for t in source_terms if t in wiki_lower)
            coverage = matched / len(source_terms)
            if coverage >= 0.5:
                score += 2.0
            elif coverage >= 0.2:
                score += 1.0
            else:
                score -= 1.0

        # Has inline links or references
        if re.search(r"\[\[.+?\]\]", content):
            score += 0.5

        return min(max(score, 1.0), 10.0)

    def _stub_rouge_l(self, content: str, sources: list[str]) -> float:
        """Stub for ROUGE-L recall. Returns 7.0 default."""
        return 7.0

    def _stub_bert_score(self, content: str, sources: list[str]) -> float:
        """Stub for BERTScore. Returns 7.0 default."""
        return 7.0

    def _summarize(self, structure: float, readability: float, density: float) -> str:
        parts = []
        if structure >= 7:
            parts.append("well-structured")
        elif structure < 4:
            parts.append("lacks structure")

        if readability >= 7:
            parts.append("readable")
        elif readability < 4:
            parts.append("hard to read")

        if density >= 7:
            parts.append("good coverage")
        elif density < 4:
            parts.append("thin coverage")

        if not parts:
            return "average quality"
        return "; ".join(parts)


# Singleton
evaluator = WikiEvaluationService()


async def evaluate_wiki_async(slug: str, content: str, source_texts: list[str]):
    """Run evaluation asynchronously. Saves result log."""
    try:
        result = evaluator.evaluate(content, source_texts, slug)
        logger.info(
            "Wiki eval [%s]: overall=%.1f structure=%.1f readability=%.1f density=%.1f — %s",
            slug, result.overall, result.structure,
            result.readability, result.info_density, result.summary,
        )
        return result
    except Exception:
        logger.exception("Wiki evaluation failed for %s", slug)
        return None
