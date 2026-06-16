<template>
  <div class="force-graph-2d" ref="containerRef">
    <canvas ref="canvasRef" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useForceGraph } from '@/composables/useForceGraph'
import { useGraphRenderer, type RenderState } from '@/composables/useGraphRenderer'
import { useGraphInteraction } from '@/composables/useGraphInteraction'
import { useKnowledgeGraphStore } from '@/stores/knowledgeGraph'

const store = useKnowledgeGraphStore()
const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
const width = ref(800)
const height = ref(600)
const transform = ref({ x: 0, y: 0, k: 1 })

// Neighbor cache for hover highlighting
let neighborCache: { nodeIds: Set<string>; edgeIds: Set<string> } | null = null

// Force graph
const forceGraph = useForceGraph({
  width,
  height,
  onTick: requestRender,
})

// Renderer
const renderer = useGraphRenderer(canvasRef)

// Hover throttle — only process hover at most once per animation frame
let pendingHoverNodeId: string | null | undefined = undefined // undefined = no pending
function throttledOnNodeHover(nodeId: string | null) {
  if (pendingHoverNodeId === nodeId) return // already pending same value
  pendingHoverNodeId = nodeId
  requestRender() // will process in doRender
}

function processPendingHover() {
  if (pendingHoverNodeId === undefined) return
  const nodeId = pendingHoverNodeId as string | null
  pendingHoverNodeId = undefined

  store.hoverNode(nodeId)
  if (nodeId) {
    neighborCache = interaction.getNeighbors(nodeId)
  } else {
    neighborCache = null
  }
}

// Interaction
const interaction = useGraphInteraction({
  canvas: canvasRef,
  nodes: forceGraph.nodesRef,
  edges: forceGraph.edgesRef,
  transform,
  width,
  height,
  onNodeHover: throttledOnNodeHover,
  onNodeSelect(nodeId) {
    store.selectNode(nodeId)
    requestRender()
  },
  onTransformChange() {
    requestRender()
  },
  onNodeDragStart(nodeId) {
    forceGraph.stopNode(nodeId)
  },
  onNodeDrag(nodeId, x, y) {
    forceGraph.dragNode(nodeId, x, y)
  },
  onNodeDragEnd(nodeId) {
    forceGraph.dragEnd(nodeId)
  },
})

// Render scheduling
let rafId = 0

function requestRender() {
  cancelAnimationFrame(rafId)
  rafId = requestAnimationFrame(doRender)
}

function doRender() {
  processPendingHover()
  const state: RenderState = {
    nodes: store.filteredNodes,
    edges: store.filteredEdges,
    transform: transform.value,
    hoveredNodeId: store.hoveredNodeId,
    selectedNodeId: store.selectedNodeId,
    highlightedNodeIds: neighborCache?.nodeIds ?? new Set(),
    highlightedEdgeIds: neighborCache?.edgeIds ?? new Set(),
    dimUnhighlighted: !!store.hoveredNodeId,
  }
  renderer.render(state)
}

// Resize observer
let resizeObs: ResizeObserver | null = null

onMounted(() => {
  if (containerRef.value) {
    resizeObs = new ResizeObserver((entries) => {
      width.value = entries[0].contentRect.width
      height.value = entries[0].contentRect.height
      forceGraph.updateCenter()
      requestRender()
    })
    resizeObs.observe(containerRef.value)
  }
  interaction.setupListeners()
})

onUnmounted(() => {
  resizeObs?.disconnect()
  interaction.cleanup()
  forceGraph.dispose()
  cancelAnimationFrame(rafId)
})

// Track whether this is the first data load
let isFirstLoad = true

// Re-init layout when data changes
watch(
  () => [store.filteredNodes, store.filteredEdges],
  () => {
    neighborCache = null // Invalidate stale highlight cache
    const nodes = store.filteredNodes
    const edges = store.filteredEdges
    if (nodes.length > 0) {
      // Center transform on first load
      if (transform.value.x === 0 && transform.value.y === 0) {
        transform.value.x = width.value / 2
        transform.value.y = height.value / 2
      }
      if (isFirstLoad || !forceGraph.simulation.value) {
        forceGraph.init(nodes, edges)
        forceGraph.reheat()
        isFirstLoad = false
      } else {
        // Incremental update — preserves positions of existing nodes
        forceGraph.updateData(nodes, edges)
      }
    }
  },
  { immediate: true, deep: false },
)

// Expose for parent component
defineExpose({ requestRender, reheat: forceGraph.reheat, transform })
</script>

<style scoped>
.force-graph-2d {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

.force-graph-2d canvas {
  width: 100%;
  height: 100%;
  display: block;
  cursor: grab;
}

.force-graph-2d canvas:active {
  cursor: grabbing;
}
</style>
