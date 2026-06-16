/** Three.js 3D renderer composable for knowledge graph. */

import { ref, type Ref, shallowRef } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { GraphNode, GraphEdge } from '@/types/graph'
import { NODE_COLORS, getEdgeSourceId, getEdgeTargetId, getNodeColor } from '@/types/graph'

const SPHERE_SEGMENTS = 16
const NODE_SCALE = 0.4 // 3D nodes are smaller than 2D

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
  const nodeMeshes = shallowRef<Map<string, THREE.Mesh>>(new Map())
  const edgeLines = shallowRef<Map<string, THREE.Line>>(new Map())
  const labelSprites = shallowRef<Map<string, THREE.Sprite>>(new Map())
  let animFrameId = 0
  let autoRotate = false

  function init() {
    const container = options.container.value
    if (!container) return

    // Scene
    const sc = new THREE.Scene()
    sc.background = new THREE.Color(0x0a0a1a)
    scene.value = sc

    // Camera
    const cam = new THREE.PerspectiveCamera(60, options.width.value / options.height.value, 0.1, 2000)
    cam.position.set(0, 50, 200)
    camera.value = cam

    // Renderer
    const rnd = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    rnd.setSize(options.width.value, options.height.value)
    rnd.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    container.appendChild(rnd.domElement)
    renderer.value = rnd

    // Controls
    const ctrl = new OrbitControls(cam, rnd.domElement)
    ctrl.enableDamping = true
    ctrl.dampingFactor = 0.05
    ctrl.minDistance = 20
    ctrl.maxDistance = 500
    controls.value = ctrl

    // Lights
    sc.add(new THREE.AmbientLight(0x404060, 0.5))
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.0)
    dirLight.position.set(10, 20, 10)
    sc.add(dirLight)
    sc.add(new THREE.HemisphereLight(0x404080, 0x202020, 0.4))

    // Starfield background
    createStarfield(sc)

    // Bloom not available without postprocessing — skip for simplicity
    // The emissive material gives a similar glow effect

    // Start render loop
    animate()
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
    scene.add(new THREE.Points(geometry, material))
  }

  function buildGraph(nodes: GraphNode[], edges: GraphEdge[]) {
    const sc = scene.value
    if (!sc) return

    // Clear old objects
    clearGraph()

    const meshes = new Map<string, THREE.Mesh>()
    const lines = new Map<string, THREE.Line>()
    const sprites = new Map<string, THREE.Sprite>()

    // Layout nodes on a sphere surface
    const n = nodes.length
    const radius = Math.max(50, n * 2)

    nodes.forEach((node, i) => {
      // Fibonacci sphere distribution
      const phi = Math.acos(1 - 2 * (i + 0.5) / n)
      const theta = Math.PI * (1 + Math.sqrt(5)) * i
      const x = radius * Math.sin(phi) * Math.cos(theta)
      const y = radius * Math.sin(phi) * Math.sin(theta)
      const z = radius * Math.cos(phi)

      node.x = x
      node.y = y
      node.z = z

      // Node sphere
      const r = (8 + (node.weight || 0.5) * 25) * NODE_SCALE
      const color = getNodeColor(node.type as string)
      const geometry = new THREE.SphereGeometry(r, SPHERE_SEGMENTS, SPHERE_SEGMENTS)
      const material = new THREE.MeshStandardMaterial({
        color: new THREE.Color(color.bg),
        emissive: new THREE.Color(color.bg),
        emissiveIntensity: 0.3,
        metalness: 0.2,
        roughness: 0.8,
      })
      const mesh = new THREE.Mesh(geometry, material)
      mesh.position.set(x, y, z)
      mesh.userData = { nodeId: node.id, label: node.label }
      sc.add(mesh)
      meshes.set(node.id, mesh)

      // Label sprite
      const label = createTextSprite(node.label, color.bg)
      label.position.set(x, y + r + 3, z)
      sc.add(label)
      sprites.set(node.id, label)
    })

    // Build edges
    edges.forEach((edge) => {
      const srcId = getEdgeSourceId(edge)
      const tgtId = getEdgeTargetId(edge)
      const srcNode = nodes.find((n) => n.id === srcId)
      const tgtNode = nodes.find((n) => n.id === tgtId)
      if (!srcNode || !tgtNode) return

      const points = [
        new THREE.Vector3(srcNode.x ?? 0, srcNode.y ?? 0, srcNode.z ?? 0),
        new THREE.Vector3(tgtNode.x ?? 0, tgtNode.y ?? 0, tgtNode.z ?? 0),
      ]
      const geometry = new THREE.BufferGeometry().setFromPoints(points)
      const material = new THREE.LineBasicMaterial({
        color: 0x94a3b8,
        transparent: true,
        opacity: 0.3,
      })
      const line = new THREE.Line(geometry, material)
      line.userData = { edgeId: edge.id }
      sc.add(line)
      lines.set(edge.id, line)
    })

    nodeMeshes.value = meshes
    edgeLines.value = lines
    labelSprites.value = sprites
  }

  function createTextSprite(text: string, color: string): THREE.Sprite {
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')!
    canvas.width = 256
    canvas.height = 64
    ctx.fillStyle = 'transparent'
    ctx.fillRect(0, 0, 256, 64)
    ctx.font = 'bold 24px Inter, -apple-system, sans-serif'
    ctx.fillStyle = '#f1f5f9'
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(text, 128, 32)

    const texture = new THREE.CanvasTexture(canvas)
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true })
    const sprite = new THREE.Sprite(material)
    sprite.scale.set(20, 5, 1)
    return sprite
  }

  function clearGraph() {
    const sc = scene.value
    if (!sc) return

    nodeMeshes.value.forEach((mesh) => {
      sc.remove(mesh)
      mesh.geometry.dispose()
      ;(mesh.material as THREE.Material).dispose()
    })
    edgeLines.value.forEach((line) => {
      sc.remove(line)
      line.geometry.dispose()
      ;(line.material as THREE.Material).dispose()
    })
    labelSprites.value.forEach((sprite) => {
      sc.remove(sprite)
      ;(sprite.material as THREE.SpriteMaterial).map?.dispose()
      ;(sprite.material as THREE.Material).dispose()
    })

    nodeMeshes.value.clear()
    edgeLines.value.clear()
    labelSprites.value.clear()
  }

  function highlightNode(nodeId: string | null) {
    nodeMeshes.value.forEach((mesh, id) => {
      const mat = mesh.material as THREE.MeshStandardMaterial
      if (!nodeId) {
        mat.emissiveIntensity = 0.3
        mesh.scale.set(1, 1, 1)
      } else if (id === nodeId) {
        mat.emissiveIntensity = 0.8
        mesh.scale.set(1.3, 1.3, 1.3)
      } else {
        mat.emissiveIntensity = 0.1
        mesh.scale.set(0.8, 0.8, 0.8)
      }
    })
  }

  function focusNode(nodeId: string) {
    const mesh = nodeMeshes.value.get(nodeId)
    const cam = camera.value
    const ctrl = controls.value
    if (!mesh || !cam || !ctrl) return

    const target = mesh.position.clone()
    const offset = new THREE.Vector3(0, 10, 30)
    const newPos = target.clone().add(offset)

    // Animate camera
    const startPos = cam.position.clone()
    const startTarget = ctrl.target.clone()
    const duration = 800
    const startTime = Date.now()

    function animateFocus() {
      const elapsed = Date.now() - startTime
      const t = Math.min(elapsed / duration, 1)
      const ease = 1 - Math.pow(1 - t, 3) // easeOutCubic

      cam.position.lerpVectors(startPos, newPos, ease)
      ctrl.target.lerpVectors(startTarget, target, ease)
      ctrl.update()

      if (t < 1) requestAnimationFrame(animateFocus)
    }
    animateFocus()
  }

  function setAutoRotate(value: boolean) {
    autoRotate = value
    if (controls.value) {
      controls.value.autoRotate = value
      controls.value.autoRotateSpeed = 1.0
    }
  }

  function resetView() {
    const cam = camera.value
    const ctrl = controls.value
    if (!cam || !ctrl) return
    cam.position.set(0, 50, 200)
    ctrl.target.set(0, 0, 0)
    ctrl.update()
  }

  function animate() {
    animFrameId = requestAnimationFrame(animate)
    controls.value?.update()
    if (renderer.value && scene.value && camera.value) {
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
  }

  function dispose() {
    cancelAnimationFrame(animFrameId)
    clearGraph()
    renderer.value?.dispose()
    controls.value?.dispose()
    const container = options.container.value
    if (container && renderer.value) {
      container.removeChild(renderer.value.domElement)
    }
  }

  // Raycaster for click/hover
  const raycaster = new THREE.Raycaster()
  const mouse = new THREE.Vector2()

  function hitTest(clientX: number, clientY: number, domElement: HTMLElement): string | null {
    const rect = domElement.getBoundingClientRect()
    mouse.x = ((clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((clientY - rect.top) / rect.height) * 2 + 1
    raycaster.setFromCamera(mouse, camera.value!)

    const meshes = Array.from(nodeMeshes.value.values())
    const intersects = raycaster.intersectObjects(meshes)
    if (intersects.length > 0) {
      return intersects[0].object.userData.nodeId || null
    }
    return null
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
    scene,
    camera,
    renderer,
    controls,
    nodeMeshes,
  }
}
