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

  function init(nodes: GraphNode[], edges: GraphEdge[]) {
    // Stop existing simulation
    if (simulation.value) {
      simulation.value.stop()
    }

    nodesRef.value = nodes
    edgesRef.value = edges

    // Create simulation
    const sim = d3
      .forceSimulation<GraphNode>(nodes)
      .force(
        'link',
        d3
          .forceLink<GraphNode, GraphEdge>(edges)
          .id((d) => d.id)
          .distance((d) => {
            // Shorter edges for higher confidence
            const conf = (d as GraphEdge).confidence || 0.5
            return 80 + (1 - conf) * 70
          })
          .strength(0.5),
      )
      .force(
        'charge',
        d3
          .forceManyBody()
          .strength(-200)
          .distanceMin(20)
          .distanceMax(800),
      )
      .force('center', d3.forceCenter(options.width.value / 2, options.height.value / 2))
      .force(
        'collide',
        d3.forceCollide().radius((d) => {
          const node = d as GraphNode
          return 8 + (node.weight || 0.5) * 25 + 10
        }),
      )
      .alphaDecay(0.02)
      .velocityDecay(0.3)

    sim.on('tick', options.onTick)

    simulation.value = sim
  }

  function reheat() {
    simulation.value?.alpha(1).restart()
  }

  function updateCenter() {
    // Update center force when canvas dimensions change
    const sim = simulation.value
    if (!sim) return
    const centerForce = sim.force('center') as d3.ForceCenter<GraphNode>
    if (centerForce) {
      centerForce.x(options.width.value / 2)
      centerForce.y(options.height.value / 2)
    }
  }

  function stopNode(nodeId: string) {
    const node = nodesRef.value.find((n) => n.id === nodeId)
    if (node) {
      node.fx = node.x
      node.fy = node.y
    }
  }

  function releaseNode(nodeId: string) {
    const node = nodesRef.value.find((n) => n.id === nodeId)
    if (node) {
      node.fx = null
      node.fy = null
    }
  }

  function dragNode(nodeId: string, x: number, y: number) {
    const node = nodesRef.value.find((n) => n.id === nodeId)
    if (node) {
      node.fx = x
      node.fy = y
      simulation.value?.alphaTarget(0.1).restart()
    }
  }

  function dragEnd(nodeId: string) {
    const node = nodesRef.value.find((n) => n.id === nodeId)
    if (node) {
      node.fx = null
      node.fy = null
      simulation.value?.alphaTarget(0)
    }
  }

  function dispose() {
    simulation.value?.stop()
    simulation.value = null
  }

  return {
    simulation,
    nodesRef,
    edgesRef,
    init,
    reheat,
    updateCenter,
    stopNode,
    releaseNode,
    dragNode,
    dragEnd,
    dispose,
  }
}
