import client from './client'
import { streamSSE } from '@/composables/useSSEStream'

export interface WikiPage {
  id: string
  slug: string
  title: string
  wiki_type: string
  content: string
  summary: string | null
  tags: string
  file_path: string | null
  source_memo_ids: string
  version: number
  created_at: string
  updated_at: string
}

export interface WikiListData {
  items: WikiPage[]
  total: number
  page: number
  page_size: number
}

export interface GraphNode {
  id: string
  label: string
  type: string
  slug: string
}

export interface GraphEdge {
  source: string
  target: string
}

export interface WikiGraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface CompileJob {
  id: string
  status: string
  memo_ids: string
  model_id: string
  result_summary: string | null
  error_msg: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface CompileProgress {
  status: string
  progress: number
  message: string
}

// --- Wiki API ---

export async function fetchWikiPages(params: {
  page?: number
  page_size?: number
  wiki_type?: string
  tag?: string
}): Promise<WikiListData> {
  const { data } = await client.get('/wiki', { params })
  return data.data
}

export async function fetchWikiPage(slug: string): Promise<WikiPage> {
  const { data } = await client.get(`/wiki/${slug}`)
  return data.data
}

export async function updateWikiPage(
  slug: string,
  body: Partial<Pick<WikiPage, 'title' | 'content' | 'summary' | 'wiki_type'>> & { tags?: string[] },
): Promise<WikiPage> {
  const { data } = await client.put(`/wiki/${slug}`, body)
  return data.data
}

export async function deleteWikiPage(slug: string): Promise<void> {
  await client.delete(`/wiki/${slug}`)
}

export async function searchWiki(q: string, limit = 20): Promise<WikiPage[]> {
  const { data } = await client.get('/wiki/search', { params: { q, limit } })
  return data.data
}

export async function fetchWikiGraph(): Promise<WikiGraphData> {
  const { data } = await client.get('/wiki/graph')
  return data.data
}

export async function fetchBacklinks(slug: string): Promise<WikiPage[]> {
  const { data } = await client.get(`/wiki/backlinks/${slug}`)
  return data.data
}

// --- Compile API ---

export async function triggerCompile(memoIds: string[] | null, modelId: string): Promise<CompileJob> {
  const { data } = await client.post('/compile/trigger', {
    memo_ids: memoIds,
    model_id: modelId,
  })
  return data.data
}

export async function fetchCompileJobs(): Promise<CompileJob[]> {
  const { data } = await client.get('/compile/jobs')
  return data.data
}

export async function fetchCompileJob(jobId: string): Promise<CompileJob> {
  const { data } = await client.get(`/compile/jobs/${jobId}`)
  return data.data
}

export async function* streamCompileProgress(jobId: string): AsyncGenerator<CompileProgress, void> {
  try {
    for await (const chunk of streamSSE<CompileProgress>(
      `/api/v1/compile/jobs/${jobId}/stream`,
    )) {
      yield chunk
    }
  } catch (err: unknown) {
    const detail = err instanceof Error ? err.message : String(err)
    yield { status: 'error', progress: 0, message: detail }
  }
}
