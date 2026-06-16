<template>
  <div class="graph-legend glass-panel" :class="{ collapsed: !expanded }">
    <button class="legend-toggle" @click="expanded = !expanded">
      <span>图例</span>
      <svg :class="{ rotated: expanded }" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd" />
      </svg>
    </button>
    <Transition name="legend-expand">
      <div v-if="expanded" class="legend-content">
        <div class="legend-section">
          <div class="section-title">节点类型</div>
          <div class="legend-item" v-for="(config, type) in nodeTypes" :key="type">
            <span class="legend-dot" :style="{ background: config.bg }" />
            <span>{{ config.label }}</span>
          </div>
        </div>
        <div class="legend-divider" />
        <div class="legend-section">
          <div class="section-title">边类型</div>
          <div class="legend-item">
            <span class="legend-line solid" />
            <span>直接关系</span>
          </div>
          <div class="legend-item">
            <span class="legend-line dashed" />
            <span>间接关系</span>
          </div>
          <div class="legend-item">
            <span class="legend-line arrow" />
            <span>有向边</span>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { NODE_COLORS } from '@/types/graph'

const expanded = ref(false)

// Only show entity types (not wiki page types)
const nodeTypes = Object.fromEntries(
  Object.entries(NODE_COLORS).filter(([key]) =>
    ['technology', 'concept', 'person', 'organization', 'tool', 'framework', 'language', 'method', 'theory', 'other'].includes(key)
  )
)
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

.graph-legend {
  position: absolute;
  bottom: 12px;
  left: 12px;
  z-index: 10;
  color: var(--text-primary, #f1f5f9);
  font-size: 12px;
  overflow: hidden;
  transition: width 0.3s cubic-bezier(0.16, 1, 0.3, 1),
              height 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.legend-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 8px 12px;
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
}

.legend-toggle svg {
  width: 14px;
  height: 14px;
  transition: transform 0.2s;
}

.legend-toggle svg.rotated {
  transform: rotate(180deg);
}

.legend-content {
  padding: 0 12px 10px;
}

.legend-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-title {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  opacity: 0.4;
  margin-bottom: 2px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-line {
  width: 24px;
  height: 0;
  border-top: 2px solid #94a3b8;
  flex-shrink: 0;
}

.legend-line.dashed {
  border-top-style: dashed;
}

.legend-line.arrow {
  position: relative;
}

.legend-line.arrow::after {
  content: '';
  position: absolute;
  right: 0;
  top: -4px;
  border: 3px solid transparent;
  border-left: 4px solid #94a3b8;
}

.legend-divider {
  height: 1px;
  background: rgba(255, 255, 255, 0.06);
  margin: 6px 0;
}

/* Expand transition */
.legend-expand-enter-active,
.legend-expand-leave-active {
  transition: opacity 0.2s, max-height 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  max-height: 300px;
  overflow: hidden;
}

.legend-expand-enter-from,
.legend-expand-leave-to {
  opacity: 0;
  max-height: 0;
}
</style>
