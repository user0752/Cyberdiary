import client from './client'

export interface GameQuestion {
  id: string
  wiki_page_id: string | null
  question_type: string
  difficulty: string
  question_text: string
  options: string // JSON string
  source_title: string | null
}

export interface GameSession {
  id: string
  wiki_page_id: string | null
  model_id: string
  status: string
  total_questions: number
  correct_count: number
  created_at: string
  finished_at: string | null
}

export interface SessionCreateData {
  session: GameSession
  questions: GameQuestion[]
}

export interface AnswerResult {
  question_id: string
  user_answer: string
  is_correct: boolean
  correct_answer: string
  explanation: string | null
}

export interface SessionSummary {
  session: GameSession
  answers: AnswerResult[]
}

export async function generateQuestions(params: {
  wiki_page_id?: string
  count?: number
  difficulty?: string
  model_id: string
}): Promise<SessionCreateData> {
  const { data } = await client.post('/game/generate', params)
  return data.data
}

export async function submitAnswer(
  sessionId: string,
  questionId: string,
  userAnswer: string,
): Promise<AnswerResult> {
  const { data } = await client.post(
    `/game/answer?session_id=${sessionId}`,
    { question_id: questionId, user_answer: userAnswer },
  )
  return data.data
}

export async function finishSession(sessionId: string): Promise<GameSession> {
  const { data } = await client.post(`/game/sessions/${sessionId}/finish`)
  return data.data
}

export async function getSessionResults(sessionId: string): Promise<SessionSummary> {
  const { data } = await client.get(`/game/sessions/${sessionId}`)
  return data.data
}
