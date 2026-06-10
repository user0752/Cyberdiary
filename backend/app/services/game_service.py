"""Game service - quiz generation, answer validation, session management."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import GameAnswer, GameQuestion, GameSession
from app.models.wiki import WikiPage
from app.services import llm_service

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def _parse_llm_json(raw: str) -> list[dict]:
    """Parse JSON array from LLM output, handling markdown code fences."""
    text = raw.strip()
    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array in the text
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            result = json.loads(match.group())
        else:
            raise ValueError(f"Failed to parse LLM output as JSON array: {text[:200]}")

    if not isinstance(result, list):
        raise ValueError(f"Expected JSON array, got {type(result).__name__}")

    return result


async def generate_questions(
    db: AsyncSession,
    wiki_page_id: str | None,
    count: int,
    difficulty: str,
    model_id: str,
) -> tuple[list[GameQuestion], GameSession]:
    """Generate quiz questions from Wiki content via LLM."""
    # 1. Get model config
    model_config = await llm_service.get_model_config_from_db(db, model_id)
    if not model_config:
        raise ValueError(f"Model not found: {model_id}")

    # 2. Get Wiki content
    if wiki_page_id:
        result = await db.execute(select(WikiPage).where(WikiPage.id == wiki_page_id))
        page = result.scalar_one_or_none()
        if not page:
            raise ValueError(f"Wiki page not found: {wiki_page_id}")
        title = page.title
        content = page.content[:3000]  # Truncate to avoid token overflow
        wiki_type = page.wiki_type
    else:
        # Pick the most recent wiki page
        result = await db.execute(
            select(WikiPage).order_by(WikiPage.updated_at.desc()).limit(1)
        )
        page = result.scalar_one_or_none()
        if not page:
            raise ValueError("No wiki pages found. Please create Wiki content first.")
        title = page.title
        content = page.content[:3000]
        wiki_type = page.wiki_type
        wiki_page_id = page.id

    # 3. Build prompt
    prompt_template = (PROMPTS_DIR / "game_question.md").read_text(encoding="utf-8")
    user_prompt = prompt_template.format(
        title=title,
        wiki_type=wiki_type,
        content=content,
        difficulty=difficulty,
        count=count,
    )

    messages = [
        {"role": "system", "content": "你是一个专业的知识测验出题专家。只输出 JSON 数组，不要输出其他内容。"},
        {"role": "user", "content": user_prompt},
    ]

    # 4. Call LLM
    response = await llm_service.chat_completion(model_config, messages, stream=False)
    raw_content = response.choices[0].message.content if response.choices else ""

    # 5. Parse JSON
    questions_data = _parse_llm_json(raw_content)

    # 6. Create question records
    questions = []
    question_ids = []
    for qd in questions_data[:count]:  # Respect requested count
        options = qd.get("options", [])
        if isinstance(options, list):
            options_json = json.dumps(options, ensure_ascii=False)
        else:
            options_json = str(options)

        question = GameQuestion(
            wiki_page_id=wiki_page_id,
            question_type="choice",
            difficulty=difficulty,
            question_text=qd.get("question_text", ""),
            options=options_json,
            correct_answer=qd.get("correct_answer", "A").upper(),
            explanation=qd.get("explanation"),
            source_title=title,
        )
        db.add(question)
        questions.append(question)

    # Flush to get IDs
    await db.flush()
    question_ids = [q.id for q in questions]

    # 7. Create session
    session = GameSession(
        wiki_page_id=wiki_page_id,
        model_id=model_id,
        status="active",
        total_questions=len(questions),
        correct_count=0,
        question_ids=json.dumps(question_ids),
        lives=20,
        gold=100,
        current_wave=0,
        total_waves=10,
        tower_placements="{}",
        game_state="playing",
        wave_configs="[]",
    )
    db.add(session)
    await db.flush()

    return questions, session


async def get_question(db: AsyncSession, question_id: str) -> GameQuestion | None:
    """Fetch a single question by ID."""
    result = await db.execute(select(GameQuestion).where(GameQuestion.id == question_id))
    return result.scalar_one_or_none()


async def get_session(db: AsyncSession, session_id: str) -> GameSession | None:
    """Fetch a session by ID."""
    result = await db.execute(select(GameSession).where(GameSession.id == session_id))
    return result.scalar_one_or_none()


async def get_session_questions(db: AsyncSession, session: GameSession) -> list[GameQuestion]:
    """Get all questions for a session."""
    question_ids = json.loads(session.question_ids)
    if not question_ids:
        return []
    result = await db.execute(
        select(GameQuestion).where(GameQuestion.id.in_(question_ids))
    )
    questions = {q.id: q for q in result.scalars().all()}
    # Preserve original order
    return [questions[qid] for qid in question_ids if qid in questions]


async def submit_answer(
    db: AsyncSession,
    session_id: str,
    question_id: str,
    user_answer: str,
) -> GameAnswer:
    """Submit an answer and record it."""
    # Validate session
    session = await get_session(db, session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    # Validate question
    question = await get_question(db, question_id)
    if not question:
        raise ValueError(f"Question not found: {question_id}")

    # Check correctness
    is_correct = user_answer.strip().upper() == question.correct_answer.strip().upper()

    # Create answer record
    answer = GameAnswer(
        session_id=session_id,
        question_id=question_id,
        user_answer=user_answer.strip().upper(),
        is_correct=is_correct,
    )
    db.add(answer)

    # Update session score
    if is_correct:
        session.correct_count += 1

    await db.flush()
    return answer


async def finish_session(db: AsyncSession, session_id: str) -> GameSession:
    """Mark a session as completed."""
    session = await get_session(db, session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    session.status = "completed"
    session.finished_at = datetime.now(timezone.utc)
    await db.flush()
    return session


async def get_session_results(
    db: AsyncSession, session_id: str
) -> tuple[GameSession, list[dict]]:
    """Get session summary with all answers."""
    session = await get_session(db, session_id)
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    # Get all answers for this session
    result = await db.execute(
        select(GameAnswer).where(GameAnswer.session_id == session_id)
    )
    answers = result.scalars().all()

    # Get questions for explanations
    question_ids = json.loads(session.question_ids)
    questions_result = await db.execute(
        select(GameQuestion).where(GameQuestion.id.in_(question_ids))
    )
    questions_map = {q.id: q for q in questions_result.scalars().all()}

    # Build answer details
    answer_details = []
    for ans in answers:
        q = questions_map.get(ans.question_id)
        answer_details.append({
            "question_id": ans.question_id,
            "user_answer": ans.user_answer,
            "is_correct": ans.is_correct,
            "correct_answer": q.correct_answer if q else "?",
            "explanation": q.explanation if q else None,
        })

    return session, answer_details
