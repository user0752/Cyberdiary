<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchMemos } from '../api/memo'
import {
  triggerSingleCompile,
  streamSingleCompile,
  triggerMultiAgentCompile,
  streamMultiAgentCompile,
  submitHumanReview,
  type CompileConfig,
  type TraceEntry,
  type CompileProgress,
  type SSEEvent,
  type SemanticLink,
} from '../api/compile'
import { useSettingsStore } from '../stores/settings'
import CompilationTracePanel from '../components/CompilationTracePanel.vue'
import CompileResult from '../components/CompileResult.vue'
import HumanReviewPanel from '../components/HumanReviewPanel.vue'

const settingsStore = useSettingsStore()

// --- Memo selection ---
const memos = ref<{ id: string; content: string; tags: string; created_at: string }[]>([])
const selectedMemoIds = ref<Set<string>>(new Set())
const loadingMemos = ref(false)

// --- Mode & Config ---
const compileMode = ref<'single' | 'multi'>('multi')
const config = ref<CompileConfig>({
  max_revisions: 3,
  pass_threshold: 8.0,
  enable_human_review: false,
})

// --- Compile state ---
const isCompiling = ref(false)
const jobId = ref<string | null>(null)
const progress = ref<CompileProgress | null>(null)
const traceEvents = ref<TraceEntry[]>([])

// --- Results ---
const finalScore = ref(0)
const wikiContent = ref<string | null>(null)
const semanticLinks = ref<SemanticLink[]>([])
const errorMsg = ref<string | null>(null)
const startTime = ref<number | null>(null)
const endTime = ref<number | null>(null)
const durationSec = computed(() => {
  if (!startTime.value || !endTime.value) return null
  return (endTime.value - startTime.value) / 1000
})

// --- Human review ---
const reviewTaskId = ref<string | null>(null)
const reviewScore = ref(0)
const reviewFeedback = ref<string[]>([])

const modelId = ref('')

async function loadMemos() {
  loadingMemos.value = true
  try {
    const data = await fetchMemos({ page_size: 100 })
    memos.value = data.items.filter((m) => !m.compiled)
  } finally {
    loadingMemos.value = false
  }
}

