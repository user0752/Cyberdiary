/**
 * Generic SSE (Server-Sent Events) stream parser.
 *
 * Usage:
 *   const controller = new AbortController()
 *   for await (const event of streamSSE<MyType>('/api/stream', { signal: controller.signal })) {
 *     // event is typed as MyType
 *   }
 *
 * The stream terminates when it receives ``data: [DONE]``, the
 * underlying ReadableStream closes naturally, or the AbortController
 * signal fires (e.g. on component unmount).
 */

export interface SSEStreamOptions extends RequestInit {
  /** AbortSignal to cancel the stream (e.g. from AbortController) */
  signal?: AbortSignal
}

export async function* streamSSE<T>(
  url: string,
  options?: SSEStreamOptions,
): AsyncGenerator<T, void, unknown> {
  const response = await fetch(url, options)

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      if (body.message) detail = body.message
    } catch {
      if (response.statusText) detail = `${response.status} ${response.statusText}`
    }
    throw new Error(detail)
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      // Check if the stream has been aborted
      if (options?.signal?.aborted) {
        break
      }

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
            yield JSON.parse(content) as T
          } catch {
            // Skip malformed JSON lines
          }
        }
      }
    }
  } finally {
    try {
      reader.releaseLock()
    } catch {
      // Reader already released
    }
    // Cancel the fetch if we exited early (e.g. due to abort)
    try {
      if (!response.body?.locked) {
        await response.body?.cancel()
      }
    } catch {
      // Ignore cancel errors
    }
  }
}
