<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{
  taskId: string
  reviewScore: number
  reviewFeedback: string[]
  wikiContent: string
}>()

const emit = defineEmits<{
  decision: [decision: 'approve' | 'revise' | 'reject', editedWiki?: string]
}>()

const activeTab = ref<'preview' | 'edit'>('preview')
const editedContent = ref('')
const submitting = ref(false)

function handleDecision(decision: 'approve' | 'revise' | 'reject') {
  submitting.value = true
  const wiki = activeTab.value === 'edit' ? editedContent.value : undefined
  emit('decision', decision, wiki)
}
</script>

<template>
  <div class="human-review">
    <div class="review-header">
      <div class="header-left">
        <svg viewBox="0 0 20 20" fill="currentColor" class="header-icon">
          <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/>
        </svg>
        <h3>HUMAN REVIEW REQUIRED</h3>
      </div>
      <span class="task-id">Task: {{ taskId.slice(0, 8) }}...</span>
    </div>

    <!-- Score -->
    <div class="review-score">
      <span class="score-badge" :class="reviewScore >= 7 ? 'pass' : 'fail'">
        {{ reviewScore.toFixed(1) }}
      </span>
      <span class="score-desc">Quality Score</span>
    </div>

    <!-- Feedback -->
    <div v-if="reviewFeedback.length" class="review-feedback">
      <div class="section-label">// FEEDBACK</div>
      <ul>
        <li v-for="(fb, i) in reviewFeedback" :key="i">{{ fb }}</li>
      </ul>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'preview' }"
        @click="activeTab = 'preview'"
      >PREVIEW</button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'edit' }"
        @click="activeTab = 'edit'"
      >EDIT</button>
    </div>

    <!-- Content -->
    <div class="tab-content">
      <pre v-if="activeTab === 'preview'" class="wiki-preview">{{ wikiContent }}</pre>
      <textarea
        v-else
        v-model="editedContent"
        class="wiki-editor"
        rows="15"
        spellcheck="false"
      ></textarea>
    </div>

    <!-- Decision Buttons -->
    <div class="decision-row">
      <button
        class="btn-decision reject"
        :disabled="submitting"
        @click="handleDecision('reject')"
      >
        <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/></svg>
        TERMINATE
      </button>
      <button
        class="btn-decision revise"
        :disabled="submitting"
        @click="handleDecision('revise')"
      >
        <svg viewBox="0 0 20 20" fill="currentColor"><path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"/></svg>
        REVISE
      </button>
      <button
        class="btn-decision approve"
        :disabled="submitting"
        @click="handleDecision('approve')"
      >
        <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
        APPROVE
      </button>
    </div>
  </div>
</template>

<style scoped>
.human-review {
  background: var(--bg-card);
  border: 1px solid var(--neon-yellow);
  border-radius: var(--radius-md);
  overflow: hidden;
  animation: pulse-border 2s ease-in-out infinite;
}

@keyframes pulse-border {
  0%, 100% { border-color: var(--neon-yellow); }
  50% { border-color: rgba(240, 255, 0, 0.4); }
}

.review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  background: rgba(240, 255, 0, 0.06);
  border-bottom: 1px solid var(--border-dim);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-icon {
  width: 18px;
  height: 18px;
  color: var(--neon-yellow);
}

.review-header h3 {
  font-family: var(--font-display);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--neon-yellow);
  letter-spacing: 0.1em;
}

.task-id {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-muted);
}

.review-score {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-dim);
}

.score-badge {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-family: var(--font-display);
  font-size: 0.95rem;
  font-weight: 700;
}

.score-badge.pass {
  color: var(--neon-green);
  border: 2px solid var(--neon-green);
  background: rgba(0, 255, 136, 0.06);
}

.score-badge.fail {
  color: var(--neon-orange);
  border: 2px solid var(--neon-orange);
  background: rgba(255, 107, 0, 0.06);
}

.score-desc {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.review-feedback {
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-dim);
}

.section-label {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-ghost);
  margin-bottom: 8px;
  letter-spacing: 0.1em;
}

.review-feedback ul {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.review-feedback li {
  font-size: 0.78rem;
  color: var(--text-secondary);
  padding-left: 16px;
  position: relative;
  line-height: 1.5;
}

.review-feedback li::before {
  content: '▸';
  position: absolute;
  left: 0;
  color: var(--neon-yellow);
}

.tabs {
  display: flex;
  border-bottom: 1px solid var(--border-dim);
}

.tab-btn {
  flex: 1;
  padding: 10px;
  font-family: var(--font-display);
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.1em;
  text-align: center;
  border-bottom: 2px solid transparent;
  transition: all var(--transition-fast);
}

.tab-btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.tab-btn.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.tab-content {
  padding: 16px 20px;
}

.wiki-preview {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--text-secondary);
  white-space: pre-wrap;
  line-height: 1.6;
  max-height: 300px;
  overflow-y: auto;
  margin: 0;
}

.wiki-editor {
  width: 100%;
  padding: 12px;
  background: var(--bg-deep);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  line-height: 1.6;
  resize: vertical;
}

.wiki-editor:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: var(--glow-sm);
}

.decision-row {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-dim);
}

.btn-decision {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  transition: all var(--transition-fast);
}

.btn-decision svg {
  width: 16px;
  height: 16px;
}

.btn-decision:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-decision.reject {
  background: rgba(255, 0, 0, 0.08);
  border: 1px solid rgba(255, 0, 0, 0.3);
  color: var(--error);
}

.btn-decision.reject:hover:not(:disabled) {
  background: rgba(255, 0, 0, 0.15);
  box-shadow: 0 0 12px rgba(255, 0, 0, 0.2);
}

.btn-decision.revise {
  background: rgba(240, 255, 0, 0.06);
  border: 1px solid rgba(240, 255, 0, 0.3);
  color: var(--neon-yellow);
}

.btn-decision.revise:hover:not(:disabled) {
  background: rgba(240, 255, 0, 0.12);
  box-shadow: 0 0 12px rgba(240, 255, 0, 0.15);
}

.btn-decision.approve {
  background: rgba(0, 255, 136, 0.06);
  border: 1px solid rgba(0, 255, 136, 0.3);
  color: var(--neon-green);
}

.btn-decision.approve:hover:not(:disabled) {
  background: rgba(0, 255, 136, 0.12);
  box-shadow: 0 0 12px rgba(0, 255, 136, 0.15);
}
</style>
