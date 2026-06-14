<script setup lang="ts">
import { computed } from 'vue'
import type { SemanticLink } from '../api/compile'

const props = defineProps<{
  finalScore: number
  totalEvents: number
  durationSec: number | null
  wikiContent: string | null
  semanticLinks: SemanticLink[]
  errorMsg: string | null
}>()

const scoreColor = computed(() => {
  if (props.finalScore >= 8.5) return 'var(--neon-green)'
  if (props.finalScore >= 7.0) return 'var(--neon-yellow)'
  if (props.finalScore > 0) return 'var(--neon-orange)'
  return 'var(--text-muted)'
})

const scoreLabel = computed(() => {
  if (props.finalScore >= 8.5) return 'EXCELLENT'
  if (props.finalScore >= 7.0) return 'GOOD'
  if (props.finalScore > 0) return 'NEEDS WORK'
  return 'PENDING'
})

const formattedDuration = computed(() => {
  if (!props.durationSec) return '--'
  const m = Math.floor(props.durationSec / 60)
  const s = Math.round(props.durationSec % 60)
  return m > 0 ? `${m}m ${s}s` : `${s}s`
})

const relationColors: Record<string, string> = {
  extends: 'var(--neon-cyan)',
  supports: 'var(--neon-green)',
  contradicts: 'var(--neon-orange)',
  related: 'var(--neon-magenta)',
}
</script>

