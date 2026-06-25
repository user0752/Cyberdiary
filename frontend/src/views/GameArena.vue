<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useGameStore } from '../stores/game'
import { useSettingsStore } from '../stores/settings'

const router = useRouter()

const gameStore = useGameStore()
const settingsStore = useSettingsStore()

// Setup state
const selectedModelId = ref('')
const selectedDifficulty = ref('medium')
const questionCount = ref(5)
const selectedWikiPageId = ref<string | undefined>(undefined)

const difficulties = [
  { value: 'easy', label: 'EASY', desc: '基础概念' },
  { value: 'medium', label: 'MEDIUM', desc: '理解应用' },
  { value: 'hard', label: 'HARD', desc: '深度分析' },
]

const optionLabels = ['A', 'B', 'C', 'D']

onMounted(() => {
  if (settingsStore.defaultChatModel) {
    selectedModelId.value = settingsStore.defaultChatModel
  } else if (settingsStore.models.length > 0) {
    const first = settingsStore.models.find((m) => m.enabled)
    if (first) selectedModelId.value = first.id
  }
})

watch(
  () => settingsStore.defaultChatModel,
  (val) => {
    if (val && !selectedModelId.value) selectedModelId.value = val
  },
)

const enabledModels = computed(() => settingsStore.models.filter((m) => m.enabled))

async function handleGenerate() {
  if (!selectedModelId.value) return
  await gameStore.startSession({
    model_id: selectedModelId.value,
    count: questionCount.value,
    difficulty: selectedDifficulty.value,
    wiki_page_id: selectedWikiPageId.value,
  })
}

function parseOptions(optionsStr: string): string[] {
  try {
    return JSON.parse(optionsStr)
  } catch {
    return []
  }
}

async function handleAnswer(answer: string) {
  await gameStore.submitCurrentAnswer(answer)
}

function handleNext() {
  if (gameStore.isSessionComplete) {
    gameStore.completeSession()
  } else {
    gameStore.nextQuestion()
  }
}

function handleRestart() {
  gameStore.resetGame()
}

const currentAnswerResult = computed(() => {
  if (!gameStore.showResult || gameStore.answers.length === 0) return null
  return gameStore.answers[gameStore.answers.length - 1]
})

const accuracyPercent = computed(() => {
  if (!gameStore.sessionSummary) return 0
  const s = gameStore.sessionSummary.session
  return s.total_questions > 0 ? Math.round((s.correct_count / s.total_questions) * 100) : 0
})
</script>

