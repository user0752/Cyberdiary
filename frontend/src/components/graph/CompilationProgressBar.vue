<template>
  <div class="compilation-progress glass-panel">
    <div class="progress-stages">
      <div
        v-for="stage in stages"
        :key="stage.key"
        class="stage"
        :class="{ active: stage.active, done: stage.done, current: stage.current }"
      >
        <span class="stage-icon">{{ stage.icon }}</span>
        <span class="stage-label">{{ stage.label }}</span>
        <div v-if="stage.active" class="pulse" />
      </div>
    </div>
    <div class="progress-bar">
      <div class="progress-fill" :style="{ width: progressPercent + '%' }" />
    </div>
    <div class="progress-info">
      <span class="progress-pct">{{ progressPercent }}%</span>
      <span class="progress-msg">{{ message }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  currentPhase: string
  progressPercent: number
  message: string
}>()

interface Stage {
  key: string
  label: string
  icon: string
  done: boolean
  active: boolean
  current: boolean
}

const phaseOrder = ['coordinator', 'researcher', 'integrator', 'writer', 'reviewer', 'arbiter', 'editor', 'linker']

const phaseMap: Record<string, { label: string; icon: string }> = {
  coordinator: { label: '协调', icon: '🎯' },
  researcher:  { label: '研究', icon: '🔍' },
  integrator:  { label: '整合', icon: '🧩' },
  writer:      { label: '写作', icon: '✍️' },
  reviewer:    { label: '评审', icon: '✅' },
  arbiter:     { label: '仲裁', icon: '⚖️' },
  editor:      { label: '编辑', icon: '🔧' },
  linker:      { label: '链接', icon: '🔗' },
}

const stages = computed<Stage[]>(() => {
  const currentIdx = phaseOrder.indexOf(props.currentPhase)
  return phaseOrder.map((key, i) => {
    const info = phaseMap[key]
    return {
      key,
      label: info.label,
      icon: info.icon,
      done: i < currentIdx,
      active: i === currentIdx,
      current: i === currentIdx,
    }
  })
})
</script>

<style scoped>
.glass-panel {
  background: var(--panel-bg, rgba(15, 15, 35, 0.88));
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid var(--panel-border, rgba(255, 255, 255, 0.08));
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.compilation-progress {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10;
  padding: 10px 16px;
  color: var(--text-primary, #f1f5f9);
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 400px;
  max-width: 90vw;
}

.progress-stages {
  display: flex;
  align-items: center;
  gap: 2px;
}

.stage {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 3px 6px;
  border-radius: 6px;
  font-size: 11px;
  opacity: 0.35;
  transition: all 0.3s;
  position: relative;
}

.stage.done {
  opacity: 0.7;
  color: #10b981;
}

.stage.active {
  opacity: 1;
  background: rgba(99, 102, 241, 0.15);
  color: #6366f1;
}

.stage-icon {
  font-size: 12px;
}

.stage-label {
  font-weight: 500;
}

.pulse {
  position: absolute;
  inset: 0;
  border-radius: 6px;
  border: 1px solid rgba(99, 102, 241, 0.4);
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.02); }
}

.progress-bar {
  height: 3px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #06b6d4);
  border-radius: 2px;
  transition: width 0.5s ease;
}

.progress-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  opacity: 0.6;
}

.progress-pct {
  font-weight: 600;
  min-width: 30px;
}

.progress-msg {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