<template>
  <div class="compile-result">
    <!-- Score Card -->
    <div class="score-card">
      <div class="score-circle" :style="{ borderColor: scoreColor, color: scoreColor }">
        <span class="score-value">{{ finalScore > 0 ? finalScore.toFixed(1) : '--' }}</span>
        <span class="score-label">{{ scoreLabel }}</span>
      </div>
      <div class="score-stats">
        <div class="stat">
          <span class="stat-value">{{ totalEvents }}</span>
          <span class="stat-label">EVENTS</span>
        </div>
        <div class="stat">
          <span class="stat-value">{{ formattedDuration }}</span>
          <span class="stat-label">DURATION</span>
        </div>
        <div class="stat">
          <span class="stat-value">{{ semanticLinks.length }}</span>
          <span class="stat-label">LINKS</span>
        </div>
      </div>
    </div>

    <!-- Error State -->
    <div v-if="errorMsg" class="error-block">
      <div class="error-header">
        <svg viewBox="0 0 20 20" fill="currentColor" class="error-icon">
          <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
        </svg>
        <span>COMPILATION ERROR</span>
      </div>
      <p class="error-msg">{{ errorMsg }}</p>
    </div>

    <!-- Wiki Preview -->
    <div v-if="wikiContent" class="wiki-preview">
      <div class="section-header">
        <svg viewBox="0 0 20 20" fill="currentColor" class="section-icon">
          <path d="M9 2a1 1 0 00-.894.553L6.382 6H3a1 1 0 000 2h1.07l.938 8.442A1 1 0 006.001 17h7.998a1 1 0 00.993-.558L15.93 8H17a1 1 0 100-2h-3.382L11.894 2.553A1 1 0 0011 2H9z"/>
        </svg>
        <span>WIKI OUTPUT</span>
      </div>
      <div class="wiki-content">
        <pre>{{ wikiContent }}</pre>
      </div>
    </div>

    <!-- Semantic Links -->
    <div v-if="semanticLinks.length" class="links-section">
      <div class="section-header">
        <svg viewBox="0 0 20 20" fill="currentColor" class="section-icon">
          <path fill-rule="evenodd" d="M12.586 4.586a2 2 0 112.828 2.828l-3 3a2 2 0 01-2.828 0 1 1 0 00-1.414 1.414 4 4 0 005.656 0l3-3a4 4 0 00-5.656-5.656l-1.5 1.5a1 1 0 101.414 1.414l1.5-1.5zm-5 5a2 2 0 012.828 0 1 1 0 101.414-1.414 4 4 0 00-5.656 0l-3 3a4 4 0 105.656 5.656l1.5-1.5a1 1 0 10-1.414-1.414l-1.5 1.5a2 2 0 11-2.828-2.828l3-3z" clip-rule="evenodd"/>
        </svg>
        <span>SEMANTIC LINKS</span>
      </div>
      <div class="links-list">
        <div
          v-for="link in semanticLinks"
          :key="`${link.source_slug}-${link.target_slug}`"
          class="link-item"
        >
          <div class="link-info">
            <span class="link-source">{{ link.source_slug }}</span>
            <span class="link-arrow">→</span>
            <span class="link-target">{{ link.target_slug }}</span>
            <span
              class="link-type"
              :style="{ color: relationColors[link.relation_type] || 'var(--text-secondary)' }"
            >
              {{ link.relation_type.toUpperCase() }}
            </span>
          </div>
          <div class="link-confidence">
            <div class="confidence-bar">
              <div
                class="confidence-fill"
                :style="{
                  width: (link.confidence * 100) + '%',
                  background: link.confidence >= 0.8
                    ? 'var(--neon-green)'
                    : link.confidence >= 0.7
                      ? 'var(--neon-yellow)'
                      : 'var(--text-muted)'
                }"
              ></div>
            </div>
            <span class="confidence-text">{{ (link.confidence * 100).toFixed(0) }}%</span>
          </div>
          <p v-if="link.reason" class="link-reason">{{ link.reason }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.compile-result {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.score-card {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 20px 24px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.score-circle {
  width: 90px;
  height: 90px;
  border-radius: 50%;
  border: 3px solid;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  flex-shrink: 0;
}

.score-value {
  font-family: var(--font-display);
  font-size: 1.6rem;
  font-weight: 700;
  line-height: 1;
}

.score-label {
  font-family: var(--font-mono);
  font-size: 0.55rem;
  letter-spacing: 0.1em;
  opacity: 0.8;
}

.score-stats {
  display: flex;
  gap: 28px;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-value {
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-label {
  font-family: var(--font-mono);
  font-size: 0.6rem;
  color: var(--text-muted);
  letter-spacing: 0.1em;
}

.error-block {
  padding: 16px 20px;
  background: rgba(255, 0, 0, 0.06);
  border: 1px solid var(--error);
  border-radius: var(--radius-md);
}

.error-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-family: var(--font-display);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--error);
  letter-spacing: 0.1em;
}

.error-icon {
  width: 18px;
  height: 18px;
}

.error-msg {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.5;
  word-break: break-word;
}

.wiki-preview,
.links-section {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border-dim);
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: 0.1em;
}

.section-icon {
  width: 16px;
  height: 16px;
}

.wiki-content {
  padding: 20px;
  max-height: 400px;
  overflow-y: auto;
}

.wiki-content pre {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  margin: 0;
}

.links-list {
  padding: 12px 20px;
}

.link-item {
  padding: 12px 0;
  border-bottom: 1px solid var(--border-dim);
}

.link-item:last-child {
  border-bottom: none;
}

.link-info {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  font-size: 0.8rem;
}

.link-source,
.link-target {
  font-family: var(--font-mono);
  color: var(--text-primary);
}

.link-arrow {
  color: var(--accent);
  font-size: 1rem;
}

.link-type {
  font-family: var(--font-display);
  font-size: 0.6rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  padding: 2px 8px;
  border: 1px solid currentColor;
  border-radius: var(--radius-sm);
  margin-left: auto;
}

.link-confidence {
  display: flex;
  align-items: center;
  gap: 10px;
}

.confidence-bar {
  flex: 1;
  height: 3px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
}

.confidence-text {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-muted);
  min-width: 36px;
  text-align: right;
}

.link-reason {
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-top: 6px;
  line-height: 1.4;
  font-style: italic;
}
</style>
