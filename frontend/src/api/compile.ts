import client from './client'

// Attach JWT to raw fetch() calls used for SSE streaming. The shared axios
// `client` already injects Authorization via an interceptor, but compile
// streams use fetch() directly (axios timeout breaks SSE), so we add the
// header manually here.
function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('cybernote-token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

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
  const { data } = await client.post('/compile/trigger', {
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
  // P2-31: delegate to the shared retryable SSE helper. The single-compile
  // stream emits CompileProgress objects; map each one to an SSEEvent and
  // let the helper handle fetch/reconnect/buffer plumbing.
  yield* _retryableSSE(
    `/api/v1/compile/jobs/${jobId}/stream`,
    options,
    (raw, emit) => {
      const progress = JSON.parse(raw) as CompileProgress
      const status = progress.status || ''
      if (status === 'done' || status === 'completed') {
        emit({ event: 'complete', data: { message: progress.message || 'Done' } })
        return true // stop the stream
      }
      if (status === 'failed') {
        emit({ event: 'error', data: { message: progress.message || 'Compile failed' } })
        return true
      }
      emit({ event: 'progress', data: progress })
      return false
    },
  )
}

export async function triggerMultiAgentCompile(
  memoIds: string[],
  config: CompileConfig,
): Promise<{ job_id: string; status: string; estimated_time: string }> {
  const { data } = await client.post('/compile/multi-agent', {
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
  // P2-31: the multi-agent stream emits already-typed SSEEvent objects, so
  // the line handler just parses + yields them verbatim.
  yield* _retryableSSE(
    `/api/v1/compile/jobs/${jobId}/multi-stream`,
    options,
    (raw, emit) => {
      const event = JSON.parse(raw) as SSEEvent
      emit(event)
      return false
    },
  )
}

/**
 * P2-31: shared retryable SSE consumer. Previously the fetch + reconnect +
 * buffer-parse loop was duplicated verbatim in streamSingleCompile and
 * streamMultiAgentCompile (~80 lines each). This helper centralizes the
 * plumbing; callers provide a `handleLine` callback that parses a single
 * `data: ...` payload and emits zero or more SSEEvents via `emit()`.
 *
 * `handleLine` returns true to signal stream completion (e.g. the backend
 * sent a "done" status), false to continue.
 */
async function* _retryableSSE(
  url: string,
  options: SSEStreamOptions,
  handleLine: (raw: string, emit: (e: SSEEvent) => void) => boolean,
): AsyncGenerator<SSEEvent, void> {
  const maxRetries = options.maxRetries ?? 3
  const baseDelay = options.retryBaseDelay ?? 1000
  let retries = 0
  let completed = false

  const reconnectEvent = (n: number): SSEEvent => ({
    event: 'progress',
    data: { status: 'reconnecting', progress: 0, message: `Reconnecting (${n}/${maxRetries})...` },
  })

  while (retries <= maxRetries && !completed) {
    if (options.signal?.aborted) return

    let response: Response
    try {
      response = await fetch(url, {
        headers: authHeaders(),
        signal: options.signal,
      })
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      retries++
      if (retries <= maxRetries) {
        yield reconnectEvent(retries)
        await new Promise((r) => setTimeout(r, baseDelay * Math.pow(2, retries - 1)))
        continue
      }
      yield { event: 'error', data: { message: 'Connection failed after retries' } }
      return
    }

    if (!response.ok) {
      yield { event: 'error', data: { message: `HTTP ${response.status}` } }
      return
    }

    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    // Collect emitted events per reader loop so we can yield them as a batch
    // from this generator. (We can't yield from inside handleLine directly
    // because it's a sync callback.)
    let pendingEvents: SSEEvent[] = []

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
          if (!line.startsWith('data: ')) continue
          const content = line.slice(6)
          if (content === '[DONE]') {
            completed = true
            // Yield any pending events before returning.
            for (const e of pendingEvents) yield e
            pendingEvents = []
            return
          }
          try {
            const stop = handleLine(content, (e) => pendingEvents.push(e))
            retries = 0 // reset on every successfully parsed event
            if (stop) {
              completed = true
              for (const e of pendingEvents) yield e
              pendingEvents = []
              return
            }
          } catch {
            // skip malformed events
          }
        }
        // Flush pending events after each chunk so the UI updates promptly.
        for (const e of pendingEvents) yield e
        pendingEvents = []
      }
    } catch {
      // Stream interrupted — fall through to retry
    } finally {
      try { reader.releaseLock() } catch { /* already released */ }
    }

    if (!completed) {
      retries++
      if (retries <= maxRetries) {
        yield reconnectEvent(retries)
        await new Promise((r) => setTimeout(r, baseDelay * Math.pow(2, retries - 1)))
      }
    }
  }

  if (!completed) {
    yield { event: 'error', data: { message: 'Max retries exceeded' } }
  }
}

export async function fetchCompileTrace(jobId: string): Promise<{
  job_id: string
  status: string
  trace: TraceEntry[]
  total_events: number
}> {
  const { data } = await client.get(`/compile/jobs/${jobId}/trace`)
  if (data.code !== 0) throw new Error(data.message || 'Trace fetch failed')
  return data.data
}

export async function fetchCompileJobs(params?: {
  compile_type?: string
}): Promise<MultiAgentJob[]> {
  const { data } = await client.get('/compile/jobs', { params })
  if (data.code !== 0) return []
  return data.data
}

export async function submitHumanReview(
  taskId: string,
  decision: 'approve' | 'revise' | 'reject',
  editedWiki?: string,
): Promise<{ review_passed: boolean; next_action: string }> {
  const { data } = await client.post(`/compile/human-review/${taskId}/submit`, {
    decision,
    edited_wiki: editedWiki,
  })
  if (data.code !== 0) throw new Error(data.message || 'Review submit failed')
  return data.data
}
