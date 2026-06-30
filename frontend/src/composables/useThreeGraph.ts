/** Three.js 3D renderer composable for knowledge graph — optimized version. */

import { ref, type Ref, shallowRef } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { GraphNode, GraphEdge } from '@/types/graph'
import { getEdgeSourceId, getEdgeTargetId, getNodeColor } from '@/types/graph'

const SPHERE_SEGMENTS = 12
const NODE_SCALE = 0.2

interface Pos3D { x: number; y: number; z: number }

export interface ThreeGraphOptions {
  container: Ref<HTMLDivElement | null>
  width: Ref<number>
  height: Ref<number>
}

export function useThreeGraph(options: ThreeGraphOptions) {
  // Three.js core
  const scene = shallowRef<THREE.Scene | null>(null)
  const camera = shallowRef<THREE.PerspectiveCamera | null>(null)
  const renderer = shallowRef<THREE.WebGLRenderer | null>(null)
  const controls = shallowRef<OrbitControls | null>(null)
  let animFrameId = 0

  // On-demand rendering
  let needsRender = false
  let isAnimating = false

  // Graph objects
  let instancedMesh: THREE.InstancedMesh | null = null
  let edgeLineSegments: THREE.LineSegments | null = null
  let labelGroup: THREE.Group | null = null
  let starfield: THREE.Points | null = null

  // 3D positions stored SEPARATELY from shared GraphNode objects
  // to avoid conflict with 2D d3-force simulation that also writes node.x/y
  let pos3dMap = new Map<string, Pos3D>()
  let nodeIdList: string[] = []
  let nodeRadiusMap = new Map<string, number>()
  let nodeTypeMap = new Map<string, string>()

  // Shared geometry & material
  let sharedSphereGeo: THREE.SphereGeometry | null = null
  let sharedNodeMaterial: THREE.MeshStandardMaterial | null = null
  let sharedEdgeMaterial: THREE.LineBasicMaterial | null = null

  function init() {
    const container = options.container.value
    if (!container) return

    const sc = new THREE.Scene()
    sc.background = new THREE.Color(0x0a0a1a)
    scene.value = sc

    const cam = new THREE.PerspectiveCamera(60, options.width.value / options.height.value, 0.1, 2000)
    cam.position.set(0, 50, 200)
    camera.value = cam

    const rnd = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    rnd.setSize(options.width.value, options.height.value)
    rnd.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    container.appendChild(rnd.domElement)
    renderer.value = rnd

    const ctrl = new OrbitControls(cam, rnd.domElement)
    ctrl.enableDamping = true
    ctrl.dampingFactor = 0.05
    ctrl.minDistance = 20
    ctrl.maxDistance = 500
    controls.value = ctrl

    ctrl.addEventListener('change', () => { scheduleRender() })

    // Lights
    sc.add(new THREE.AmbientLight(0x404060, 0.5))
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.0)
    dirLight.position.set(10, 20, 10)
    sc.add(dirLight)
    sc.add(new THREE.HemisphereLight(0x404080, 0x202020, 0.4))

    // Shared geometry & materials
    sharedSphereGeo = new THREE.SphereGeometry(1, SPHERE_SEGMENTS, SPHERE_SEGMENTS)
    sharedNodeMaterial = new THREE.MeshStandardMaterial({
      metalness: 0.2,
      roughness: 0.8,
    })
    sharedEdgeMaterial = new THREE.LineBasicMaterial({
      color: 0x94a3b8,
      transparent: true,
      opacity: 0.3,
    })

    createStarfield(sc)

    // P2-38: pause the RAF loop when the tab is hidden so the 3D graph
    // doesn't burn CPU/GPU cycles in the background. Resumes on focus.
    document.addEventListener('visibilitychange', onVisibilityChange)

    isAnimating = true
    animate()
  }

  // P2-38: visibilitychange handler — stops/resumes the RAF loop.
  function onVisibilityChange() {
    if (document.hidden) {
      isAnimating = false
      cancelAnimationFrame(animFrameId)
    } else if (scene.value && renderer.value) {
      // Only resume if not already disposed.
      if (!isAnimating) {
        isAnimating = true
        scheduleRender()
        animate()
      }
    }
  }

  function createStarfield(scene: THREE.Scene) {
    const geometry = new THREE.BufferGeometry()
    const count = 1500
    const positions = new Float32Array(count * 3)
    for (let i = 0; i < count; i++) {
      const r = 300 + Math.random() * 200
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta)
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta)
      positions[i * 3 + 2] = r * Math.cos(phi)
    }
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
    const material = new THREE.PointsMaterial({ color: 0xffffff, size: 0.5, sizeAttenuation: true })
    starfield = new THREE.Points(geometry, material)
    scene.add(starfield)
  }

  /** 3D force-directed layout — operates on pos3dMap, NOT on shared GraphNode.x/y/z.
   *  P1-22: iteration count is capped by node count so large graphs don't
   *  blow up the O(n^2) repulsion loop on a 4c/4G server. 60 iterations is
   *  enough for visual convergence; force layouts settle quickly. */
  function layoutForce3D(nodes: GraphNode[], edges: GraphEdge[], iterations?: number) {
    const n = nodes.length
    if (n === 0) return
    // Adaptive: small graphs get the full 60, large graphs taper down to 30.
    if (iterations == null) {
      iterations = n > 120 ? 30 : n > 60 ? 40 : 60
    }

    // Initialize positions: Fibonacci sphere, stored in pos3dMap
    const radius = Math.max(80, n * 3)
    for (let i = 0; i < n; i++) {
      const node = nodes[i]
      const existing = pos3dMap.get(node.id)
      if (existing) {
        // Keep existing 3D position (e.g. from previous build)
        continue
      }
      const phi = Math.acos(1 - 2 * (i + 0.5) / n)
      const theta = Math.PI * (1 + Math.sqrt(5)) * i
      pos3dMap.set(node.id, {
        x: radius * Math.sin(phi) * Math.cos(theta),
        y: radius * Math.sin(phi) * Math.sin(theta),
        z: radius * Math.cos(phi),
      })
    }

    // Build node index map
    const nodeIndex = new Map<string, number>()
    for (let i = 0; i < n; i++) {
      nodeIndex.set(nodes[i].id, i)
    }

    const repulsionStrength = -600
    const attractionStrength = 0.015
    const idealLength = 100
    const damping = 0.85

    // Velocity arrays
    const vx = new Float64Array(n)
    const vy = new Float64Array(n)
    const vz = new Float64Array(n)

    // Helper to get position
    function getPos(id: string): Pos3D {
      return pos3dMap.get(id) ?? { x: 0, y: 0, z: 0 }
    }

    for (let iter = 0; iter < iterations; iter++) {
      const alpha = 1 - iter / iterations

      // Repulsion: all pairs
      for (let i = 0; i < n; i++) {
        const pi = getPos(nodes[i].id)
        for (let j = i + 1; j < n; j++) {
          const pj = getPos(nodes[j].id)
          const dx = pi.x - pj.x
          const dy = pi.y - pj.y
          const dz = pi.z - pj.z
          const distSq = dx * dx + dy * dy + dz * dz + 1
          const dist = Math.sqrt(distSq)
          const force = repulsionStrength * alpha / distSq
          const fx = (dx / dist) * force
          const fy = (dy / dist) * force
          const fz = (dz / dist) * force
          vx[i] += fx; vy[i] += fy; vz[i] += fz
          vx[j] -= fx; vy[j] -= fy; vz[j] -= fz
        }
      }

      // Attraction: edges
      for (const edge of edges) {
        const srcIdx = nodeIndex.get(getEdgeSourceId(edge))
        const tgtIdx = nodeIndex.get(getEdgeTargetId(edge))
        if (srcIdx == null || tgtIdx == null) continue
        const ps = getPos(nodes[srcIdx].id)
        const pt = getPos(nodes[tgtIdx].id)
        const dx = pt.x - ps.x
        const dy = pt.y - ps.y
        const dz = pt.z - ps.z
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz + 0.1)
        const force = attractionStrength * alpha * (dist - idealLength)
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        const fz = (dz / dist) * force
        vx[srcIdx] += fx; vy[srcIdx] += fy; vz[srcIdx] += fz
        vx[tgtIdx] -= fx; vy[tgtIdx] -= fy; vz[tgtIdx] -= fz
      }

      // Center gravity — FIXED: proper parentheses around (pos - center)
      let cx = 0, cy = 0, cz = 0
      for (let i = 0; i < n; i++) {
        const p = getPos(nodes[i].id)
        cx += p.x; cy += p.y; cz += p.z
      }
      cx /= n; cy /= n; cz /= n
      for (let i = 0; i < n; i++) {
        const p = getPos(nodes[i].id)
        vx[i] -= (p.x - cx) * 0.01 * alpha
        vy[i] -= (p.y - cy) * 0.01 * alpha
        vz[i] -= (p.z - cz) * 0.01 * alpha
      }

      // Apply velocities
      for (let i = 0; i < n; i++) {
        vx[i] *= damping; vy[i] *= damping; vz[i] *= damping
        const p = getPos(nodes[i].id)
        const nx = p.x + vx[i]
        const ny = p.y + vy[i]
        const nz = p.z + vz[i]
        // NaN/Infinity guard
        if (isFinite(nx) && isFinite(ny) && isFinite(nz)) {
          pos3dMap.set(nodes[i].id, { x: nx, y: ny, z: nz })
        }
      }
    }
  }

  function buildGraph(nodes: GraphNode[], edges: GraphEdge[]) {
    const sc = scene.value
    if (!sc) return

    clearGraph()

    // Build data maps
    nodeIdList = []
    nodeRadiusMap.clear()
    nodeTypeMap.clear()
    for (const node of nodes) {
      nodeIdList.push(node.id)
      const r = (8 + (node.weight || 0.5) * 25) * NODE_SCALE
      nodeRadiusMap.set(node.id, r)
      nodeTypeMap.set(node.id, node.type as string)
    }

    // Run 3D force layout (uses pos3dMap, not shared node.x/y)
    layoutForce3D(nodes, edges)

    // --- InstancedMesh for nodes ---
    const count = nodes.length
    if (count > 0 && sharedSphereGeo && sharedNodeMaterial) {
      instancedMesh = new THREE.InstancedMesh(sharedSphereGeo, sharedNodeMaterial, count)
      instancedMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage)

      const dummy = new THREE.Object3D()
      const color = new THREE.Color()

      for (let i = 0; i < count; i++) {
        const node = nodes[i]
        const r = nodeRadiusMap.get(node.id) ?? 5
        const pos = pos3dMap.get(node.id) ?? { x: 0, y: 0, z: 0 }
        dummy.position.set(pos.x, pos.y, pos.z)
        dummy.scale.set(r, r, r)
        dummy.updateMatrix()
        instancedMesh.setMatrixAt(i, dummy.matrix)

        const nodeColor = getNodeColor(node.type as string)
        color.set(nodeColor.bg)
        instancedMesh.setColorAt(i, color)
      }

      instancedMesh.instanceMatrix.needsUpdate = true
      if (instancedMesh.instanceColor) instancedMesh.instanceColor.needsUpdate = true
      instancedMesh.userData = { nodeIdList: nodeIdList.slice() }
      sc.add(instancedMesh)
    }

    // --- Batched LineSegments for edges ---
    if (edges.length > 0 && sharedEdgeMaterial) {
      const positions = new Float32Array(edges.length * 6)
      let offset = 0
      for (const edge of edges) {
        const srcPos = pos3dMap.get(getEdgeSourceId(edge))
        const tgtPos = pos3dMap.get(getEdgeTargetId(edge))
        if (!srcPos || !tgtPos) { offset += 6; continue }
        positions[offset++] = srcPos.x
        positions[offset++] = srcPos.y
        positions[offset++] = srcPos.z
        positions[offset++] = tgtPos.x
        positions[offset++] = tgtPos.y
        positions[offset++] = tgtPos.z
      }
      const geo = new THREE.BufferGeometry()
      geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
      edgeLineSegments = new THREE.LineSegments(geo, sharedEdgeMaterial)
      sc.add(edgeLineSegments)
    }

    // --- Labels as sprites ---
    labelGroup = new THREE.Group()
    for (const node of nodes) {
      const sprite = createTextSprite(node.label)
      const r = nodeRadiusMap.get(node.id) ?? 5
      const pos = pos3dMap.get(node.id) ?? { x: 0, y: 0, z: 0 }
      sprite.position.set(pos.x, pos.y + r + 3, pos.z)
      sprite.userData = { nodeId: node.id }
      labelGroup.add(sprite)
    }
    sc.add(labelGroup)

    scheduleRender()
  }

  function createTextSprite(text: string): THREE.Sprite {
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')!
    const font = 'bold 24px Inter, -apple-system, sans-serif'
    ctx.font = font

    // Measure text width and size canvas to fit
    const metrics = ctx.measureText(text)
    const textWidth = metrics.width
    const padding = 16
    const canvasWidth = Math.max(256, Math.ceil(textWidth + padding * 2))
    const canvasHeight = 64

    canvas.width = canvasWidth
    canvas.height = canvasHeight
    ctx.clearRect(0, 0, canvasWidth, canvasHeight)
    ctx.font = font
    ctx.fillStyle = '#f1f5f9'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(text, canvasWidth / 2, canvasHeight / 2)

    const texture = new THREE.CanvasTexture(canvas)
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false })
    const sprite = new THREE.Sprite(material)
    // Scale sprite proportionally to canvas aspect ratio
    const aspect = canvasWidth / canvasHeight
    sprite.scale.set(3 * aspect, 3, 1)
    return sprite
  }

  function clearGraph() {
    const sc = scene.value
    if (!sc) return

    if (instancedMesh) {
      sc.remove(instancedMesh)
      instancedMesh.dispose()
      instancedMesh = null
    }
    if (edgeLineSegments) {
      sc.remove(edgeLineSegments)
      edgeLineSegments.geometry.dispose()
      edgeLineSegments = null
    }
    if (labelGroup) {
      labelGroup.traverse((child) => {
        if (child instanceof THREE.Sprite) {
          ;(child.material as THREE.SpriteMaterial).map?.dispose()
          ;(child.material as THREE.Material).dispose()
        }
      })
      sc.remove(labelGroup)
      labelGroup = null
    }

    nodeIdList = []
    nodeRadiusMap.clear()
    nodeTypeMap.clear()
  }

  function highlightNode(nodeId: string | null) {
    if (!instancedMesh) return

    const ids = instancedMesh.userData.nodeIdList as string[]
    if (!ids) return

    const dummy = new THREE.Object3D()
    const color = new THREE.Color()

    for (let i = 0; i < ids.length; i++) {
      const id = ids[i]
      const r = nodeRadiusMap.get(id) ?? 5
      const pos = pos3dMap.get(id) ?? { x: 0, y: 0, z: 0 }
      dummy.position.set(pos.x, pos.y, pos.z)

      const nodeType = nodeTypeMap.get(id) ?? 'other'
      const baseColor = getNodeColor(nodeType).bg

      if (!nodeId) {
        dummy.scale.set(r, r, r)
        instancedMesh.setColorAt(i, color.set(baseColor))
      } else if (id === nodeId) {
        dummy.scale.set(r * 1.3, r * 1.3, r * 1.3)
        instancedMesh.setColorAt(i, color.set(baseColor).multiplyScalar(1.5))
      } else {
        dummy.scale.set(r * 0.8, r * 0.8, r * 0.8)
        instancedMesh.setColorAt(i, color.set(baseColor).multiplyScalar(0.4))
      }
      dummy.updateMatrix()
      instancedMesh.setMatrixAt(i, dummy.matrix)
    }

    instancedMesh.instanceMatrix.needsUpdate = true
    if (instancedMesh.instanceColor) instancedMesh.instanceColor.needsUpdate = true

    // Dim/brighten labels
    if (labelGroup) {
      labelGroup.traverse((child) => {
        if (child instanceof THREE.Sprite) {
          const id = child.userData.nodeId
          if (!nodeId) {
            child.material.opacity = 1
          } else if (id === nodeId) {
            child.material.opacity = 1
          } else {
            child.material.opacity = 0.2
          }
        }
      })
    }

    scheduleRender()
  }

  function focusNode(nodeId: string) {
    const pos = pos3dMap.get(nodeId)
    const cam = camera.value
    const ctrl = controls.value
    if (!pos || !cam || !ctrl) return

    const target = new THREE.Vector3(pos.x, pos.y, pos.z)
    const offset = new THREE.Vector3(0, 10, 30)
    const newPos = target.clone().add(offset)

    const startPos = cam.position.clone()
    const startTarget = ctrl.target.clone()
    const duration = 800
    const startTime = Date.now()

    function animateFocus() {
      const elapsed = Date.now() - startTime
      const t = Math.min(elapsed / duration, 1)
      const ease = 1 - Math.pow(1 - t, 3)

      // cam/ctrl null-checked above; assert non-null in this closure
      cam!.position.lerpVectors(startPos, newPos, ease)
      ctrl!.target.lerpVectors(startTarget, target, ease)
      ctrl!.update()
      scheduleRender()

      if (t < 1) requestAnimationFrame(animateFocus)
    }
    animateFocus()
  }

  function setAutoRotate(value: boolean) {
    if (controls.value) {
      controls.value.autoRotate = value
      controls.value.autoRotateSpeed = 1.0
    }
    if (value) scheduleRender()
  }

  function resetView() {
    const cam = camera.value
    const ctrl = controls.value
    if (!cam || !ctrl) return
    cam.position.set(0, 50, 200)
    ctrl.target.set(0, 0, 0)
    ctrl.update()
    scheduleRender()
  }

  function scheduleRender() {
    needsRender = true
  }

  function animate() {
    if (!isAnimating) return
    animFrameId = requestAnimationFrame(animate)

    const ctrl = controls.value
    if (ctrl) {
      if (ctrl.update()) needsRender = true
    }

    if (needsRender && renderer.value && scene.value && camera.value) {
      needsRender = false
      renderer.value.render(scene.value, camera.value)
    }
  }

  function resize() {
    const cam = camera.value
    const rnd = renderer.value
    if (!cam || !rnd) return
    cam.aspect = options.width.value / options.height.value
    cam.updateProjectionMatrix()
    rnd.setSize(options.width.value, options.height.value)
    scheduleRender()
  }

  function dispose() {
    isAnimating = false
    cancelAnimationFrame(animFrameId)
    // P2-38: remove the visibilitychange listener so it doesn't fire after
    // dispose and try to resume a torn-down RAF loop.
    document.removeEventListener('visibilitychange', onVisibilityChange)
    clearGraph()
    pos3dMap.clear()
    // P2-39: dispose the starfield geometry + material — previously leaked.
    if (starfield) {
      const sc = scene.value
      if (sc) sc.remove(starfield)
      starfield.geometry.dispose()
      ;(starfield.material as THREE.Material).dispose()
      starfield = null
    }
    if (sharedSphereGeo) { sharedSphereGeo.dispose(); sharedSphereGeo = null }
    if (sharedNodeMaterial) { sharedNodeMaterial.dispose(); sharedNodeMaterial = null }
    if (sharedEdgeMaterial) { sharedEdgeMaterial.dispose(); sharedEdgeMaterial = null }
    renderer.value?.dispose()
    controls.value?.dispose()
    const container = options.container.value
    if (container && renderer.value) {
      container.removeChild(renderer.value.domElement)
    }
  }

  // Raycaster
  const raycaster = new THREE.Raycaster()
  const mouse = new THREE.Vector2()
  let lastHoverTime = 0
  const HOVER_THROTTLE_MS = 50

  function hitTest(clientX: number, clientY: number, domElement: HTMLElement): string | null {
    const rect = domElement.getBoundingClientRect()
    mouse.x = ((clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((clientY - rect.top) / rect.height) * 2 + 1
    raycaster.setFromCamera(mouse, camera.value!)

    if (instancedMesh) {
      const intersects = raycaster.intersectObject(instancedMesh)
      if (intersects.length > 0 && intersects[0].instanceId != null) {
        const ids = instancedMesh.userData.nodeIdList as string[]
        return ids[intersects[0].instanceId] || null
      }
    }
    return null
  }

  function throttledHitTest(clientX: number, clientY: number, domElement: HTMLElement): string | null | undefined {
    const now = Date.now()
    if (now - lastHoverTime < HOVER_THROTTLE_MS) return undefined
    lastHoverTime = now
    return hitTest(clientX, clientY, domElement)
  }

  return {
    init,
    buildGraph,
    clearGraph,
    highlightNode,
    focusNode,
    setAutoRotate,
    resetView,
    resize,
    dispose,
    hitTest,
    throttledHitTest,
    scene,
    camera,
    renderer,
    controls,
    nodeMeshes: ref(new Map()),
  }
}