<template>
  <div class="game-arena">
    <!-- Back to Game Box -->
    <button class="btn-back" @click="router.push('/game')">
      <span class="back-arrow">&larr;</span>
      <span class="back-label">GAME BOX</span>
    </button>

    <!-- Header -->
    <header class="arena-header">
      <div class="header-title">
        <span class="title-icon">&#9876;</span>
        <h1>KNOWLEDGE ARENA</h1>
        <span class="title-tag">BETA</span>
      </div>
      <p class="header-sub">知识防御战 - 等待拦截</p>
    </header>

    <!-- State: Setup -->
    <div v-if="!gameStore.currentSession && !gameStore.sessionSummary" class="setup-panel">
      <div class="setup-card">
        <div class="card-header">
          <span class="card-tag">CONFIG</span>
          <span class="card-title">&#28216;&#25103;&#37197;&#32622;</span>
        </div>

        <!-- Model Selection -->
        <div class="form-group">
          <label class="form-label">LLM MODEL</label>
          <select v-model="selectedModelId" class="form-select">
            <option value="" disabled>-- &#36873;&#25321;&#27169;&#22411; --</option>
            <option v-for="m in enabledModels" :key="m.id" :value="m.id">
              {{ m.display_name || m.model_name }}
            </option>
          </select>
        </div>

        <!-- Difficulty -->
        <div class="form-group">
          <label class="form-label">DIFFICULTY</label>
          <div class="difficulty-row">
            <button
              v-for="d in difficulties"
              :key="d.value"
              class="diff-btn"
              :class="{ active: selectedDifficulty === d.value }"
              @click="selectedDifficulty = d.value"
            >
              <span class="diff-label">{{ d.label }}</span>
              <span class="diff-desc">{{ d.desc }}</span>
            </button>
          </div>
        </div>

        <!-- Question Count -->
        <div class="form-group">
          <label class="form-label">QUESTIONS: {{ questionCount }}</label>
          <input
            v-model.number="questionCount"
            type="range"
            min="1"
            max="20"
            class="form-range"
          />
        </div>

        <!-- Generate Button -->
        <button
          class="btn-generate"
          :disabled="!selectedModelId || gameStore.generating"
          @click="handleGenerate"
        >
          <span v-if="gameStore.generating" class="spinner"></span>
          <span v-else>GENERATE QUESTIONS</span>
        </button>

        <p v-if="gameStore.generating" class="generating-hint">
          &#27491;&#22312;&#29983;&#25104;&#39064;&#30446;&#65292;&#35831;&#31245;&#20505;...
        </p>
      </div>
    </div>

    <!-- State: Quiz -->
    <div
      v-else-if="gameStore.currentSession && !gameStore.sessionSummary"
      class="quiz-panel"
    >
      <!-- Progress Bar -->
      <div class="progress-bar">
        <div class="progress-info">
          <span class="progress-text">{{ gameStore.progress }}</span>
          <span class="progress-score">SCORE: {{ gameStore.score }}</span>
        </div>
        <div class="progress-track">
          <div
            class="progress-fill"
            :style="{
              width: `${(gameStore.answers.length / gameStore.questions.length) * 100}%`,
            }"
          ></div>
        </div>
      </div>

      <!-- Question Card -->
      <div v-if="gameStore.currentQuestion" class="question-card">
        <div class="q-header">
          <span class="q-type">CHOICE</span>
          <span class="q-source">{{ gameStore.currentQuestion.source_title }}</span>
        </div>
        <p class="q-text">{{ gameStore.currentQuestion.question_text }}</p>

        <!-- Options -->
        <div class="options-grid">
          <button
            v-for="(opt, idx) in parseOptions(gameStore.currentQuestion.options)"
            :key="idx"
            class="option-btn"
            :class="{
              selected: currentAnswerResult?.user_answer === optionLabels[idx],
              correct: gameStore.showResult && gameStore.currentQuestion && optionLabels[idx] === currentAnswerResult?.correct_answer,
              wrong:
                gameStore.showResult &&
                currentAnswerResult?.user_answer === optionLabels[idx] &&
                !currentAnswerResult?.is_correct,
              disabled: gameStore.showResult,
            }"
            :disabled="gameStore.showResult || gameStore.loading"
            @click="handleAnswer(optionLabels[idx])"
          >
            <span class="opt-label">{{ optionLabels[idx] }}</span>
            <span class="opt-text">{{ opt }}</span>
          </button>
        </div>

        <!-- Feedback -->
        <div v-if="gameStore.showResult && currentAnswerResult" class="feedback-box">
          <div
            class="feedback-status"
            :class="{ correct: currentAnswerResult.is_correct, wrong: !currentAnswerResult.is_correct }"
          >
            {{ currentAnswerResult.is_correct ? 'CORRECT' : 'WRONG' }}
          </div>
          <p v-if="currentAnswerResult.explanation" class="feedback-explain">
            {{ currentAnswerResult.explanation }}
          </p>
          <button class="btn-next" @click="handleNext">
            {{ gameStore.isSessionComplete ? 'VIEW RESULTS' : 'NEXT QUESTION' }}
          </button>
        </div>
      </div>
    </div>

    <!-- State: Results -->
    <div v-else-if="gameStore.sessionSummary" class="results-panel">
      <div class="results-card">
        <div class="results-header">
          <span class="results-tag">REPORT</span>
          <h2>MISSION COMPLETE</h2>
        </div>

        <div class="results-stats">
          <div class="stat-item">
            <span class="stat-value">{{ gameStore.sessionSummary.session.total_questions }}</span>
            <span class="stat-label">TOTAL</span>
          </div>
          <div class="stat-item correct-stat">
            <span class="stat-value">{{ gameStore.sessionSummary.session.correct_count }}</span>
            <span class="stat-label">CORRECT</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">{{ accuracyPercent }}%</span>
            <span class="stat-label">ACCURACY</span>
          </div>
        </div>

        <!-- Answer Details -->
        <div class="results-details">
          <div
            v-for="(ans, idx) in gameStore.sessionSummary.answers"
            :key="ans.question_id"
            class="detail-row"
            :class="{ correct: ans.is_correct, wrong: !ans.is_correct }"
          >
            <span class="detail-idx">#{{ idx + 1 }}</span>
            <span class="detail-status">{{ ans.is_correct ? 'PASS' : 'FAIL' }}</span>
            <span class="detail-answer">
              &#20320;:{{ ans.user_answer }} | &#31561;&#24453;:{{ ans.correct_answer }}
            </span>
          </div>
        </div>

        <button class="btn-restart" @click="handleRestart">PLAY AGAIN</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.game-arena {
  padding: 32px;
  max-width: 800px;
  margin: 0 auto;
  min-height: 100vh;
}

