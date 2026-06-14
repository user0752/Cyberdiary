/** Knowledge graph API — fetch graph data, search, filter, stream updates. */

import client from './client'
import type { KnowledgeGraph, NodeDetail, GraphNode } from '@/types/graph'

/** Get the full knowledge graph for a completed compilation job. */
export async function fetchKnowledgeGraph(jobId: string): Promise<KnowledgeGraph> {
  const res = await client.get(`/compile/jobs/${jobId}/knowledge-graph`)
  return res.data.data
}

/** Get a single node with its related edges and wiki pages. */
export async function fetchNodeDetail(jobId: string, nodeId: string): Promise<NodeDetail> {
  const res = await client.get(`/compile/jobs/${jobId}/knowledge-graph/node/${nodeId}`)
  return res.data.data
}

/** Search graph nodes by label (fuzzy match). */
export async function searchGraphNodes(jobId: string, keyword: string): Promise<GraphNode[]> {
  const res = await client.get(`/compile/jobs/${jobId}/knowledge-graph/search`, {
    params: { q: keyword },
  })
  return res.data.data
}

/** Filter the knowledge graph by node/edge types. */
export async function filterKnowledgeGraph(
  jobId: string,
  nodeTypes?: string[],
  edgeTypes?: string[],
): Promise<KnowledgeGraph> {
  const params: Record<string, string> = {}
  if (nodeTypes?.length) params.types = nodeTypes.join(',')
  if (edgeTypes?.length) params.edge_types = edgeTypes.join(',')
  const res = await client.get(`/compile/jobs/${jobId}/knowledge-graph/filter`, { params })
  return res.data.data
}

/** SSE stream for real-time graph updates during compilation. */
export async function* streamGraphUpdates(jobId: string): AsyncGenerator<{
  event: 'graph_update' | 'graph_complete' | 'error'
  data: any
}> {
  const response = await fetch(`/api/v1/compile/jobs/${jobId}/knowledge-graph/stream`)
  if (!response.ok) {
    yield { event: 'error', data: { message: `HTTP ${response.status}` } }
    return
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim()
          if (data === '[DONE]') return
          try {
            yield JSON.parse(data)
          } catch {
            // skip malformed JSON
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
