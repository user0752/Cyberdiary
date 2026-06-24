/** Knowledge graph type definitions. */

// Node type — matches Researcher entity types.
// Using const object + union type instead of enum (erasableSyntaxOnly).
export const NodeType = {
  TECHNOLOGY: "technology",
  CONCEPT: "concept",
  PERSON: "person",
  ORGANIZATION: "organization",
  TOOL: "tool",
  FRAMEWORK: "framework",
  LANGUAGE: "language",
  METHOD: "method",
  THEORY: "theory",
  OTHER: "other",
} as const
export type NodeType = (typeof NodeType)[keyof typeof NodeType]

// Edge type — matches relation predicates.
export const EdgeType = {
  BELONGS_TO: "belongs_to",
  USED_FOR: "used_for",
  DEPENDS_ON: "depends_on",
  SIMILAR_TO: "similar_to",
  RELATES_TO: "relates_to",
  DERIVED_FROM: "derived_from",
  IMPLEMENTS: "implements",
  REFERENCES: "references",
} as const
export type EdgeType = (typeof EdgeType)[keyof typeof EdgeType]

// Graph node
export interface GraphNode {
  id: string
  label: string
  type: NodeType | string
  group: string
  weight: number
  memoCount: number
  description: string
  sourceMemos: string[]
  originalEntity: any
  // Runtime fields set by d3-force / three.js
  x?: number
  y?: number
  z?: number
  vx?: number
  vy?: number
  fx?: number | null
  fy?: number | null
}

// Graph edge
export interface GraphEdge {
  id: string
  source: string | GraphNode
  target: string | GraphNode
  label: string
  type: EdgeType | string
  confidence: number
  directed: boolean
}

// Graph metadata
export interface GraphMeta {
  totalNodes: number
  totalEdges: number
  nodeTypes: Record<string, number>
  edgeTypes: Record<string, number>
  maxConnectedComponent: number
  compilationId: string
  compiledAt: string
}

// Root graph structure
export interface KnowledgeGraph {
  nodes: GraphNode[]
  edges: GraphEdge[]
  meta: GraphMeta
}

// Node detail (with related data)
export interface NodeDetail extends GraphNode {
  relatedEdges: GraphEdge[]
  relatedWikis: { slug: string; title: string }[]
}

// SSE graph update event payload
export interface GraphUpdateEvent {
  phase: "research" | "integrate" | "link" | "complete"
  newNodes: GraphNode[]
  newEdges: GraphEdge[]
  removedNodes: string[]
  removedEdges: string[]
  mergedNodes: { keep: string; removed: string[] }[]
}

// Node color config
export interface NodeColorConfig {
  bg: string
  glow: string
  label: string
}

// Node type -> color mapping
export const NODE_COLORS: Record<string, NodeColorConfig> = {
  technology:   { bg: "#6366f1", glow: "rgba(99,102,241,0.35)", label: "技术" },
  concept:      { bg: "#06b6d4", glow: "rgba(6,182,212,0.35)", label: "概念" },
  person:       { bg: "#f59e0b", glow: "rgba(245,158,11,0.35)", label: "人物" },
  organization: { bg: "#10b981", glow: "rgba(16,185,129,0.35)", label: "组织" },
  tool:         { bg: "#ef4444", glow: "rgba(239,68,68,0.35)", label: "工具" },
  framework:    { bg: "#8b5cf6", glow: "rgba(139,92,246,0.35)", label: "框架" },
  language:     { bg: "#3b82f6", glow: "rgba(59,130,246,0.35)", label: "语言" },
  method:       { bg: "#14b8a6", glow: "rgba(20,184,166,0.35)", label: "方法" },
  theory:       { bg: "#ec4899", glow: "rgba(236,72,153,0.35)", label: "理论" },
  other:        { bg: "#78716c", glow: "rgba(120,113,108,0.35)", label: "其他" },
  // Wiki page types
  entity:       { bg: "#10b981", glow: "rgba(16,185,129,0.35)", label: "实体" },
  comparison:   { bg: "#f59e0b", glow: "rgba(245,158,11,0.35)", label: "对比" },
  synthesis:    { bg: "#ec4899", glow: "rgba(236,72,153,0.35)", label: "综合" },
  source:       { bg: "#06b6d4", glow: "rgba(6,182,212,0.35)", label: "来源" },
}

// Edge type -> style mapping
export const EDGE_STYLES: Record<string, { dash: boolean; color: string; opacity: number }> = {
  belongs_to:   { dash: false, color: "#94a3b8", opacity: 0.6 },
  used_for:     { dash: false, color: "#64748b", opacity: 0.6 },
  depends_on:   { dash: true,  color: "#475569", opacity: 0.5 },
  similar_to:   { dash: true,  color: "#94a3b8", opacity: 0.35 },
  relates_to:   { dash: true,  color: "#475569", opacity: 0.45 },
  derived_from: { dash: false, color: "#64748b", opacity: 0.6 },
  implements:   { dash: false, color: "#94a3b8", opacity: 0.7 },
  references:   { dash: true,  color: "#475569", opacity: 0.4 },
}

// Helper: get node color with fallback
export function getNodeColor(type: string): NodeColorConfig {
  return NODE_COLORS[type] || NODE_COLORS.other
}

// Helper: get edge style with fallback
export function getEdgeStyle(type: string) {
  return EDGE_STYLES[type] || EDGE_STYLES.relates_to
}

// Helper: resolve source/target ID from edge (handles d3 object vs string)
export function getEdgeSourceId(edge: GraphEdge): string {
  return typeof edge.source === "object" ? (edge.source as GraphNode).id : edge.source
}

export function getEdgeTargetId(edge: GraphEdge): string {
  return typeof edge.target === "object" ? (edge.target as GraphNode).id : edge.target
}
