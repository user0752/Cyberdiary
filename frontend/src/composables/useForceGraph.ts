/** D3-force layout engine composable for 2D knowledge graph. */

import { ref, type Ref } from 'vue'
import * as d3 from 'd3'
import type { GraphNode, GraphEdge } from '@/types/graph'

export interface ForceGraphOptions {
  width: Ref<number>
  height: Ref<number>
  onTick: () => void
}

export function useForceGraph(options: ForceGraphOptions) {
  const simulation = ref<d3.Simulation<GraphNode, GraphEdge> | null>(null)
  const nodesRef = ref<GraphNode[]>([])
  const edgesRef = ref<GraphEdge[]>([])
  // O(1) node lookup by id
  let nodeMap = new Map<string, GraphNode>()

  function rebuildNodeMap() {
    nodeMap.clear()
    for (const n of nodesRef.value) {
      nodeMap.set(n.id, n)
    }
  }

  function init(nodes: GraphNode[], edges: GraphEdge[]) {
    if (simulation.value) {
      simulation.value.stop()
    }

    nodesRef.value = nodes
    edgesRef.value = edges
    rebuildNodeMap()

    const sim = d3
      .forceSimulation<GraphNode>(nodes)
      .force(
        'link',
        d3
          .forceLink<GraphNode, GraphEdge>(edges)
          .id((d) => d.id)
          .distance((d) => {
            const conf = (d as GraphEdge).confidence || 0.5
            return 100 + (1 - conf) * 80
          })
          .strength(0.4),
      )
      .force(
        'charge',
        d3
          .forceManyBody()
          .strength(-400)
          .distanceMin(20)
          .distanceMax(1000),
      )
      .force('center', d3.forceCenter(options.width.value / 2, options.height.value / 2))
      .force(
        'collide',
        d3.forceCollide().radius((d) => {
          const node = d as GraphNode
          // Include label space in collision radius
          return 8 + (node.weight || 0.5) * 25 + 30
        }),
      )
      .alphaDecay(0.02)
      .velocityDecay(0.3)

    sim.on('tick', options.onTick)

    simulation.value = sim
  }

  /** Update simulation incrementally — preserves positions of existing nodes. */
  function updateData(nodes: GraphNode[], edges: GraphEdge[]) {
    const sim = simulation.value
    if (!sim) {
      init(nodes, edges)
      return
    }

    const existingMap = new Map<string, GraphNode>()
    for (const n of nodesRef.value) {
      existingMap.set(n.id, n)
    }

    for (const node of nodes) {
      const existing = existingMap.get(node.id)
      if (existing) {
        node.x = existing.x
        node.y = existing.y
        node.vx = existing.vx
        node.vy = existing.vy
        node.fx = existing.fx
        node.fy = existing.fy
      }
    }

    nodesRef.value = nodes
    edgesRef.value = edges
    rebuildNodeMap()

    sim.nodes(nodes)

    const linkForce = sim.force('link') as d3.ForceLink<GraphNode, GraphEdge>
    if (linkForce) {
      linkForce.links(edges)
    }

    sim.alpha(0.3).restart()
  }

  function reheat() {
    simulation.value?.alpha(1).restart()
  }

  function updateCenter() {
    const sim = simulation.value
    if (!sim) return
    const centerForce = sim.force('center') as d3.ForceCenter<GraphNode>
    if (centerForce) {
      centerForce.x(options.width.value / 2)
      centerForce.y(options.height.value / 2)
    }
  }

  function stopNode(nodeId: string) {
    const node = nodeMap.get(nodeId)
    if (node) {
      node.fx = node.x
      node.fy = node.y
      // Set alphaTarget once at drag start — simulation stays alive during drag
      simulation.value?.alphaTarget(0.1).restart()
    }
  }

  function releaseNode(nodeId: string) {
    const node = nodeMap.get(nodeId)
    if (node) {
      node.fx = null
      node.fy = null
    }
  }

  function dragNode(nodeId: string, x: number, y: number) {
    const node = nodeMap.get(nodeId)
    if (node) {
      node.fx = x
      node.fy = y
      // Don't restart simulation here — it's already running from stopNode
    }
  }

  function dragEnd(nodeId: string) {
    const node = nodeMap.get(nodeId)
    if (node) {
      node.fx = null
      node.fy = null
      simulation.value?.alphaTarget(0)
    }
  }

  function dispose() {
    simulation.value?.stop()
    simulation.value = null
    nodeMap.clear()
  }

  return {
    simulation,
    nodesRef,
    edgesRef,
    init,
    updateData,
    reheat,
    updateCenter,
    stopNode,
    releaseNode,
    dragNode,
    dragEnd,
    dispose,
  }
}
