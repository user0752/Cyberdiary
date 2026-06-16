<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { TraceEntry, CompileProgress } from '../api/compile'

const props = defineProps<{
  traceEvents: TraceEntry[]
  progress: CompileProgress | null
  isCompiling: boolean
}>()

const expandedIndex = ref<number | null>(null)

const STAGES = [
  { key: 'Coordinator', label: 'COORD', layer: 'L0', icon: '◈' },
  { key: 'Researcher', label: 'RSRCH', layer: 'L1', icon: '◆' },
  { key: 'Integrator', label: 'INTEG', layer: 'L1', icon: '◇' },
  { key: 'Writer', label: 'WRITE', layer: 'L2', icon: '◉' },
  { key: 'Reviewer(accuracy)', label: 'ACC', layer: 'L3', icon: '◎' },
  { key: 'Reviewer(readability)', label: 'READ', layer: 'L3', icon: '◐' },
  { key: 'Arbiter', label: 'ARB', layer: 'L3', icon: '⬡' },
  { key: 'Editor', label: 'EDIT', layer: 'L4', icon: '✎' },
  { key: 'Linker', label: 'LINK', layer: 'L4', icon: '↗' },
]

const completedStages = computed(() => {
  const completed = new Set<string>()
  for (const ev of props.traceEvents) {
    if (ev.event === 'phase_end') {
      completed.add(ev.phase)
    }
  }
  return completed
})

const currentAgent = computed(() => {
  return props.progress?.current_agent || null
})

const logEntries = computed(() => {
  return props.traceEvents.map((ev, i) => ({
    ...ev,
    index: i,
    time: formatTimestamp(ev.timestamp),
  }))
})

function formatTimestamp(ts: string) {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return '--:--:--'
  }
}

function eventIcon(eventType: string) {
  switch (eventType) {
    case 'phase_start': return '▸'
    case 'phase_end': return '✓'
    case 'llm_request': return '↑'
    case 'llm_response': return '↓'
    default: return '·'
  }
}

function eventColor(eventType: string) {
  switch (eventType) {
    case 'phase_start': return 'var(--neon-cyan)'
    case 'phase_end': return 'var(--neon-green)'
    case 'llm_request': return 'var(--neon-yellow)'
    case 'llm_response': return 'var(--neon-magenta)'
    default: return 'var(--text-muted)'
  }
}

function toggleExpand(i: number) {
  expandedIndex.value = expandedIndex.value === i ? null : i
}

// Auto-scroll to latest when new events arrive
const logContainer = ref<HTMLElement | null>(null)
watch(
  () => props.traceEvents.length,
  () => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight
    }
  },
)
</script>

