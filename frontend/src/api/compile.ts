import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1' })

// --- Types ---

export interface CompileConfig {
  model?: string
  max_revisions?: number
  parallel_researchers?: number
  pass_threshold?: number
  fallback_model?: string
  enable_human_review?: boolean
}

export interface MultiAgentJob {
  id: string
  status: string
  compile_type: string
  memo_ids: string
  model_id: string
  result_summary: string | null
  error_msg: string | null
  final_score: number | null
  progress: number | null
  current_agent: string | null
  current_layer: string | null
  compilation_log: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface TraceEntry {
  phase: string
  event: string
  agent?: string
  layer?: string
  message?: string
  data?: Record<string, unknown>
  timestamp: string
}

export interface CompileProgress {
  status: string
  progress: number
  message: string
  current_agent?: string
  current_layer?: string
}

export interface SSEEvent {
  event: 'progress' | 'complete' | 'error' | 'needs_review' | 'trace'
  data: CompileProgress | TraceEntry | Record<string, unknown>
}

export interface SemanticLink {
  source_slug: string
  target_slug: string
  relation_type: string
  confidence: number
  reason?: string
}

// --- API ---

export async function triggerSingleCompile(
  memoIds: string[],
  modelId: string,
): Promise<{ id: string; status: string }> {
  const { data } = await api.post('/compile/trigger', {
    memo_ids: memoIds,
    model_id: modelId,
  })
  if (data.code !== 0) throw new Error(data.message || 'Compile trigger failed')
  return data.data
}

export async function* streamSingleCompile(
  jobId: string,
  options: SSEStreamOptions = {},
): AsyncGenerator<SSEEvent, void> {
  const maxRetries = options.maxRetries ?? 3
  const baseDelay = options.retryBaseDelay ?? 1000
  let retries = 0
  let completed = false

  while (retries <= maxRetries && !completed) {
    if (options.signal?.aborted) return

    let response: Response
    try {
      response = await fetch(`/api/v1/compile/jobs/${jobId}/stream`, {
        signal: options.signal,
      })
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      retries++
      if (retries <= maxRetries) {
        yield { event: 'progress', data: { status: 'reconnecting', progress: 0, message: `Reconnecting (${retries}/${maxRetries})...` } } as SSEEvent
        await new Promise(r => setTimeout(r, baseDelay * Math.pow(2, retries - 1)))
        continue
      }
      yield { event: 'error', data: { message: 'Connection failed after retries' } } as SSEEvent
      return
    }

    if (!response.ok) {
      yield { event: 'error', data: { message: `HTTP ${response.status}` } } as SSEEvent
      return
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        if (options.signal?.aborted) {
          try { reader.releaseLock() } catch { /* already released */ }
          return
        }

        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const content = line.slice(6)
            if (content === '[DONE]') {
              completed = true
              return
            }
            try {
              const progress = JSON.parse(content) as CompileProgress
              retries = 0
              const status = progress.status || ''
              if (status === 'done' || status === 'completed') {
                yield { event: 'complete', data: { message: progress.message || 'Done' } } as SSEEvent
                completed = true
                return
              } else if (status === 'failed') {
                yield { event: 'error', data: { message: progress.message || 'Compile failed' } } as SSEEvent
                completed = true
                return
              } else {
                yield { event: 'progress', data: progress } as SSEEvent
              }
            } catch {
              // skip malformed events
            }
          }
        }
      }
    } catch {
      // Stream interrupted — will retry
    } finally {
      try { reader.releaseLock() } catch { /* already released */ }
    }

    if (!completed) {
      retries++
      if (retries <= maxRetries) {
        yield { event: 'progress', data: { status: 'reconnecting', progress: 0, message: `Reconnecting (${retries}/${maxRetries})...` } } as SSEEvent
        await new Promise(r => setTimeout(r, baseDelay * Math.pow(2, retries - 1)))
      }
    }
  }

  if (!completed) {
    yield { event: 'error', data: { message: 'Max retries exceeded' } } as SSEEvent
  }
}

