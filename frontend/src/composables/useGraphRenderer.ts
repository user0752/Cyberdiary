/** Canvas 2D renderer composable for knowledge graph. */

import type { Ref } from 'vue'
import type { GraphNode, GraphEdge } from '@/types/graph'
import { NODE_COLORS, EDGE_STYLES, getNodeColor, getEdgeStyle, getEdgeSourceId, getEdgeTargetId } from '@/types/graph'

const BASE_RADIUS = 8
const WEIGHT_SCALE = 25
const NODE_FONT = '12px Inter, -apple-system, sans-serif'
const LABEL_FONT = '10px Inter, -apple-system, sans-serif'

export interface RenderState {
  nodes: GraphNode[]
  edges: GraphEdge[]
  transform: { x: number; y: number; k: number }
  hoveredNodeId: string | null
  highlightedNodeIds: Set<string>
  highlightedEdgeIds: Set<string>
  dimUnhighlighted: boolean
}

export function useGraphRenderer(canvas: Ref<HTMLCanvasElement | null>) {
  function render(state: RenderState) {
    const cvs = canvas.value
    if (!cvs) return

    const ctx = cvs.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const w = cvs.clientWidth
    const h = cvs.clientHeight
    const pw = Math.round(w * dpr)
    const ph = Math.round(h * dpr)

    // Resize canvas for HiDPI
    if (cvs.width !== pw || cvs.height !== ph) {
      cvs.width = pw
      cvs.height = ph
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, w, h)

    // Apply pan/zoom transform
    ctx.save()
    ctx.translate(state.transform.x, state.transform.y)
    ctx.scale(state.transform.k, state.transform.k)

    // Build node lookup map for O(1) edge rendering
    const nodeMap = new Map<string, GraphNode>()
    for (const node of state.nodes) {
      nodeMap.set(node.id, node)
    }

    // Draw edges first (below nodes)
    for (const edge of state.edges) {
      drawEdge(ctx, edge, state, nodeMap)
    }

    // Draw nodes
    for (const node of state.nodes) {
      drawNode(ctx, node, state)
    }

    ctx.restore()
  }

  function drawNode(ctx: CanvasRenderingContext2D, node: GraphNode, state: RenderState) {
    const x = node.x ?? 0
    const y = node.y ?? 0
    const radius = BASE_RADIUS + (node.weight || 0.5) * WEIGHT_SCALE
    const color = getNodeColor(node.type as string)
    const isHovered = state.hoveredNodeId === node.id
    const isHighlighted = !state.dimUnhighlighted || state.highlightedNodeIds.has(node.id)
    const alpha = isHighlighted ? 1.0 : 0.15

    ctx.save()
    ctx.globalAlpha = alpha

    // Glow effect for hovered node
    if (isHovered) {
      ctx.shadowColor = color.glow
      ctx.shadowBlur = 20
    }

    // Composite node (double ring) for high-weight nodes
    if (node.weight >= 0.7) {
      const outerR = radius * 1.3
      ctx.beginPath()
      ctx.arc(x, y, outerR, 0, Math.PI * 2)
      ctx.fillStyle = color.bg + '40' // 25% opacity hex
      ctx.fill()
    }

    // Main circle
    ctx.beginPath()
    ctx.arc(x, y, radius, 0, Math.PI * 2)
    ctx.fillStyle = color.bg
    ctx.fill()

    // Hover scale effect
    if (isHovered) {
      ctx.beginPath()
      ctx.arc(x, y, radius * 1.2, 0, Math.PI * 2)
      ctx.strokeStyle = '#ffffff80'
      ctx.lineWidth = 2
      ctx.stroke()
    }

    ctx.shadowColor = 'transparent'
    ctx.shadowBlur = 0

    // Label
    if (state.transform.k > 0.4 || isHovered) {
      ctx.font = isHovered ? `bold ${NODE_FONT}` : NODE_FONT
      ctx.fillStyle = isHighlighted ? '#f1f5f9' : '#94a3b8'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillText(node.label, x, y + radius + 4)
    }

    ctx.restore()
  }

  function drawEdge(ctx: CanvasRenderingContext2D, edge: GraphEdge, state: RenderState, nodeMap: Map<string, GraphNode>) {
    const srcId = getEdgeSourceId(edge)
    const tgtId = getEdgeTargetId(edge)
    const srcNode = nodeMap.get(srcId)
    const tgtNode = nodeMap.get(tgtId)
    if (!srcNode || !tgtNode) return

    const x1 = srcNode.x ?? 0
    const y1 = srcNode.y ?? 0
    const x2 = tgtNode.x ?? 0
    const y2 = tgtNode.y ?? 0

    const style = getEdgeStyle(edge.type as string)
    const isHighlighted = !state.dimUnhighlighted || state.highlightedEdgeIds.has(edge.id)
    const isHovered = state.hoveredNodeId === srcId || state.hoveredNodeId === tgtId
    const alpha = isHighlighted ? (isHovered ? 0.9 : style.opacity) : 0.05

    ctx.save()
    ctx.globalAlpha = alpha
    ctx.strokeStyle = style.color
    ctx.lineWidth = 1 + (edge.confidence || 0.5) * 3

    if (style.dash) {
      ctx.setLineDash([6, 4])
    }

    // Draw line
    ctx.beginPath()
    ctx.moveTo(x1, y1)
    ctx.lineTo(x2, y2)
    ctx.stroke()

    ctx.setLineDash([])

    // Arrow for directed edges
    if (edge.directed) {
      drawArrow(ctx, x1, y1, x2, y2, style.color, alpha)
    }

    // Edge label on hover
    if (isHovered && edge.label) {
      const mx = (x1 + x2) / 2
      const my = (y1 + y2) / 2
      ctx.font = LABEL_FONT
      ctx.fillStyle = '#94a3b8'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'bottom'

      // Background pill
      const text = edge.label
      const tw = ctx.measureText(text).width + 8
      ctx.fillStyle = 'rgba(15,23,42,0.85)'
      roundRect(ctx, mx - tw / 2, my - 16, tw, 18, 4)
      ctx.fill()

      ctx.fillStyle = '#94a3b8'
      ctx.fillText(text, mx, my - 2)
    }

    ctx.restore()
  }

  function drawArrow(
    ctx: CanvasRenderingContext2D,
    x1: number,
    y1: number,
    x2: number,
    y2: number,
    color: string,
    alpha: number,
  ) {
    const angle = Math.atan2(y2 - y1, x2 - x1)
    const headLen = 8
    // Move arrow tip back so it doesn't overlap the node circle
    const tipX = x2 - Math.cos(angle) * 15
    const tipY = y2 - Math.sin(angle) * 15

    ctx.save()
    ctx.globalAlpha = alpha
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.moveTo(tipX, tipY)
    ctx.lineTo(
      tipX - headLen * Math.cos(angle - Math.PI / 6),
      tipY - headLen * Math.sin(angle - Math.PI / 6),
    )
    ctx.lineTo(
      tipX - headLen * Math.cos(angle + Math.PI / 6),
      tipY - headLen * Math.sin(angle + Math.PI / 6),
    )
    ctx.closePath()
    ctx.fill()
    ctx.restore()
  }

  function roundRect(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    w: number,
    h: number,
    r: number,
  ) {
    ctx.beginPath()
    ctx.moveTo(x + r, y)
    ctx.lineTo(x + w - r, y)
    ctx.arcTo(x + w, y, x + w, y + r, r)
    ctx.lineTo(x + w, y + h - r)
    ctx.arcTo(x + w, y + h, x + w - r, y + h, r)
    ctx.lineTo(x + r, y + h)
    ctx.arcTo(x, y + h, x, y + h - r, r)
    ctx.lineTo(x, y + r)
    ctx.arcTo(x, y, x + r, y, r)
    ctx.closePath()
  }

  return { render }
}