function toggleMemo(id: string) {
  const next = new Set(selectedMemoIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedMemoIds.value = next
}

function toggleAll() {
  if (selectedMemoIds.value.size === memos.value.length) {
    selectedMemoIds.value = new Set()
  } else {
    selectedMemoIds.value = new Set(memos.value.map((m) => m.id))
  }
}

function canCompile(): boolean {
  if (selectedMemoIds.value.size === 0) return false
  if (!modelId.value) return false
  return true
}

async function startCompile() {
  if (isCompiling.value || !canCompile()) return

  // Reset state
  isCompiling.value = true
  errorMsg.value = null
  traceEvents.value = []
  progress.value = { status: 'pending', progress: 0, message: 'Starting...' }
  finalScore.value = 0
  wikiContent.value = null
  semanticLinks.value = []
  startTime.value = Date.now()
  endTime.value = null

  try {
    if (compileMode.value === 'single') {
      // Single-agent compile
      const job = await triggerSingleCompile(
        Array.from(selectedMemoIds.value),
        modelId.value,
      )
      jobId.value = job.id

      const stream = streamSingleCompile(job.id)
      for await (const event of stream) {
        handleSSEEvent(event)
      }
    } else {
      // Multi-agent compile
      const job = await triggerMultiAgentCompile(
        Array.from(selectedMemoIds.value),
        { ...config.value, model: modelId.value },
      )
      jobId.value = job.job_id

      const stream = streamMultiAgentCompile(job.job_id)
      for await (const event of stream) {
        handleSSEEvent(event)
      }
    }
  } catch (e: any) {
    errorMsg.value = e.message || 'Compile failed'
    progress.value = { status: 'failed', progress: 0, message: errorMsg.value! }
    isCompiling.value = false
    endTime.value = Date.now()
  }
}

function handleSSEEvent(event: SSEEvent) {
  switch (event.event) {
    case 'progress':
      progress.value = event.data as CompileProgress
      break

    case 'complete': {
      const data = event.data as Record<string, unknown>
      progress.value = {
        status: 'completed',
        progress: 100,
        message: (data.message as string) || 'Done',
      }
      finalScore.value = (data.final_score as number) || 0
      wikiContent.value = (data.wiki_draft as string) || (data.wiki_revised as string) || null
      semanticLinks.value = (data.suggested_links as SemanticLink[]) || []
      isCompiling.value = false
      endTime.value = Date.now()
      break
    }

    case 'error': {
      const data = event.data as Record<string, unknown>
      errorMsg.value = (data.message as string) || 'Unknown error'
      progress.value = { status: 'failed', progress: 0, message: errorMsg.value! }
      isCompiling.value = false
      endTime.value = Date.now()
      break
    }

    case 'needs_review': {
      const data = event.data as Record<string, unknown>
      reviewTaskId.value = (data.task_id as string) || ''
      reviewScore.value = (data.final_score as number) || 0
      reviewFeedback.value = (data.review_feedback as string[]) || []
      wikiContent.value = (data.wiki_draft as string) || ''
      finalScore.value = reviewScore.value
      progress.value = {
        status: 'needs_review',
        progress: (data.progress as number) || 75,
        message: (data.message as string) || 'Human review required',
      }
      isCompiling.value = false
      break
    }

    case 'trace': {
      const data = event.data as TraceEntry
      if (data) traceEvents.value.push(data)
      break
    }
  }
}

async function handleReviewDecision(decision: 'approve' | 'revise' | 'reject', editedWiki?: string) {
  if (!reviewTaskId.value) return

  isCompiling.value = true
  try {
    const result = await submitHumanReview(reviewTaskId.value, decision, editedWiki)
    reviewTaskId.value = null

    if (result.review_passed) {
      progress.value = { status: 'running', progress: 85, message: 'Review approved, finalizing...' }
      // Reconnect SSE to get final result
      await pollJobResult()
    } else if (result.next_action === 'revise') {
      progress.value = { status: 'running', progress: 78, message: 'Revision requested, re-entering pipeline...' }
      await pollJobResult()
    } else {
      progress.value = { status: 'failed', progress: 0, message: 'Compilation terminated by reviewer' }
      errorMsg.value = 'Terminated by reviewer'
      isCompiling.value = false
      endTime.value = Date.now()
    }
  } catch (e: any) {
    errorMsg.value = e.message || 'Review submission failed'
    isCompiling.value = false
    endTime.value = Date.now()
  }
}

async function pollJobResult() {
  if (!jobId.value) return
  try {
    const stream = streamMultiAgentCompile(jobId.value)
    for await (const event of stream) {
      handleSSEEvent(event)
      if (event.event === 'complete' || event.event === 'error') break
    }
  } catch {
    // stream may close when job completes
  }
}

function formatMemoDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function truncateContent(content: string, max = 80) {
  return content.length > max ? content.slice(0, max) + '...' : content
}

onMounted(async () => {
  await settingsStore.init()
  if (settingsStore.defaultCompileModel) {
    modelId.value = settingsStore.defaultCompileModel
  } else {
    const first = settingsStore.models.find((m) => m.enabled)
    if (first) modelId.value = first.id
  }
  await loadMemos()
})
</script>

<template>
  <div class="compile-view">
    <header class="view-header">
      <div class="header-left">
        <div>
          <h1 class="page-title">COMPILE ENGINE</h1>
          <p class="page-subtitle">编译引擎 — 多智能体协作知识编译</p>
        </div>
      </div>
      <div class="mode-toggle">
        <button
          class="mode-btn"
          :class="{ active: compileMode === 'single' }"
          @click="compileMode = 'single'"
        >SINGLE</button>
        <button
          class="mode-btn"
          :class="{ active: compileMode === 'multi' }"
          @click="compileMode = 'multi'"
        >MULTI-AGENT</button>
      </div>
    </header>

    <div class="compile-layout">
      <!-- Left Panel: Memo Selection + Config -->
      <aside class="left-panel" :class="{ collapsed: isCompiling && compileMode === 'multi' }">
        <!-- Memo Selector -->
        <section class="panel-section">
          <div class="section-header">
            <span class="section-label">// MEMOS</span>
            <button
              v-if="memos.length"
              class="btn-ghost-sm"
              @click="toggleAll"
            >
              {{ selectedMemoIds.size === memos.length ? 'DESELECT ALL' : 'SELECT ALL' }}
            </button>
          </div>

          <div v-if="loadingMemos" class="section-placeholder">
            <div class="loading-spinner"></div>
            <span>LOADING...</span>
          </div>

          <div v-else-if="memos.length === 0" class="section-placeholder">
            <svg viewBox="0 0 40 40" fill="none" class="empty-icon">
              <rect x="8" y="12" width="24" height="20" rx="2" stroke="currentColor" stroke-width="1.5"/>
              <line x1="14" y1="20" x2="26" y2="20" stroke="currentColor" stroke-width="1.5"/>
              <line x1="14" y1="26" x2="22" y2="26" stroke="currentColor" stroke-width="1.5"/>
            </svg>
            <span>No uncompiled memos</span>
            <span class="hint">Write some memos first</span>
          </div>

          <div v-else class="memo-list">
            <label
              v-for="memo in memos"
              :key="memo.id"
              class="memo-item"
              :class="{ selected: selectedMemoIds.has(memo.id) }"
            >
              <input
                type="checkbox"
                :checked="selectedMemoIds.has(memo.id)"
                @change="toggleMemo(memo.id)"
              />
              <div class="memo-info">
                <span class="memo-text">{{ truncateContent(memo.content) }}</span>
                <span class="memo-date">{{ formatMemoDate(memo.created_at) }}</span>
              </div>
            </label>
          </div>

          <div v-if="selectedMemoIds.size > 0" class="selection-count">
            {{ selectedMemoIds.size }} memo{{ selectedMemoIds.size !== 1 ? 's' : '' }} selected
          </div>
        </section>

        <!-- Config -->
        <section class="panel-section">
          <div class="section-header">
            <span class="section-label">// CONFIG</span>
          </div>

          <div class="config-grid">
            <div class="config-item">
              <label>Model</label>
              <select v-model="modelId" class="config-select">
                <option value="" disabled>Select model...</option>
                <option
                  v-for="m in settingsStore.models.filter(m => m.enabled)"
                  :key="m.id"
                  :value="m.id"
                >
                  {{ m.display_name || m.model_name }}
                </option>
              </select>
            </div>

            <template v-if="compileMode === 'multi'">
              <div class="config-item">
                <label>Pass Threshold</label>
                <input
                  v-model.number="config.pass_threshold"
                  type="number"
                  min="1"
                  max="10"
                  step="0.5"
                  class="config-input"
                />
              </div>

              <div class="config-item">
                <label>Max Revisions</label>
                <input
                  v-model.number="config.max_revisions"
                  type="number"
                  min="0"
                  max="10"
                  class="config-input"
                />
              </div>

              <div class="config-item checkbox-item">
                <label>
                  <input v-model="config.enable_human_review" type="checkbox" />
                  Human Review
                </label>
              </div>
            </template>
          </div>
        </section>

        <!-- Start Button -->
        <div class="action-bar">
          <button
            class="btn btn-primary btn-start"
            :disabled="!canCompile() || isCompiling"
            @click="startCompile"
          >
            <svg v-if="!isCompiling" viewBox="0 0 20 20" fill="currentColor" class="btn-icon">
              <path d="M10 2l8 4-8 4-8-4 8-4zm0 8l8 4-8 4-8-4 8-4zm0 8l8 4-8 4-8-4 8-4z"/>
            </svg>
            <div v-else class="btn-spinner"></div>
            {{ isCompiling ? 'COMPILING...' : `START ${compileMode === 'multi' ? 'MULTI-AGENT ' : ''}COMPILE` }}
          </button>
        </div>
      </aside>

      <!-- Right Panel: Trace + Results -->
      <main class="right-panel">
        <!-- Trace Panel (during compile) -->
        <CompilationTracePanel
          v-if="isCompiling || traceEvents.length > 0"
          :trace-events="traceEvents"
          :progress="progress"
          :is-compiling="isCompiling"
        />

        <!-- Idle State -->
        <div v-if="!isCompiling && traceEvents.length === 0 && !errorMsg" class="idle-state">
          <div class="idle-visual">
            <svg viewBox="0 0 80 80" fill="none">
              <path d="M40 8L8 40L40 72L72 40L40 8Z" stroke="currentColor" stroke-width="1.5" opacity="0.15"/>
              <path d="M40 20L20 40L40 60L60 40L40 20Z" stroke="currentColor" stroke-width="1.5" opacity="0.25"/>
              <circle cx="40" cy="40" r="6" fill="currentColor" opacity="0.3"/>
            </svg>
          </div>
          <p>SELECT MEMOS TO BEGIN</p>
          <p class="idle-hint">Choose uncompiled memos and configure compilation settings</p>
        </div>

        <!-- Compile Result -->
        <CompileResult
          v-if="!isCompiling && (finalScore > 0 || wikiContent || errorMsg || jobId)"
          :final-score="finalScore"
          :total-events="traceEvents.length"
          :duration-sec="durationSec"
          :wiki-content="wikiContent"
          :semantic-links="semanticLinks"
          :error-msg="errorMsg"
          :job-id="jobId"
        />
      </main>
    </div>

    <!-- Human Review Panel (overlay) -->
    <HumanReviewPanel
      v-if="reviewTaskId"
      :task-id="reviewTaskId"
      :review-score="reviewScore"
      :review-feedback="reviewFeedback"
      :wiki-content="wikiContent || ''"
      @decision="handleReviewDecision"
    />
  </div>
</template>

<style scoped>
.compile-view {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 32px 18px;
  border-bottom: 1px solid var(--border-dim);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.title-prefix {
  font-family: var(--font-mono);
  font-size: 1rem;
  color: var(--accent);
  opacity: 0.6;
}

.page-title {
  font-family: var(--font-display);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.15em;
}

.page-subtitle {
  font-family: var(--font-sans);
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-top: 4px;
  letter-spacing: 0.04em;
}

.mode-toggle {
  display: flex;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.mode-btn {
  padding: 8px 18px;
  font-family: var(--font-display);
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  transition: all var(--transition-fast);
  border-right: 1px solid var(--border);
}

.mode-btn:last-child {
  border-right: none;
}

.mode-btn.active {
  background: var(--accent-ghost);
  color: var(--accent);
}

.mode-btn:hover:not(.active) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.compile-layout {
  flex: 1;
  display: flex;
  gap: 0;
  overflow: hidden;
}

.left-panel {
  width: 340px;
  min-width: 340px;
  border-right: 1px solid var(--border-dim);
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  transition: all var(--transition-smooth);
}

.left-panel.collapsed {
  min-width: 60px;
  width: 60px;
}

.panel-section {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-dim);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-label {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-ghost);
  letter-spacing: 0.1em;
}

.btn-ghost-sm {
  font-family: var(--font-mono);
  font-size: 0.6rem;
  color: var(--accent);
  padding: 2px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.btn-ghost-sm:hover {
  background: var(--accent-ghost);
}

.section-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 32px 0;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.empty-icon {
  width: 40px;
  height: 40px;
  color: var(--text-ghost);
  margin-bottom: 4px;
}

.hint {
  font-size: 0.65rem;
  color: var(--text-ghost);
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.memo-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 320px;
  overflow-y: auto;
}

.memo-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.memo-item:hover {
  background: var(--bg-hover);
}

.memo-item.selected {
  background: var(--accent-ghost);
  border-color: var(--border);
}

.memo-item input[type="checkbox"] {
  margin-top: 3px;
  accent-color: var(--accent);
  cursor: pointer;
}

.memo-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.memo-text {
  font-size: 0.78rem;
  color: var(--text-primary);
  line-height: 1.4;
  word-break: break-word;
}

.memo-date {
  font-family: var(--font-mono);
  font-size: 0.6rem;
  color: var(--text-ghost);
}

.selection-count {
  margin-top: 10px;
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--accent);
}

.config-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.config-item label {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.config-select,
.config-input {
  padding: 8px 12px;
  background: var(--bg-deep);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.75rem;
}

.config-select:focus,
.config-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: var(--glow-sm);
}

.config-select option {
  background: var(--bg-deep);
  color: var(--text-primary);
}

.config-input[type="number"] {
  width: 80px;
}

.checkbox-item label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.checkbox-item input[type="checkbox"] {
  accent-color: var(--accent);
}

.action-bar {
  padding: 20px;
  margin-top: auto;
  border-top: 1px solid var(--border-dim);
}

.btn-start {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 14px 24px;
  font-family: var(--font-display);
  font-size: 0.85rem;
  font-weight: 600;
  letter-spacing: 0.1em;
}

.btn-start:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-icon {
  width: 16px;
  height: 16px;
}

.btn-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.right-panel {
  flex: 1;
  padding: 24px 32px;
  overflow-y: auto;
}

.idle-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 400px;
}

.idle-visual {
  width: 80px;
  height: 80px;
  margin-bottom: 24px;
  color: var(--text-ghost);
}

.idle-state p {
  font-family: var(--font-display);
  font-size: 0.9rem;
  letter-spacing: 0.15em;
  color: var(--text-muted);
}

.idle-hint {
  font-size: 0.75rem !important;
  color: var(--text-ghost) !important;
  margin-top: 8px;
}
</style>