/* Back button */
.btn-back {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 6px 14px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.7rem;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-bottom: 24px;
}

.btn-back:hover {
  border-color: var(--accent-dim);
  color: var(--accent);
  background: var(--accent-ghost);
}

.back-arrow {
  font-size: 0.85rem;
}

.back-label {
  font-weight: 600;
}

/* Header */
.arena-header {
  margin-bottom: 32px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-icon {
  font-size: 1.5rem;
  color: var(--accent);
}

.header-title h1 {
  font-family: var(--font-display);
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.15em;
  margin: 0;
}

.title-tag {
  font-family: var(--font-mono);
  font-size: 0.55rem;
  color: var(--neon-orange);
  border: 1px solid var(--neon-orange);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  letter-spacing: 0.1em;
}

.header-sub {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 6px;
}

/* Setup Panel */
.setup-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 24px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 24px;
}

.card-tag {
  font-family: var(--font-mono);
  font-size: 0.6rem;
  color: var(--accent);
  background: var(--accent-ghost);
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  letter-spacing: 0.1em;
}

.card-title {
  font-family: var(--font-display);
  font-size: 0.9rem;
  color: var(--text-primary);
  letter-spacing: 0.08em;
}

.form-group {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-muted);
  letter-spacing: 0.1em;
  margin-bottom: 8px;
}

.form-select {
  width: 100%;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: 0.85rem;
  padding: 10px 12px;
  outline: none;
  transition: border-color var(--transition-fast);
}

.form-select:focus {
  border-color: var(--accent);
}

.form-select option {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.difficulty-row {
  display: flex;
  gap: 8px;
}

.diff-btn {
  flex: 1;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 8px;
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: center;
}

.diff-btn:hover {
  border-color: var(--accent-dim);
}

.diff-btn.active {
  border-color: var(--accent);
  background: var(--accent-ghost);
  box-shadow: var(--glow-sm);
}

.diff-label {
  display: block;
  font-family: var(--font-display);
  font-size: 0.75rem;
  color: var(--text-primary);
  letter-spacing: 0.1em;
}

.diff-desc {
  display: block;
  font-size: 0.65rem;
  color: var(--text-muted);
  margin-top: 2px;
}

.diff-btn.active .diff-label {
  color: var(--accent);
}

.form-range {
  width: 100%;
  accent-color: var(--accent);
  height: 4px;
}

.btn-generate {
  width: 100%;
  background: var(--accent);
  color: var(--bg-void);
  border: none;
  border-radius: var(--radius-sm);
  padding: 14px;
  font-family: var(--font-display);
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-top: 8px;
}

.btn-generate:hover:not(:disabled) {
  background: var(--accent-hover);
  box-shadow: var(--glow-md);
}

.btn-generate:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid var(--bg-void);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.generating-hint {
  text-align: center;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--accent);
  margin-top: 12px;
  animation: blink 1.5s ease-in-out infinite;
}

@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

