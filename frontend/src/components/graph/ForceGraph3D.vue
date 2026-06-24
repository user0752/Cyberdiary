<template>
  <div class="force-graph-3d" ref="containerRef" />
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useThreeGraph } from '@/composables/useThreeGraph'
import { useKnowledgeGraphStore } from '@/stores/knowledgeGraph'

const store = useKnowledgeGraphStore()
const containerRef = ref<HTMLDivElement | null>(null)
const width = ref(800)
const height = ref(600)
const webglAvailable = ref(true)
let mounted = false

// Named handlers so they can be removed
function onClick(e: MouseEvent) {
  if (!webglAvailable.value) return
  const rnd = threeGraph.renderer.value
  if (!rnd) return
  const nodeId = threeGraph.hitTest(e.clientX, e.clientY, rnd.domElement)
  store.selectNode(nodeId)
}

function onMouseMove(e: MouseEvent) {
  if (!webglAvailable.value) return
  const rnd = threeGraph.renderer.value
  if (!rnd) return
  const result = threeGraph.throttledHitTest(e.clientX, e.clientY, rnd.domElement)
  if (result === undefined) return // throttled — skip this event
  const nodeId = result
  store.hoverNode(nodeId)
  threeGraph.highlightNode(nodeId)
}

function onMouseLeave() {
  store.hoverNode(null)
  threeGraph.highlightNode(null)
}

const threeGraph = useThreeGraph({
  container: containerRef,
  width,
  height,
})

onMounted(() => {
  // WebGL availability check
  try {
    const testCanvas = document.createElement('canvas')
    const gl = testCanvas.getContext('webgl') || testCanvas.getContext('experimental-webgl')
    if (!gl) {
      webglAvailable.value = false
      return
    }
  } catch {
    webglAvailable.value = false
    return
  }

  try {
    threeGraph.init()
  } catch {
    webglAvailable.value = false
    return
  }

  mounted = true

  // Resize observer
  if (containerRef.value) {
    resizeObs = new ResizeObserver((entries) => {
      width.value = entries[0].contentRect.width
      height.value = entries[0].contentRect.height
      threeGraph.resize()
    })
    resizeObs.observe(containerRef.value)
  }

  // Event listeners (named functions for cleanup)
  containerRef.value?.addEventListener('click', onClick)
  containerRef.value?.addEventListener('mousemove', onMouseMove)
  containerRef.value?.addEventListener('mouseleave', onMouseLeave)

  // Build graph if data is already available
  const nodes = store.filteredNodes
  const edges = store.filteredEdges
  if (nodes.length > 0) {
    threeGraph.buildGraph(nodes, edges)
  }
})

let resizeObs: ResizeObserver | null = null

onUnmounted(() => {
  resizeObs?.disconnect()
  resizeObs = null
  containerRef.value?.removeEventListener('click', onClick)
  containerRef.value?.removeEventListener('mousemove', onMouseMove)
  containerRef.value?.removeEventListener('mouseleave', onMouseLeave)
  threeGraph.dispose()
})

// Watch BOTH nodes and edges — only after mount
watch(
  () => [store.filteredNodes, store.filteredEdges] as [typeof store.filteredNodes, typeof store.filteredEdges],
  ([nodes, edges]) => {
    if (mounted && nodes.length > 0 && webglAvailable.value) {
      threeGraph.buildGraph(nodes, edges)
    }
  },
  { deep: false },
)

defineExpose({
  resetView: threeGraph.resetView,
  setAutoRotate: threeGraph.setAutoRotate,
  focusNode: threeGraph.focusNode,
  webglAvailable,
})
</script>

<style scoped>
.force-graph-3d {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
}

.force-graph-3d :deep(canvas) {
  display: block;
  cursor: grab;
}

.force-graph-3d :deep(canvas):active {
  cursor: grabbing;
}
</style>
