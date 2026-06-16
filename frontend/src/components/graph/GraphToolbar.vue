<template>
  <div class="graph-toolbar glass-panel">
    <!-- Search -->
    <div class="search-section">
      <div class="search-box">
        <svg class="search-icon" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd" />
        </svg>
        <input
          v-model="keyword"
          type="text"
          placeholder="搜索节点..."
          @input="onSearch"
          @keydown.escape="clearSearch"
        />
        <button v-if="keyword" class="clear-btn" @click="clearSearch">&times;</button>
      </div>
      <div v-if="store.searchResults.length > 0" class="search-dropdown">
        <div
          v-for="result in store.searchResults"
          :key="result.id"
          class="search-item"
          @click="focusNode(result.id)"
        >
          <span class="dot" :style="{ background: getColor(result.type) }" />
          <span class="label">{{ result.label }}</span>
          <span class="type">{{ getTypeLabel(result.type) }}</span>
        </div>
      </div>
    </div>

    <!-- Node type filters -->
    <div class="filter-section">
      <div class="filter-label">节点类型</div>
      <div class="filter-chips">
        <button
          v-for="(config, type) in nodeTypeOptions"
          :key="type"
          class="chip"
          :class="{ active: store.activeNodeTypes.has(type) }"
          :style="chipStyle(type, config.bg)"
          @click="store.toggleNodeType(type)"
        >
          <span class="chip-dot" :style="{ background: config.bg }" />
          {{ config.label }}
          <span class="count">({{ store.stats.nodeTypeCounts[type] || 0 }})</span>
        </button>
      </div>
    </div>

    <!-- Actions -->
    <div class="action-section">
      <button class="action-btn" @click="$emit('reset')" title="重置布局">
        <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd" /></svg>
      </button>
      <button class="action-btn" @click="$emit('fullscreen')" title="全屏">
        <svg viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M3 4a1 1 0 011-1h4a1 1 0 010 2H6.414l2.293 2.293a1 1 0 01-1.414 1.414L5 6.414V8a1 1 0 01-2 0V4zm9 1a1 1 0 110-2h4a1 1 0 011 1v4a1 1 0 11-2 0V6.414l-2.293 2.293a1 1 0 11-1.414-1.414L13.586 5H12zm-9 7a1 1 0 112 0v1.586l2.293-2.293a1 1 0 011.414 1.414L5.414 15H7a1 1 0 110 2H3a1 1 0 01-1-1v-4zm13.707 4.707a1 1 0 010-1.414L14.586 15H13a1 1 0 110-2h4a1 1 0 011 1v4a1 1 0 11-2 0v-1.586l-2.293 2.293a1 1 0 01-1.414-1.414z" clip-rule="evenodd" /></svg>
      </button>
    </div>

    <!-- Stats -->
    <div class="stats-section">
      <span class="stat">节点 {{ store.stats.totalNodes }}</span>
      <span class="divider">·</span>
      <span class="stat">边 {{ store.stats.totalEdges }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { NODE_COLORS, getNodeColor } from '@/types/graph'
import { useKnowledgeGraphStore } from '@/stores/knowledgeGraph'

defineEmits<{
  reset: []
  fullscreen: []
}>()

const store = useKnowledgeGraphStore()
const keyword = ref('')
let debounceTimer: ReturnType<typeof setTimeout> | null = null

onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
})

// Filter out wiki-only types from the node type options
const nodeTypeOptions = computed(() => {
  const result: Record<string, { bg: string; label: string }> = {}
  for (const [key, config] of Object.entries(NODE_COLORS)) {
    // Only show entity types, not wiki page types
    if (['technology', 'concept', 'person', 'organization', 'tool', 'framework', 'language', 'method', 'theory', 'other'].includes(key)) {
      result[key] = config
    }
  }
  return result
})

function getColor(type: string): string {
  return getNodeColor(type).bg
}

function getTypeLabel(type: string): string {
  return getNodeColor(type).label
}

function chipStyle(type: string, color: string) {
  const active = store.activeNodeTypes.has(type)
  return {
    borderColor: active ? color : 'var(--graph-border, rgba(255,255,255,0.08))',
    background: active ? color + '20' : 'transparent',
  }
}

function onSearch() {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    store.search(keyword.value)
  }, 300)
}

function clearSearch() {
  keyword.value = ''
  store.search('')
}

function focusNode(nodeId: string) {
  store.selectNode(nodeId)
  store.hoverNode(nodeId)
  keyword.value = ''
  store.searchResults = []
}
</script>

<style scoped>
.glass-panel {
  background: var(--panel-bg, rgba(15, 15, 35, 0.88));
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.08));
  border-radius: 12px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.graph-toolbar {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 10;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 360px;
  color: var(--text-primary, #f1f5f9);
  font-size: 13px;
}

/* Search */
.search-section {
  position: relative;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 6px 10px;
}

.search-icon {
  width: 14px;
  height: 14px;
  opacity: 0.5;
  flex-shrink: 0;
}

.search-box input {
  flex: 1;
  background: none;
  border: none;
  outline: none;
  color: inherit;
  font-size: 13px;
  min-width: 140px;
}

.search-box input::placeholder {
  opacity: 0.4;
}

.clear-btn {
  background: none;
  border: none;
  color: inherit;
  opacity: 0.5;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  padding: 0 2px;
}

.search-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  background: rgba(15, 15, 35, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 20;
}

.search-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  cursor: pointer;
  transition: background 0.15s;
}

.search-item:hover {
  background: rgba(255, 255, 255, 0.08);
}

.search-item .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.search-item .label {
  flex: 1;
}

.search-item .type {
  font-size: 11px;
  opacity: 0.5;
}

/* Filters */
.filter-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.filter-label {
  font-size: 11px;
  opacity: 0.5;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border: 1px solid;
  border-radius: 12px;
  background: none;
  color: inherit;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.chip:hover {
  opacity: 0.8;
}

.chip-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.chip .count {
  opacity: 0.5;
  font-size: 10px;
}

/* Actions */
.action-section {
  display: flex;
  gap: 6px;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  color: inherit;
  cursor: pointer;
  transition: all 0.15s;
}

.action-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.action-btn svg {
  width: 14px;
  height: 14px;
}

/* Stats */
.stats-section {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  opacity: 0.5;
}

.divider {
  opacity: 0.3;
}
</style>