/* Quiz Panel */
.progress-bar {
  margin-bottom: 24px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.progress-text,
.progress-score {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  letter-spacing: 0.08em;
}

.progress-score {
  color: var(--accent);
}

.progress-track {
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  transition: width var(--transition-smooth);
  box-shadow: 0 0 8px var(--accent-glow);
}

/* Question Card */
.question-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 24px;
}

.q-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.q-type {
  font-family: var(--font-mono);
  font-size: 0.6rem;
  color: var(--neon-magenta);
  background: var(--neon-magenta-glow);
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  letter-spacing: 0.1em;
}

.q-source {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-muted);
}

.q-text {
  font-size: 1rem;
  color: var(--text-primary);
  line-height: 1.7;
  margin-bottom: 20px;
}

/* Options */
.options-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.option-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  cursor: pointer;
  transition: all var(--transition-fast);
  text-align: left;
  width: 100%;
}

.option-btn:hover:not(:disabled) {
  border-color: var(--accent-dim);
  background: var(--bg-hover);
}

.option-btn.selected {
  border-color: var(--accent);
  background: var(--accent-ghost);
}

.option-btn.correct {
  border-color: var(--neon-green);
  background: var(--neon-green-glow);
}

.option-btn.wrong {
  border-color: #ff4757;
  background: rgba(255, 71, 87, 0.1);
}

.option-btn.disabled {
  cursor: default;
}

.opt-label {
  font-family: var(--font-display);
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--accent);
  min-width: 24px;
  text-align: center;
}

.option-btn.correct .opt-label {
  color: var(--neon-green);
}

.option-btn.wrong .opt-label {
  color: #ff4757;
}

.opt-text {
  font-size: 0.9rem;
  color: var(--text-primary);
  line-height: 1.5;
}

/* Feedback */
.feedback-box {
  border-top: 1px solid var(--border-dim);
  padding-top: 16px;
}

.feedback-status {
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  margin-bottom: 8px;
}

.feedback-status.correct {
  color: var(--neon-green);
  text-shadow: 0 0 12px var(--neon-green-glow);
}

.feedback-status.wrong {
  color: #ff4757;
  text-shadow: 0 0 12px rgba(255, 71, 87, 0.3);
}

.feedback-explain {
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 16px;
}

.btn-next {
  background: var(--accent);
  color: var(--bg-void);
  border: none;
  border-radius: var(--radius-sm);
  padding: 10px 24px;
  font-family: var(--font-display);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-next:hover {
  background: var(--accent-hover);
  box-shadow: var(--glow-sm);
}

/* Results Panel */
.results-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 32px;
}

.results-header {
  text-align: center;
  margin-bottom: 28px;
}

.results-tag {
  font-family: var(--font-mono);
  font-size: 0.6rem;
  color: var(--accent);
  background: var(--accent-ghost);
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  letter-spacing: 0.15em;
}

.results-header h2 {
  font-family: var(--font-display);
  font-size: 1.3rem;
  color: var(--text-primary);
  letter-spacing: 0.2em;
  margin-top: 10px;
}

.results-stats {
  display: flex;
  justify-content: center;
  gap: 32px;
  margin-bottom: 28px;
}

.stat-item {
  text-align: center;
}

.stat-value {
  display: block;
  font-family: var(--font-display);
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.05em;
}

.stat-item.correct-stat .stat-value {
  color: var(--neon-green);
  text-shadow: 0 0 16px var(--neon-green-glow);
}

.stat-label {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-muted);
  letter-spacing: 0.12em;
}

.results-details {
  margin-bottom: 24px;
}

.detail-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-dim);
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.detail-row.correct {
  color: var(--neon-green);
}

.detail-row.wrong {
  color: #ff4757;
}

.detail-idx {
  color: var(--text-muted);
  min-width: 28px;
}

.detail-status {
  font-weight: 700;
  min-width: 40px;
}

.detail-answer {
  color: var(--text-secondary);
}

.btn-restart {
  display: block;
  width: 100%;
  background: var(--accent);
  color: var(--bg-void);
  border: none;
  border-radius: var(--radius-sm);
  padding: 14px;
  font-family: var(--font-display);
  font-size: 0.9rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-restart:hover {
  background: var(--accent-hover);
  box-shadow: var(--glow-md);
}
</style>
