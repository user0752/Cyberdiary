import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as gameApi from '../api/game'
import type { GameQuestion, GameSession, AnswerResult, SessionSummary } from '../api/game'
import { useToastStore } from './toast'
import { ApiError } from '../api/client'

export const useGameStore = defineStore('game', () => {
  // State
  const currentSession = ref<GameSession | null>(null)
  const questions = ref<GameQuestion[]>([])
  const currentIndex = ref(0)
  const answers = ref<AnswerResult[]>([])
  const loading = ref(false)
  const generating = ref(false)
  const showResult = ref(false)
  const sessionSummary = ref<SessionSummary | null>(null)

  // Computed
  const currentQuestion = computed(() => questions.value[currentIndex.value] || null)
  const progress = computed(() => `${currentIndex.value + 1} / ${questions.value.length}`)
  const score = computed(() => {
    const correct = answers.value.filter((a) => a.is_correct).length
    return `${correct} / ${answers.value.length}`
  })
  const isSessionComplete = computed(
    () => answers.value.length === questions.value.length && questions.value.length > 0,
  )

  // Actions
  async function startSession(params: {
    wiki_page_id?: string
    count?: number
    difficulty?: string
    model_id: string
  }) {
    const toast = useToastStore()
    generating.value = true
    try {
      const data = await gameApi.generateQuestions(params)
      currentSession.value = data.session
      questions.value = data.questions
      currentIndex.value = 0
      answers.value = []
      showResult.value = false
      sessionSummary.value = null
    } catch (e) {
      // Surface API errors as a user-facing toast instead of letting them
      // bubble to the global Vue errorHandler (which would otherwise show a
      // misleading "界面渲染错误" toast — the UI didn't actually fail to
      // render; the LLM just returned malformed JSON).
      const msg = e instanceof ApiError ? e.message : '生成题目失败'
      toast.error('生成题目失败: ' + msg)
    } finally {
      generating.value = false
    }
  }

  async function submitCurrentAnswer(userAnswer: string) {
    if (!currentSession.value || !currentQuestion.value || showResult.value) return
    const toast = useToastStore()
    loading.value = true
    try {
      const result = await gameApi.submitAnswer(
        currentSession.value.id,
        currentQuestion.value.id,
        userAnswer,
      )
      answers.value.push(result)
      showResult.value = true
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : '提交答案失败'
      toast.error('提交答案失败: ' + msg)
    } finally {
      loading.value = false
    }
  }

  function nextQuestion() {
    if (currentIndex.value < questions.value.length - 1) {
      currentIndex.value++
      showResult.value = false
    }
  }

  async function completeSession() {
    if (!currentSession.value) return
    sessionSummary.value = await gameApi.getSessionResults(currentSession.value.id)
    await gameApi.finishSession(currentSession.value.id)
  }

  function resetGame() {
    currentSession.value = null
    questions.value = []
    currentIndex.value = 0
    answers.value = []
    showResult.value = false
    sessionSummary.value = null
  }

  return {
    currentSession,
    questions,
    currentIndex,
    answers,
    loading,
    generating,
    showResult,
    sessionSummary,
    currentQuestion,
    progress,
    score,
    isSessionComplete,
    startSession,
    submitCurrentAnswer,
    nextQuestion,
    completeSession,
    resetGame,
  }
})