<template>
  <div class="trace-panel">
    <!-- Pipeline Progress -->
    <div class="pipeline">
      <div class="pipeline-label">// PIPELINE</div>
      <div class="pipeline-bar">
        <div
          v-for="stage in STAGES"
          :key="stage.key"
          class="stage-node"
          :class="{
            completed: completedStages.has(stage.key),
            active: currentAgent === stage.key && isCompiling,
          }"
          :title="`${stage.label} (${stage.layer})`"
        >
          <span class="stage-icon">{{ stage.icon }}</span>
          <span class="stage-label">{{ stage.label }}</span>
          <div class="stage-connector" v-if="STAGES.indexOf(stage) < STAGES.length - 1"></div>
        </div>
      </div>
    </div>

    <!-- Progress Bar -->
    <div v-if="progress" class="progress-section">
      <div class="progress-bar-wrap">
        <div
          class="progress-fill"
          :class="{ compiling: isCompiling }"
          :style="{ width: (progress.progress || 0) + '%' }"
        ></div>
      </div>
      <div class="progress-meta">
        <span class="progress-pct">{{ progress.progress || 0 }}%</span>
        <span class="progress-msg">{{ progress.message }}</span>
      </div>
    </div>

    <!-- Event Timeline -->
    <div class="timeline">
      <div class="timeline-label">// EVENT LOG</div>
      <div class="log-stream" ref="logContainer">
        <div v-if="logEntries.length === 0" class="log-empty">
          <span class="empty-icon">◎</span>
          <span>{{ isCompiling ? 'Awaiting events...' : 'No events yet' }}</span>
          <span v-if="isCompiling" class="blink-cursor">▌</span>
        </div>

        <div
          v-for="entry in logEntries"
          :key="entry.index"
          class="log-entry"
          :class="{ expanded: expandedIndex === entry.index }"
          @click="toggleExpand(entry.index)"
        >
          <div class="entry-line">
            <span class="entry-time">{{ entry.time }}</span>
            <span class="entry-icon" :style="{ color: eventColor(entry.event) }">
              {{ eventIcon(entry.event) }}
            </span>
            <span class="entry-agent">{{ entry.phase || entry.agent }}</span>
            <span class="entry-layer">{{ entry.layer }}</span>
            <span class="entry-msg">{{ entry.message }}</span>
            <span v-if="isCompiling && entry.index === logEntries.length - 1" class="blink-cursor">▌</span>
          </div>

          <!-- Expanded Details -->
          <div v-if="expandedIndex === entry.index && entry.data" class="entry-detail">
            <pre>{{ JSON.stringify(entry.data, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.trace-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pipeline-label,
.timeline-label {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-ghost);
  margin-bottom: 10px;
  letter-spacing: 0.1em;
}

.pipeline-bar {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 12px 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow-x: auto;
}

.stage-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 48px;
  position: relative;
  opacity: 0.35;
  transition: all var(--transition-fast);
}

.stage-node.completed {
  opacity: 0.8;
}

.stage-node.active {
  opacity: 1;
}

.stage-node.active .stage-icon {
  animation: pulse 1s ease-in-out infinite;
}

.stage-icon {
  font-size: 0.9rem;
}

.stage-label {
  font-family: var(--font-mono);
  font-size: 0.5rem;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.stage-connector {
  position: absolute;
  top: 10px;
  left: calc(100% - 4px);
  width: 12px;
  height: 1px;
  background: var(--border);
}

.stage-node.completed .stage-connector {
  background: var(--accent-dim);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.progress-section {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 16px;
}

.progress-bar-wrap {
  height: 3px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--neon-magenta));
  border-radius: 2px;
  transition: width 0.4s ease;
}

.progress-fill.compiling {
  animation: progress-glow 2s ease-in-out infinite;
}

@keyframes progress-glow {
  0%, 100% { box-shadow: 0 0 8px var(--accent-glow); }
  50% { box-shadow: 0 0 16px var(--accent-glow); }
}

.progress-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.progress-pct {
  font-family: var(--font-display);
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--accent);
  min-width: 36px;
}

.progress-msg {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-secondary);
}

.log-stream {
  max-height: 320px;
  overflow-y: auto;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 0;
}

.log-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.empty-icon {
  font-size: 0.9rem;
}

.blink-cursor {
  color: var(--accent);
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.log-entry {
  padding: 6px 16px;
  cursor: pointer;
  border-bottom: 1px solid var(--border-dim);
  transition: background var(--transition-fast);
}

.log-entry:hover {
  background: var(--bg-hover);
}

.log-entry.expanded {
  background: var(--bg-tertiary);
}

.entry-line {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.72rem;
}

.entry-time {
  font-family: var(--font-mono);
  font-size: 0.6rem;
  color: var(--text-ghost);
  min-width: 60px;
}

.entry-icon {
  font-size: 0.7rem;
  min-width: 14px;
  text-align: center;
}

.entry-agent {
  font-family: var(--font-display);
  font-size: 0.65rem;
  font-weight: 500;
  color: var(--text-primary);
  min-width: 100px;
  letter-spacing: 0.05em;
}

.entry-layer {
  font-family: var(--font-mono);
  font-size: 0.55rem;
  color: var(--accent);
  padding: 1px 6px;
  background: var(--accent-ghost);
  border-radius: var(--radius-sm);
  min-width: 28px;
  text-align: center;
}

.entry-msg {
  flex: 1;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.entry-detail {
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--bg-deep);
  border-radius: var(--radius-sm);
}

.entry-detail pre {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
  margin: 0;
  max-height: 160px;
  overflow-y: auto;
}
</style>
