<template>
  <Transition name="slide">
    <div v-if="store.selectedNodeId && detail" class="entity-detail glass-panel">
      <button class="close-btn" @click="store.selectNode(null)" title="关闭">
        <svg viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
        </svg>
      </button>

      <!-- Header -->
      <div class="detail-header">
        <div class="node-icon" :style="{ background: nodeColor.bg }">
          <span>{{ detail.label.charAt(0).toUpperCase() }}</span>
        </div>
        <div class="header-info">
          <h3 class="node-label">{{ detail.label }}</h3>
          <span class="type-badge" :style="{ color: nodeColor.bg, borderColor: nodeColor.bg }">
            {{ nodeColor.label }}
          </span>
        </div>
      </div>

      <!-- Stats -->
      <section class="detail-section">
        <div class="stat-row">
          <span class="stat-label">权重</span>
          <div class="weight-bar">
            <div class="weight-fill" :style="{ width: (detail.weight * 100) + '%', background: nodeColor.bg }" />
          </div>
          <span class="stat-value">{{ detail.weight.toFixed(2) }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">关联 Memo</span>
          <span class="stat-value">{{ detail.memoCount }} 条</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">分组</span>
          <span class="stat-value">{{ detail.group }}</span>
        </div>
      </section>

      <!-- Description -->
      <section v-if="detail.description" class="detail-section">
        <h4 class="section-title">描述</h4>
        <p class="description">{{ detail.description }}</p>
      </section>

      <!-- Related Edges -->
      <section v-if="detail.relatedEdges.length" class="detail-section">
        <h4 class="section-title">关联关系 ({{ detail.relatedEdges.length }})</h4>
        <div class="relations-list">
          <div
            v-for="edge in detail.relatedEdges"
            :key="edge.id"
            class="relation-item"
            @click="navigateToRelated(edge)"
          >
            <span class="rel-node">{{ getNodeLabel(getOtherId(edge)) }}</span>
            <span class="rel-arrow" :class="{ directed: edge.directed }">
              {{ edge.directed ? (isSource(edge) ? '→' : '←') : '—' }}
            </span>
            <span class="rel-type">{{ edge.label }}</span>
          </div>
        </div>
      </section>

      <!-- Related Wikis -->
      <section v-if="detail.relatedWikis.length" class="detail-section">
        <h4 class="section-title">关联 Wiki</h4>
        <div class="wiki-list">
          <router-link
            v-for="wiki in detail.relatedWikis"
            :key="wiki.slug"
            :to="`/wiki/${wiki.slug}`"
            class="wiki-link"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" class="wiki-icon">
              <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z"/>
            </svg>
            {{ wiki.title }}
          </router-link>
        </div>
      </section>

      <!-- Locate button -->
      <button class="locate-btn" @click="locateInGraph">
        <svg viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clip-rule="evenodd"/>
        </svg>
        在图谱中定位
      </button>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useKnowledgeGraphStore } from '@/stores/knowledgeGraph'
import { getNodeColor, getEdgeSourceId, getEdgeTargetId, type GraphEdge } from '@/types/graph'

const store = useKnowledgeGraphStore()
const detail = computed(() => store.selectedNodeDetail)
const nodeColor = computed(() => getNodeColor(detail.value?.type || 'other'))

function getOtherId(edge: GraphEdge): string {
  const src = getEdgeSourceId(edge)
  const tgt = getEdgeTargetId(edge)
  return src === store.selectedNodeId ? tgt : src
}

function isSource(edge: GraphEdge): boolean {
  return getEdgeSourceId(edge) === store.selectedNodeId
}

function getNodeLabel(nodeId: string): string {
  const node = store.graph?.nodes.find((n) => n.id === nodeId)
  return node?.label || nodeId
}

function navigateToRelated(edge: GraphEdge) {
  const otherId = getOtherId(edge)
  store.selectNode(otherId)
}

function locateInGraph() {
  // Emit event that parent can handle to pan/zoom to the node
  // For now, just re-select to trigger highlight
  if (store.selectedNodeId) {
    store.hoverNode(store.selectedNodeId)
  }
}
</script>

<style scoped>
.glass-panel {
  background: var(--panel-bg, rgba(15, 15, 35, 0.88));
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.08));
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.entity-detail {
  position: absolute;
  top: 0;
  right: 0;
  width: 380px;
  max-width: 90vw;
  height: 100%;
  z-index: 20;
  padding: 16px;
  overflow-y: auto;
  color: var(--text-primary, #f1f5f9);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.close-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: inherit;
  cursor: pointer;
  transition: background 0.15s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.12);
}

.close-btn svg {
  width: 14px;
  height: 14px;
}

/* Header */
.detail-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-right: 32px;
}

.node-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  color: white;
  flex-shrink: 0;
}

.header-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.node-label {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
  line-height: 1.2;
}

.type-badge {
  font-size: 11px;
  font-weight: 500;
  border: 1px solid;
  border-radius: 10px;
  padding: 1px 8px;
  align-self: flex-start;
}

/* Stats */
.detail-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stat-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
}

.stat-label {
  opacity: 0.5;
  min-width: 60px;
}

.stat-value {
  font-weight: 500;
}

.weight-bar {
  flex: 1;
  height: 4px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 2px;
  overflow: hidden;
}

.weight-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s;
}

/* Description */
.section-title {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  opacity: 0.4;
  margin: 0;
}

.description {
  font-size: 13px;
  line-height: 1.6;
  opacity: 0.8;
  margin: 0;
}

/* Relations */
.relations-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.relation-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.relation-item:hover {
  background: rgba(255, 255, 255, 0.06);
}

.rel-node {
  font-weight: 500;
  color: var(--accent, #6366f1);
}

.rel-arrow {
  opacity: 0.4;
  font-size: 14px;
}

.rel-arrow.directed {
  opacity: 0.6;
}

.rel-type {
  opacity: 0.5;
  margin-left: auto;
  font-size: 11px;
}

/* Wikis */
.wiki-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.wiki-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--accent, #6366f1);
  text-decoration: none;
  transition: background 0.15s;
}

.wiki-link:hover {
  background: rgba(99, 102, 241, 0.1);
}

.wiki-icon {
  width: 14px;
  height: 14px;
  opacity: 0.6;
}

/* Locate button */
.locate-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 8px;
  color: var(--accent, #6366f1);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
  margin-top: auto;
}

.locate-btn:hover {
  background: rgba(99, 102, 241, 0.2);
}

.locate-btn svg {
  width: 14px;
  height: 14px;
}

/* Slide transition */
.slide-enter-active {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1),
              opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-leave-active {
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1),
              opacity 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-enter-from,
.slide-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>
