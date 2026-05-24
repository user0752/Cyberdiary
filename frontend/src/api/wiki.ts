import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1' })

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

interface ApiRes<T> {
  code: number
  message: string
  data: T
}

// --- Wiki API ---

export async function fetchWikiPages(params: {
  page?: number
  page_size?: number
  wiki_type?: string
  tag?: string
}): Promise<WikiListData> {
  const { data } = await api.get<ApiRes<WikiListData>>('/wiki', { params })
  return data.data
}

export async function fetchWikiPage(slug: string): Promise<WikiPage> {
  const { data } = await api.get<ApiRes<WikiPage>>(`/wiki/${slug}`)
  return data.data
}

export async function updateWikiPage(
  slug: string,
  body: Partial<Pick<WikiPage, 'title' | 'content' | 'summary' | 'wiki_type'>> & { tags?: string[] },
): Promise<WikiPage> {
  const { data } = await api.put<ApiRes<WikiPage>>(`/wiki/${slug}`, body)
  return data.data
}

export async function searchWiki(q: string, limit = 20): Promise<WikiPage[]> {
  const { data } = await api.get<ApiRes<WikiPage[]>>('/wiki/search', { params: { q, limit } })
  return data.data
}

export async function fetchWikiGraph(): Promise<WikiGraphData> {
  const { data } = await api.get<ApiRes<WikiGraphData>>('/wiki/graph')
  return data.data
}

export async function fetchBacklinks(slug: string): Promise<WikiPage[]> {
  const { data } = await api.get<ApiRes<WikiPage[]>>(`/wiki/backlinks/${slug}`)
  return data.data
}

// --- Compile API ---

export async function triggerCompile(memoIds: string[] | null, modelId: string): Promise<CompileJob> {
  const { data } = await api.post<ApiRes<CompileJob>>('/compile/trigger', {
    memo_ids: memoIds,
    model_id: modelId,
  })
  return data.data
}

export async function fetchCompileJobs(): Promise<CompileJob[]> {
  const { data } = await api.get<ApiRes<CompileJob[]>>('/compile/jobs')
  return data.data
}

export async function fetchCompileJob(jobId: string): Promise<CompileJob> {
  const { data } = await api.get<ApiRes<CompileJob>>(`/compile/jobs/${jobId}`)
  return data.data
}

export async function* streamCompileProgress(jobId: string): AsyncGenerator<CompileProgress, void> {
  const response = await fetch(`/api/v1/compile/jobs/${jobId}/stream`)
  if (!response.ok) {
    yield { status: 'error', progress: 0, message: `HTTP ${response.status}` }
    return
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const content = line.slice(6)
        if (content === '[DONE]') return
        try {
          const parsed = JSON.parse(content) as CompileProgress
          yield parsed
        } catch {
          // ignore parse errors
        }
      }
    }
  }
}
