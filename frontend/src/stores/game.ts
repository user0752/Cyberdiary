import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as gameApi from '../api/game'
import type { GameQuestion, GameSession, AnswerResult, SessionSummary } from '../api/game'

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
    generating.value = true
    try {
      const data = await gameApi.generateQuestions(params)
      currentSession.value = data.session
      questions.value = data.questions
      currentIndex.value = 0
      answers.value = []
      showResult.value = false
      sessionSummary.value = null
    } finally {
      generating.value = false
    }
  }

  async function submitCurrentAnswer(userAnswer: string) {
    if (!currentSession.value || !currentQuestion.value || showResult.value) return
    loading.value = true
    try {
      const result = await gameApi.submitAnswer(
        currentSession.value.id,
        currentQuestion.value.id,
        userAnswer,
      )
      answers.value.push(result)
      showResult.value = true
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
