<template>
  <div class="mini-map glass-panel" :class="{ collapsed: !expanded }">
    <button class="map-toggle" @click="expanded = !expanded" title="迷你地图">
      <svg viewBox="0 0 20 20" fill="currentColor">
        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"/>
        <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"/>
      </svg>
    </button>
    <canvas
      v-if="expanded"
      ref="miniCanvas"
      class="mini-canvas"
      @mousedown="onMiniMouseDown"
      @mousemove="onMiniMouseMove"
      @mouseup="onMiniMouseUp"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted, watch } from 'vue'
import { useKnowledgeGraphStore } from '@/stores/knowledgeGraph'
import { getNodeColor } from '@/types/graph'

const props = defineProps<{
  mainWidth: number
  mainHeight: number
  transform: { x: number; y: number; k: number }
}>()

const emit = defineEmits<{
  panTo: [x: number, y: number]
}>()

const store = useKnowledgeGraphStore()
const expanded = ref(false)
const miniCanvas = ref<HTMLCanvasElement | null>(null)
const MAP_W = 160
const MAP_H = 120
let isDraggingViewport = false

function renderMiniMap() {
  const cvs = miniCanvas.value
  if (!cvs || !store.graph) return
  const ctx = cvs.getContext('2d')
  if (!ctx) return

  const dpr = window.devicePixelRatio || 1
  cvs.width = MAP_W * dpr
  cvs.height = MAP_H * dpr
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, MAP_W, MAP_H)

  const nodes = store.graph.nodes
  if (nodes.length === 0) return

  // Compute bounding box of all nodes
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const n of nodes) {
    const x = n.x ?? 0
    const y = n.y ?? 0
    if (x < minX) minX = x
    if (x > maxX) maxX = x
    if (y < minY) minY = y
    if (y > maxY) maxY = y
  }

  const padding = 20
  minX -= padding; maxX += padding; minY -= padding; maxY += padding
  const rangeX = maxX - minX || 1
  const rangeY = maxY - minY || 1
  const scale = Math.min(MAP_W / rangeX, MAP_H / rangeY)

  const offsetX = (MAP_W - rangeX * scale) / 2
  const offsetY = (MAP_H - rangeY * scale) / 2

  function toMini(x: number, y: number): [number, number] {
    return [(x - minX) * scale + offsetX, (y - minY) * scale + offsetY]
  }

  // Draw edges
  ctx.strokeStyle = 'rgba(148, 163, 184, 0.2)'
  ctx.lineWidth = 0.5
  for (const edge of store.graph.edges) {
    const srcNode = nodes.find(n => n.id === (typeof edge.source === 'object' ? edge.source.id : edge.source))
    const tgtNode = nodes.find(n => n.id === (typeof edge.target === 'object' ? edge.target.id : edge.target))
    if (!srcNode || !tgtNode) continue
    const [x1, y1] = toMini(srcNode.x ?? 0, srcNode.y ?? 0)
    const [x2, y2] = toMini(tgtNode.x ?? 0, tgtNode.y ?? 0)
    ctx.beginPath()
    ctx.moveTo(x1, y1)
    ctx.lineTo(x2, y2)
    ctx.stroke()
  }

  // Draw nodes
  for (const node of nodes) {
    const [mx, my] = toMini(node.x ?? 0, node.y ?? 0)
    const color = getNodeColor(node.type as string)
    ctx.beginPath()
    ctx.arc(mx, my, 2, 0, Math.PI * 2)
    ctx.fillStyle = color.bg
    ctx.fill()
  }

  // Draw viewport rectangle
  const t = props.transform
  const viewLeft = (-t.x) / t.k
  const viewTop = (-t.y) / t.k
  const viewRight = viewLeft + props.mainWidth / t.k
  const viewBottom = viewTop + props.mainHeight / t.k

  const [vx1, vy1] = toMini(viewLeft, viewTop)
  const [vx2, vy2] = toMini(viewRight, viewBottom)

  ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)'
  ctx.lineWidth = 1
  ctx.strokeRect(vx1, vy1, vx2 - vx1, vy2 - vy1)
}

function getMiniToGraphCoords(mx: number, my: number): { x: number; y: number } | null {
  const nodes = store.graph?.nodes
  if (!nodes || nodes.length === 0) return null

  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const n of nodes) {
    const x = n.x ?? 0, y = n.y ?? 0
    if (x < minX) minX = x; if (x > maxX) maxX = x
    if (y < minY) minY = y; if (y > maxY) maxY = y
  }
  const padding = 20
  minX -= padding; maxX += padding; minY -= padding; maxY += padding
  const rangeX = (maxX - minX) || 1
  const rangeY = (maxY - minY) || 1
  const scale = Math.min(MAP_W / rangeX, MAP_H / rangeY)
  const offsetX = (MAP_W - rangeX * scale) / 2
  const offsetY = (MAP_H - rangeY * scale) / 2

  const graphX = (mx - offsetX) / scale + minX
  const graphY = (my - offsetY) / scale + minY
  return { x: graphX, y: graphY }
}

function onMiniMouseDown(e: MouseEvent) {
  isDraggingViewport = true
  panToMiniPos(e)
}

function onMiniMouseMove(e: MouseEvent) {
  if (isDraggingViewport) panToMiniPos(e)
}

function onMiniMouseUp() {
  isDraggingViewport = false
}

function panToMiniPos(e: MouseEvent) {
  const cvs = miniCanvas.value
  if (!cvs) return
  const rect = cvs.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  const coords = getMiniToGraphCoords(mx, my)
  if (coords) {
    emit('panTo', coords.x, coords.y)
  }
}

let rafId = 0

function scheduleRender() {
  cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(renderMiniMap)
}

onUnmounted(() => {
  cancelAnimationFrame(rafId)
})

watch(() => props.transform, scheduleRender, { deep: true })
watch(expanded, (v) => { if (v) scheduleRender() })
watch(() => store.graph?.nodes, scheduleRender, { deep: true })
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

.mini-map {
  position: absolute;
  bottom: 12px;
  right: 12px;
  z-index: 10;
  overflow: hidden;
  transition: width 0.2s, height 0.2s;
}

.mini-map.collapsed {
  width: 32px;
  height: 32px;
}

.map-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: none;
  border: none;
  color: var(--text-primary, #f1f5f9);
  cursor: pointer;
  opacity: 0.6;
  transition: opacity 0.15s;
}

.map-toggle:hover {
  opacity: 1;
}

.map-toggle svg {
  width: 14px;
  height: 14px;
}

.mini-canvas {
  display: block;
  width: 160px;
  height: 120px;
  cursor: pointer;
}
</style>
