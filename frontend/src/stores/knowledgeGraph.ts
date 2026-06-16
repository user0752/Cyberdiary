/** Knowledge graph store — manages graph data and interaction state. */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { KnowledgeGraph, GraphNode, GraphEdge, NodeDetail } from '@/types/graph'
import { getEdgeSourceId, getEdgeTargetId } from '@/types/graph'
import {
  fetchKnowledgeGraph,
  fetchAggregateKnowledgeGraph,
  fetchNodeDetail,
  searchGraphNodes,
} from '@/api/knowledgeGraph'

export const useKnowledgeGraphStore = defineStore('knowledgeGraph', () => {
  // --- Graph data ---
  const graph = ref<KnowledgeGraph | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentJobId = ref<string | null>(null)

  // --- Interaction state ---
  const selectedNodeId = ref<string | null>(null)
  const selectedNodeDetail = ref<NodeDetail | null>(null)
  const hoveredNodeId = ref<string | null>(null)
  const searchKeyword = ref('')
  const searchResults = ref<GraphNode[]>([])

  // --- Filter state ---
  const activeNodeTypes = ref<Set<string>>(new Set())
  const activeEdgeTypes = ref<Set<string>>(new Set())

  // --- Computed ---

  const filteredNodes = computed(() => {
    if (!graph.value) return []
    if (activeNodeTypes.value.size === 0) return graph.value.nodes
    return graph.value.nodes.filter((n) => activeNodeTypes.value.has(n.type))
  })

  const filteredEdges = computed(() => {
    if (!graph.value) return []
    const nodeIds = new Set(filteredNodes.value.map((n) => n.id))
    return graph.value.edges.filter((e) => {
      const src = getEdgeSourceId(e)
      const tgt = getEdgeTargetId(e)
      const typeOk =
        activeEdgeTypes.value.size === 0 || activeEdgeTypes.value.has(e.type)
      return typeOk && nodeIds.has(src) && nodeIds.has(tgt)
    })
  })

  const stats = computed(() => ({
    totalNodes: filteredNodes.value.length,
    totalEdges: filteredEdges.value.length,
    nodeTypeCounts: graph.value?.meta.nodeTypes || ({} as Record<string, number>),
  }))

  // --- Actions ---

  async function loadGraph(jobId: string) {
    loading.value = true
    error.value = null
    currentJobId.value = jobId
    try {
      graph.value = await fetchKnowledgeGraph(jobId)
      // Initialize filters: all types active
      activeNodeTypes.value = new Set(graph.value.nodes.map((n) => n.type))
      activeEdgeTypes.value = new Set(graph.value.edges.map((e) => e.type))
    } catch (e: any) {
      error.value = e.message || 'Failed to load graph'
    } finally {
      loading.value = false
    }
  }

  async function loadAggregateGraph() {
    loading.value = true
    error.value = null
    currentJobId.value = null
    try {
      graph.value = await fetchAggregateKnowledgeGraph()
      activeNodeTypes.value = new Set(graph.value.nodes.map((n) => n.type))
      activeEdgeTypes.value = new Set(graph.value.edges.map((e) => e.type))
    } catch (e: any) {
      error.value = e.message || 'Failed to load graph'
    } finally {
      loading.value = false
    }
  }

  async function loadNodeDetail(nodeId: string) {
    if (!currentJobId.value) return
    try {
      selectedNodeDetail.value = await fetchNodeDetail(currentJobId.value, nodeId)
    } catch {
      selectedNodeDetail.value = null
    }
  }

  function selectNode(nodeId: string | null) {
    selectedNodeId.value = nodeId
    if (nodeId) {
      if (currentJobId.value) {
        loadNodeDetail(nodeId)
      } else {
        // No jobId (aggregate graph) — build detail from local graph data
        buildLocalDetail(nodeId)
      }
    } else {
      selectedNodeDetail.value = null
    }
  }

  /** Build a NodeDetail from local graph data when no jobId is available. */
  function buildLocalDetail(nodeId: string) {
    if (!graph.value) {
      selectedNodeDetail.value = null
      return
    }
    const node = graph.value.nodes.find((n) => n.id === nodeId)
    if (!node) {
      selectedNodeDetail.value = null
      return
    }
    const relatedEdges = graph.value.edges.filter((e) => {
      const src = getEdgeSourceId(e)
      const tgt = getEdgeTargetId(e)
      return src === nodeId || tgt === nodeId
    })
    selectedNodeDetail.value = {
      ...node,
      relatedEdges,
      relatedWikis: [],
    }
  }

  function hoverNode(nodeId: string | null) {
    hoveredNodeId.value = nodeId
  }

  function toggleNodeType(type: string) {
    const s = new Set(activeNodeTypes.value)
    if (s.has(type)) {
      s.delete(type)
    } else {
      s.add(type)
    }
    activeNodeTypes.value = s
  }

  function toggleEdgeType(type: string) {
    const s = new Set(activeEdgeTypes.value)
    if (s.has(type)) {
      s.delete(type)
    } else {
      s.add(type)
    }
    activeEdgeTypes.value = s
  }

  async function search(keyword: string) {
    searchKeyword.value = keyword
    if (!keyword.trim() || !currentJobId.value) {
      searchResults.value = []
      return
    }
    try {
      searchResults.value = await searchGraphNodes(currentJobId.value, keyword)
    } catch {
      searchResults.value = []
    }
  }

  function resetFilters() {
    if (graph.value) {
      activeNodeTypes.value = new Set(graph.value.nodes.map((n) => n.type))
      activeEdgeTypes.value = new Set(graph.value.edges.map((e) => e.type))
    }
  }

  function $reset() {
    graph.value = null
    loading.value = false
    error.value = null
    currentJobId.value = null
    selectedNodeId.value = null
    selectedNodeDetail.value = null
    hoveredNodeId.value = null
    searchKeyword.value = ''
    searchResults.value = []
    activeNodeTypes.value.clear()
    activeEdgeTypes.value.clear()
  }

  return {
    // State
    graph,
    loading,
    error,
    currentJobId,
    selectedNodeId,
    selectedNodeDetail,
    hoveredNodeId,
    searchKeyword,
    searchResults,
    activeNodeTypes,
    activeEdgeTypes,
    // Computed
    filteredNodes,
    filteredEdges,
    stats,
    // Actions
    loadGraph,
    loadAggregateGraph,
    loadNodeDetail,
    selectNode,
    hoverNode,
    toggleNodeType,
    toggleEdgeType,
    search,
    resetFilters,
    $reset,
  }
})
