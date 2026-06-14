<template>
  <div class="knowledge-graph" ref="containerRef" :data-theme="currentTheme">
    <!-- Loading state -->
    <div v-if="store.loading" class="graph-loading">
      <div class="spinner" />
      <span>加载图谱数据...</span>
    </div>

    <!-- Error state -->
    <div v-else-if="store.error" class="graph-error">
      <span>{{ store.error }}</span>
      <button @click="loadGraph">重试</button>
    </div>

    <!-- Empty state -->
    <div v-else-if="!store.graph || store.graph.nodes.length === 0" class="graph-empty">
      <svg viewBox="0 0 20 20" fill="currentColor" class="empty-icon">
        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
        <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/>
      </svg>
      <span>暂无图谱数据</span>
      <span class="empty-hint">编译完成后将自动生成知识图谱</span>
    </div>

    <!-- Graph content -->
    <template v-else>
      <!-- Compilation progress bar (when compiling) -->
      <CompilationProgressBar
        v-if="showProgress"
        :current-phase="currentPhase"
        :progress-percent="progressPercent"
        :message="progressMessage"
      />

      <!-- Toolbar -->
      <GraphToolbar @reset="onReset" @fullscreen="toggleFullscreen" />

      <!-- Mode switcher -->
      <div class="mode-switcher">
        <button
          class="mode-btn"
          :class="{ active: viewMode === '2d' }"
          @click="switchMode('2d')"
        >
          <svg viewBox="0 0 20 20" fill="currentColor"><rect x="3" y="3" width="14" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
          2D 图谱
        </button>
        <button
          class="mode-btn"
          :class="{ active: viewMode === '3d' }"
          @click="switchMode('3d')"
        >
          <svg viewBox="0 0 20 20" fill="currentColor"><path d="M10 2L2 7l8 5 8-5-8-5zM2 13l8 5 8-5M2 7v6l8 5 8-5V7" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
          3D 沉浸
        </button>
      </div>

      <!-- 2D Graph -->
      <ForceGraph2D v-show="viewMode === '2d'" ref="graph2dRef" />

      <!-- 3D Graph -->
      <ForceGraph3D v-show="viewMode === '3d'" ref="graph3dRef" />

      <!-- Legend (2D only) -->
      <GraphLegend v-show="viewMode === '2d'" />

      <!-- MiniMap (2D only) -->
      <MiniMap
        v-show="viewMode === '2d'"
        :main-width="containerWidth"
        :main-height="containerHeight"
        :transform="graph2dRef?.transform || defaultTransform"
        @pan-to="onPanTo"
      />

      <!-- Entity detail panel -->
      <EntityDetailPanel />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useKnowledgeGraphStore } from '@/stores/knowledgeGraph'
import { useSettingsStore } from '@/stores/settings'
import ForceGraph2D from './ForceGraph2D.vue'
import ForceGraph3D from './ForceGraph3D.vue'
import GraphToolbar from './GraphToolbar.vue'
import GraphLegend from './GraphLegend.vue'
import MiniMap from './MiniMap.vue'
import EntityDetailPanel from './EntityDetailPanel.vue'
import CompilationProgressBar from './CompilationProgressBar.vue'

const props = defineProps<{
  jobId: string
  showProgress?: boolean
  currentPhase?: string
  progressPercent?: number
  progressMessage?: string
}>()

const store = useKnowledgeGraphStore()
const settingsStore = useSettingsStore()
const graph2dRef = ref<InstanceType<typeof ForceGraph2D> | null>(null)
const graph3dRef = ref<InstanceType<typeof ForceGraph3D> | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
const containerWidth = ref(800)
const containerHeight = ref(600)
const defaultTransform = { x: 0, y: 0, k: 1 }
const currentTheme = computed(() => {
  const t = settingsStore.theme
  return t === 'cyberpunk' ? 'dark' : t
})
const viewMode = ref<'2d' | '3d'>('2d')

