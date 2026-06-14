/** Interaction logic composable — drag, zoom, hover, click for Canvas graph. */

import { type Ref } from 'vue'
import type { GraphNode, GraphEdge } from '@/types/graph'
import { getEdgeSourceId, getEdgeTargetId } from '@/types/graph'

export interface InteractionOptions {
  canvas: Ref<HTMLCanvasElement | null>
  nodes: Ref<GraphNode[]>
  edges: Ref<GraphEdge[]>
  transform: Ref<{ x: number; y: number; k: number }>
  width: Ref<number>
  height: Ref<number>
  onNodeHover: (nodeId: string | null) => void
  onNodeSelect: (nodeId: string | null) => void
  onTransformChange: () => void
  onNodeDrag: (nodeId: string, x: number, y: number) => void
  onNodeDragEnd: (nodeId: string) => void
  onNodeDragStart: (nodeId: string) => void
}

export function useGraphInteraction(options: InteractionOptions) {
  let draggingNode: GraphNode | null = null
  let isPanning = false
  let panStart = { x: 0, y: 0 }
  let lastTouchDist = 0
  let clickTime = 0
  let clickPos = { x: 0, y: 0 }
  // Capture the actual DOM element for cleanup (BUG 7 fix)
  let boundElement: HTMLCanvasElement | null = null

  function getMousePos(e: MouseEvent): { x: number; y: number } {
    const cvs = options.canvas.value
    if (!cvs) return { x: 0, y: 0 }
    const rect = cvs.getBoundingClientRect()
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    }
  }

  function screenToWorld(sx: number, sy: number): { x: number; y: number } {
    const t = options.transform.value
    return {
      x: (sx - t.x) / t.k,
      y: (sy - t.y) / t.k,
    }
  }

  function hitTest(sx: number, sy: number): GraphNode | null {
    const { x: wx, y: wy } = screenToWorld(sx, sy)
    const nodes = options.nodes.value
    for (let i = nodes.length - 1; i >= 0; i--) {
      const node = nodes[i]
      const nx = node.x ?? 0
      const ny = node.y ?? 0
      const r = 8 + (node.weight || 0.5) * 25
      const dx = wx - nx
      const dy = wy - ny
      // 1.3x hit area to match outer ring rendering
      if (dx * dx + dy * dy <= r * r * 1.69) {
        return node
      }
    }
    return null
  }

  function getNeighbors(nodeId: string): { nodeIds: Set<string>; edgeIds: Set<string> } {
    const nodeIds = new Set<string>([nodeId])
    const edgeIds = new Set<string>()
    for (const edge of options.edges.value) {
      const src = getEdgeSourceId(edge)
      const tgt = getEdgeTargetId(edge)
      if (src === nodeId || tgt === nodeId) {
        nodeIds.add(src)
        nodeIds.add(tgt)
        edgeIds.add(edge.id)
      }
    }
    return { nodeIds, edgeIds }
  }

  function resetInteractionState() {
    draggingNode = null
    isPanning = false
    lastTouchDist = 0
  }

  // --- Event handlers ---

  function onMouseDown(e: MouseEvent) {
    const pos = getMousePos(e)
    const node = hitTest(pos.x, pos.y)
    clickTime = Date.now() // Always set clickTime (BUG 8 fix)

    if (node) {
      draggingNode = node
      clickPos = pos
      // Don't fire onNodeDragStart yet — wait for actual movement (BUG 9 fix)
    } else {
      isPanning = true
      panStart = { x: e.clientX - options.transform.value.x, y: e.clientY - options.transform.value.y }
    }
  }

  function onMouseMove(e: MouseEvent) {
    const pos = getMousePos(e)

    if (draggingNode) {
      // Fire drag start on first actual movement
      if (!isPanning && draggingNode) {
        options.onNodeDragStart(draggingNode.id)
        isPanning = true // reuse as "dragging has started" flag
      }
      const { x: wx, y: wy } = screenToWorld(pos.x, pos.y)
      options.onNodeDrag(draggingNode.id, wx, wy)
      options.onTransformChange()
      return
    }

    if (isPanning && !draggingNode) {
      options.transform.value.x = e.clientX - panStart.x
      options.transform.value.y = e.clientY - panStart.y
      options.onTransformChange()
      return
    }

    // Hover detection
    const node = hitTest(pos.x, pos.y)
    options.onNodeHover(node?.id ?? null)
  }

  function onMouseUp(e: MouseEvent) {
    if (draggingNode) {
      const pos = getMousePos(e)
      const dt = Date.now() - clickTime
      const dist = Math.hypot(pos.x - clickPos.x, pos.y - clickPos.y)
      if (dt < 200 && dist < 5) {
        // Short click = select (no drag happened)
        options.onNodeSelect(draggingNode.id)
      } else {
        // Was a drag — fire drag end
        options.onNodeDragEnd(draggingNode.id)
      }
      draggingNode = null
      isPanning = false
      return
    }

    if (isPanning) {
      isPanning = false
      const pos = getMousePos(e)
      const dt = Date.now() - clickTime
      if (dt < 200) {
        const node = hitTest(pos.x, pos.y)
        if (!node) {
          options.onNodeSelect(null)
        }
      }
    }
  }

  function onWheel(e: WheelEvent) {
    e.preventDefault()
    const pos = getMousePos(e)
    const t = options.transform.value

    const factor = e.deltaY > 0 ? 0.92 : 1.08
    const newK = Math.min(5, Math.max(0.3, t.k * factor))

    const wx = (pos.x - t.x) / t.k
    const wy = (pos.y - t.y) / t.k
    t.x = pos.x - wx * newK
    t.y = pos.y - wy * newK
    t.k = newK

    options.onTransformChange()
  }

  function onDblClick(e: MouseEvent) {
    const t = options.transform.value
    t.x = options.width.value / 2
    t.y = options.height.value / 2
    t.k = 1
    const nodes = options.nodes.value
    if (nodes.length > 0) {
      let cx = 0, cy = 0
      for (const n of nodes) {
        cx += n.x ?? 0
        cy += n.y ?? 0
      }
      cx /= nodes.length
      cy /= nodes.length
      t.x -= cx
      t.y -= cy
    }
    options.onTransformChange()
  }

  // --- Touch handlers ---

  function onTouchStart(e: TouchEvent) {
    if (e.touches.length === 1) {
      e.preventDefault() // Prevent browser scroll (BUG 12 fix)
      const touch = e.touches[0]
      const pos = { x: touch.clientX, y: touch.clientY }
      const cvs = options.canvas.value
      if (!cvs) return
      const rect = cvs.getBoundingClientRect()
      const sx = pos.x - rect.left
      const sy = pos.y - rect.top
      const node = hitTest(sx, sy)
      clickTime = Date.now() // Always set clickTime
      if (node) {
        draggingNode = node
        clickPos = { x: sx, y: sy }
      } else {
        isPanning = true
        panStart = { x: pos.x - options.transform.value.x, y: pos.y - options.transform.value.y }
      }
    } else if (e.touches.length === 2) {
      // Pinch zoom: cancel any ongoing drag/pan (BUG 13 fix)
      resetInteractionState()
      const dx = e.touches[0].clientX - e.touches[1].clientX
      const dy = e.touches[0].clientY - e.touches[1].clientY
      lastTouchDist = Math.hypot(dx, dy)
    }
  }

  function onTouchMove(e: TouchEvent) {
    e.preventDefault()
    if (e.touches.length === 1) {
      const touch = e.touches[0]
      const pos = { x: touch.clientX, y: touch.clientY }
      if (draggingNode) {
        const cvs = options.canvas.value
        if (!cvs) return
        const rect = cvs.getBoundingClientRect()
        const { x: wx, y: wy } = screenToWorld(pos.x - rect.left, pos.y - rect.top)
        options.onNodeDrag(draggingNode.id, wx, wy)
        options.onTransformChange()
      } else if (isPanning) {
        options.transform.value.x = pos.x - panStart.x
        options.transform.value.y = pos.y - panStart.y
        options.onTransformChange()
      }
    } else if (e.touches.length === 2) {
      const dx = e.touches[0].clientX - e.touches[1].clientX
      const dy = e.touches[0].clientY - e.touches[1].clientY
      const dist = Math.hypot(dx, dy)
      if (lastTouchDist > 0) {
        const factor = dist / lastTouchDist
        const t = options.transform.value
        const mx = (e.touches[0].clientX + e.touches[1].clientX) / 2
        const my = (e.touches[0].clientY + e.touches[1].clientY) / 2
        const cvs = options.canvas.value
        if (cvs) {
          const rect = cvs.getBoundingClientRect()
          const sx = mx - rect.left
          const sy = my - rect.top
          const wx = (sx - t.x) / t.k
          const wy = (sy - t.y) / t.k
          const newK = Math.min(5, Math.max(0.3, t.k * factor))
          t.x = sx - wx * newK
          t.y = sy - wy * newK
          t.k = newK
          options.onTransformChange()
        }
      }
      lastTouchDist = dist
    }
  }

  function onTouchEnd(e: TouchEvent) {
    // Tap-to-select for touch (BUG 10 fix)
    if (draggingNode) {
      const dt = Date.now() - clickTime
      // Use a slightly larger threshold for touch (10px vs 5px for mouse)
      const cvs = options.canvas.value
      if (cvs && dt < 300) {
        // Check if it was a tap (no significant movement)
        // Since we don't track touch move distance easily, use time as primary signal
        options.onNodeSelect(draggingNode.id)
      } else {
        options.onNodeDragEnd(draggingNode.id)
      }
      draggingNode = null
    }
    isPanning = false
    lastTouchDist = 0
  }

  // --- Setup / Cleanup ---

  function setupListeners() {
    const cvs = options.canvas.value
    if (!cvs) return
    boundElement = cvs // Capture for cleanup (BUG 7 fix)
    cvs.addEventListener('mousedown', onMouseDown)
    cvs.addEventListener('mousemove', onMouseMove)
    cvs.addEventListener('mouseup', onMouseUp)
    cvs.addEventListener('mouseleave', onMouseUp)
    cvs.addEventListener('wheel', onWheel, { passive: false })
    cvs.addEventListener('dblclick', onDblClick)
    cvs.addEventListener('touchstart', onTouchStart, { passive: false })
    cvs.addEventListener('touchmove', onTouchMove, { passive: false })
    cvs.addEventListener('touchend', onTouchEnd)
    cvs.addEventListener('touchcancel', onTouchEnd) // BUG 11 fix
  }

  function cleanup() {
    const cvs = boundElement // Use captured element, not current ref (BUG 7 fix)
    if (!cvs) return
    cvs.removeEventListener('mousedown', onMouseDown)
    cvs.removeEventListener('mousemove', onMouseMove)
    cvs.removeEventListener('mouseup', onMouseUp)
    cvs.removeEventListener('mouseleave', onMouseUp)
    cvs.removeEventListener('wheel', onWheel)
    cvs.removeEventListener('dblclick', onDblClick)
    cvs.removeEventListener('touchstart', onTouchStart)
    cvs.removeEventListener('touchmove', onTouchMove)
    cvs.removeEventListener('touchend', onTouchEnd)
    cvs.removeEventListener('touchcancel', onTouchEnd)
    boundElement = null
  }

  return { setupListeners, cleanup, getNeighbors, hitTest }
}