export async function triggerMultiAgentCompile(
  memoIds: string[],
  config: CompileConfig,
): Promise<{ job_id: string; status: string; estimated_time: string }> {
  const { data } = await api.post('/compile/multi-agent', {
    memo_ids: memoIds,
    config,
  })
  if (data.code !== 0) throw new Error(data.message || 'Compile trigger failed')
  return data.data
}

export interface SSEStreamOptions {
  /** Max reconnection attempts on connection loss (default 3) */
  maxRetries?: number
  /** Base delay in ms for exponential backoff (default 1000) */
  retryBaseDelay?: number
  /** AbortSignal to cancel the stream (e.g. from AbortController) */
  signal?: AbortSignal
}

export async function* streamMultiAgentCompile(
  jobId: string,
  options: SSEStreamOptions = {},
): AsyncGenerator<SSEEvent, void> {
  const maxRetries = options.maxRetries ?? 3
  const baseDelay = options.retryBaseDelay ?? 1000
  let retries = 0
  let completed = false

  while (retries <= maxRetries && !completed) {
    // Check if aborted before attempting connection
    if (options.signal?.aborted) return

    let response: Response
    try {
      response = await fetch(`/api/v1/compile/jobs/${jobId}/multi-stream`, {
        signal: options.signal,
      })
    } catch (err: unknown) {
      // If aborted, exit silently
      if (err instanceof DOMException && err.name === 'AbortError') return
      retries++
      if (retries <= maxRetries) {
        yield { event: 'progress', data: { status: 'reconnecting', progress: 0, message: `Reconnecting (${retries}/${maxRetries})...` } } as SSEEvent
        await new Promise(r => setTimeout(r, baseDelay * Math.pow(2, retries - 1)))
        continue
      }
      yield { event: 'error', data: { message: 'Connection failed after retries' } } as SSEEvent
      return
    }

    if (!response.ok) {
      yield { event: 'error', data: { message: `HTTP ${response.status}` } } as SSEEvent
      return
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        // Check if aborted before reading next chunk
        if (options.signal?.aborted) {
          try { reader.releaseLock() } catch { /* already released */ }
          return
        }

        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const content = line.slice(6)
            if (content === '[DONE]') {
              completed = true
              return
            }
            try {
              const event = JSON.parse(content) as SSEEvent
              // Reset retry counter on successful event
              retries = 0
              yield event
            } catch {
              // skip malformed events
            }
          }
        }
      }
    } catch {
      // Stream interrupted — will retry
    } finally {
      try { reader.releaseLock() } catch { /* already released */ }
    }

    if (!completed) {
      retries++
      if (retries <= maxRetries) {
        yield { event: 'progress', data: { status: 'reconnecting', progress: 0, message: `Reconnecting (${retries}/${maxRetries})...` } } as SSEEvent
        await new Promise(r => setTimeout(r, baseDelay * Math.pow(2, retries - 1)))
      }
    }
  }

  if (!completed) {
    yield { event: 'error', data: { message: 'Max retries exceeded' } } as SSEEvent
  }
}

export async function fetchCompileTrace(jobId: string): Promise<{
  job_id: string
  status: string
  trace: TraceEntry[]
  total_events: number
}> {
  const { data } = await api.get(`/compile/jobs/${jobId}/trace`)
  if (data.code !== 0) throw new Error(data.message || 'Trace fetch failed')
  return data.data
}

export async function fetchCompileJobs(params?: {
  compile_type?: string
}): Promise<MultiAgentJob[]> {
  const { data } = await api.get('/compile/jobs', { params })
  if (data.code !== 0) return []
  return data.data
}

export async function submitHumanReview(
  taskId: string,
  decision: 'approve' | 'revise' | 'reject',
  editedWiki?: string,
): Promise<{ review_passed: boolean; next_action: string }> {
  const { data } = await api.post(`/compile/human-review/${taskId}/submit`, {
    decision,
    edited_wiki: editedWiki,
  })
  if (data.code !== 0) throw new Error(data.message || 'Review submit failed')
  return data.data
}