let resizeObs: ResizeObserver | null = null

async function loadGraph() {
  await store.loadGraph(props.jobId)
}

function switchMode(mode: '2d' | '3d') {
  if (mode === '3d' && graph3dRef.value && !graph3dRef.value.webglAvailable) {
    // WebGL not available, stay in 2D
    return
  }
  viewMode.value = mode
}

function onReset() {
  store.resetFilters()
  if (viewMode.value === '2d') {
    graph2dRef.value?.reheat()
  } else {
    graph3dRef.value?.resetView()
  }
}

function toggleFullscreen() {
  const el = containerRef.value
  if (!el) return
  if (document.fullscreenElement) {
    document.exitFullscreen()
  } else {
    el.requestFullscreen()
  }
}

function onPanTo(worldX: number, worldY: number) {
  if (!graph2dRef.value) return
  const t = graph2dRef.value.transform
  t.x = containerWidth.value / 2 - worldX * t.k
  t.y = containerHeight.value / 2 - worldY * t.k
  graph2dRef.value.requestRender()
}

onMounted(() => {
  loadGraph()

  if (containerRef.value) {
    resizeObs = new ResizeObserver((entries) => {
      containerWidth.value = entries[0].contentRect.width
      containerHeight.value = entries[0].contentRect.height
    })
    resizeObs.observe(containerRef.value)
  }

  // Theme is now reactive via computed — no manual sync needed
})

onUnmounted(() => {
  resizeObs?.disconnect()
  store.$reset()
})
</script>

<style scoped>
.knowledge-graph {
  position: relative;
  width: 100%;
  height: 600px;
  min-height: 400px;
  background: var(--graph-bg, #0a0a1a);
  border-radius: 12px;
  overflow: hidden;
}

.knowledge-graph:fullscreen {
  height: 100vh;
  border-radius: 0;
}

/* Mode switcher */
.mode-switcher {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  display: flex;
  gap: 0;
  background: var(--panel-bg, rgba(15, 15, 35, 0.88));
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.08));
  border-radius: 8px;
  overflow: hidden;
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: none;
  border: none;
  color: var(--text-primary, #f1f5f9);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  opacity: 0.5;
  transition: all 0.15s;
}

.mode-btn:hover {
  opacity: 0.8;
}

.mode-btn.active {
  opacity: 1;
  background: rgba(99, 102, 241, 0.15);
  color: #6366f1;
}

.mode-btn svg {
  width: 14px;
  height: 14px;
}

/* Loading */
.graph-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: var(--text-primary, #f1f5f9);
  opacity: 0.6;
}

.spinner {
  width: 28px;
  height: 28px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-top-color: var(--accent, #6366f1);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Error */
.graph-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: var(--text-primary, #f1f5f9);
}

.graph-error button {
  padding: 6px 16px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.3);
  border-radius: 6px;
  color: var(--accent, #6366f1);
  cursor: pointer;
}

/* Empty */
.graph-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 8px;
  color: var(--text-primary, #f1f5f9);
  opacity: 0.5;
}

.empty-icon {
  width: 36px;
  height: 36px;
  margin-bottom: 4px;
}

.empty-hint {
  font-size: 12px;
  opacity: 0.5;
}

/* Theme variables */
.knowledge-graph {
  --graph-bg: #0a0a1a;
  --panel-bg: rgba(15, 15, 35, 0.88);
  --panel-border: rgba(255, 255, 255, 0.08);
  --text-primary: #f1f5f9;
  --text-secondary: #94a3b8;
  --accent: #6366f1;
}

.knowledge-graph[data-theme="light"] {
  --graph-bg: #f8fafc;
  --panel-bg: rgba(255, 255, 255, 0.90);
  --panel-border: rgba(0, 0, 0, 0.08);
  --text-primary: #0f172a;
  --text-secondary: #64748b;
  --accent: #6366f1;
}
</style>
