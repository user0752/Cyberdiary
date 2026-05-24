<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import ForceGraph from 'force-graph'
import type { GraphNode, GraphEdge } from '../api/wiki'

const props = defineProps<{
  nodes: GraphNode[]
  edges: GraphEdge[]
}>()

const router = useRouter()
const containerRef = ref<HTMLDivElement>()
let graph: any = null

// Color map for wiki types
const typeColors: Record<string, string> = {
  concept: '#6366f1',
  entity: '#22c55e',
  comparison: '#f59e0b',
  synthesis: '#ec4899',
  source: '#06b6d4',
}

function initGraph() {
  if (!containerRef.value || !props.nodes.length) return

  // Convert to force-graph format
  const graphData = {
    nodes: props.nodes.map((n) => ({
      id: n.slug,
      name: n.label,
      type: n.type,
      color: typeColors[n.type] || '#6366f1',
    })),
    links: props.edges
      .filter((e) => {
        // Only include edges where both endpoints exist
        const nodeIds = new Set(props.nodes.map((n) => n.slug))
        return nodeIds.has(e.source) && nodeIds.has(e.target)
      })
      .map((e) => ({
        source: e.source,
        target: e.target,
      })),
  }

  if (graph) {
    graph.graphData(graphData)
    return
  }

  graph = new ForceGraph(containerRef.value)
    .graphData(graphData)
    .nodeLabel('name')
    .nodeColor('color')
    .nodeVal(() => 4)
    .nodeAutoColorBy('type')
    .linkColor(() => 'rgba(99, 102, 241, 0.3)')
    .linkDirectionalArrowLength(4)
    .linkDirectionalArrowRelPos(0.9)
    .backgroundColor('transparent')
    .onNodeClick((node: any) => {
      router.push(`/wiki/${node.id}`)
    })
    .d3Force('charge', null)

  // Configure charge force for better spacing
  graph.d3Force('charge')?.strength(-120)

  // Warm up the simulation
  graph.d3VelocityDecay(0.3)
}

onMounted(() => {
  initGraph()
})

watch(
  () => [props.nodes, props.edges],
  () => {
    initGraph()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  if (graph) {
    graph._destructor()
    graph = null
  }
})
</script>

<template>
  <div class="force-graph-container">
    <div v-if="!nodes.length" class="empty-state">
      <span style="font-size: 2rem;">🕸️</span>
      <p>暂无知识图谱数据</p>
      <p class="hint">编译笔记后将自动生成</p>
    </div>
    <div ref="containerRef" class="graph-canvas" :class="{ hidden: !nodes.length }"></div>
  </div>
</template>

<style scoped>
.force-graph-container {
  width: 100%;
  height: 100%;
  min-height: 400px;
  position: relative;
}

.graph-canvas {
  width: 100%;
  height: 100%;
}

.graph-canvas.hidden {
  display: none;
}

.hint {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-top: 4px;
}
</style>
