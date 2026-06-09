"""Game API routes - quiz generation, answering, session management."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.game import (
    AnswerResult,
    AnswerSubmit,
    GenerateRequest,
    QuestionResponse,
    SessionCreateResponse,
    SessionResponse,
    SessionSummary,
)
from app.schemas.memo import ApiResponse
from app.services import game_service

router = APIRouter(prefix="/game", tags=["game"])


@router.post("/generate", response_model=ApiResponse[SessionCreateResponse])
async def generate_questions(data: GenerateRequest, db: AsyncSession = Depends(get_db)):
    """Generate quiz questions from Wiki content and create a game session."""
    try:
        questions, session = await game_service.generate_questions(
            db, data.wiki_page_id, data.count, data.difficulty, data.model_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ApiResponse(data=SessionCreateResponse(
        session=SessionResponse.model_validate(session),
        questions=[QuestionResponse.model_validate(q) for q in questions],
    ))


@router.post("/answer", response_model=ApiResponse[AnswerResult])
async def submit_answer(
    data: AnswerSubmit,
    session_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Submit an answer for a question in a game session."""
    try:
        answer = await game_service.submit_answer(
            db, session_id, data.question_id, data.user_answer
        )
        question = await game_service.get_question(db, data.question_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return ApiResponse(data=AnswerResult(
        question_id=answer.question_id,
        user_answer=answer.user_answer,
        is_correct=answer.is_correct,
        correct_answer=question.correct_answer,
        explanation=question.explanation,
    ))


@router.post("/sessions/{session_id}/finish", response_model=ApiResponse[SessionResponse])
async def finish_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Mark a game session as completed."""
    try:
        session = await game_service.finish_session(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return ApiResponse(data=SessionResponse.model_validate(session))


@router.get("/sessions/{session_id}", response_model=ApiResponse[SessionSummary])
async def get_session_results(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get session results with all answers and explanations."""
    try:
        session, answers = await game_service.get_session_results(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return ApiResponse(data=SessionSummary(
        session=SessionResponse.model_validate(session),
        answers=[AnswerResult(**a) for a in answers],
    ))
