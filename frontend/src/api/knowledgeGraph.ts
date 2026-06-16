/** Knowledge graph API — fetch graph data, search, filter, stream updates. */

import client from './client'
import { streamSSE } from '@/composables/useSSEStream'
import type { KnowledgeGraph, NodeDetail, GraphNode } from '@/types/graph'

/** Get the full knowledge graph for a completed compilation job. */
export async function fetchKnowledgeGraph(jobId: string): Promise<KnowledgeGraph> {
  const res = await client.get(`/compile/jobs/${jobId}/knowledge-graph`)
  return res.data.data
}

/** Get the aggregated knowledge graph across ALL completed compilations. */
export async function fetchAggregateKnowledgeGraph(): Promise<KnowledgeGraph> {
  const res = await client.get('/compile/knowledge-graph')
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
  try {
    for await (const chunk of streamSSE<{
      event: 'graph_update' | 'graph_complete' | 'error'
      data: any
    }>(`/api/v1/compile/jobs/${jobId}/knowledge-graph/stream`)) {
      yield chunk
    }
  } catch (err: unknown) {
    const detail = err instanceof Error ? err.message : String(err)
    yield { event: 'error', data: { message: detail } }
  }
}
