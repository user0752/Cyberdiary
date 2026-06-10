import client from './client'

export interface Conversation {
  id: string
  title: string
  model_id: string
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  conv_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
}

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await client.get('/chat/conversations')
  return res.data.data || []
}

export async function fetchMessages(convId: string): Promise<ChatMessage[]> {
  const res = await client.get(`/chat/conversations/${convId}/messages`)
  return res.data.data || []
}

export async function deleteConversation(convId: string): Promise<void> {
  await client.delete(`/chat/conversations/${convId}`)
}

export async function* chatStream(
  message: string,
  modelId: string,
  convId: string | null = null,
): AsyncGenerator<{ content?: string; error?: string; conv_id?: string }, void, unknown> {
  const response = await fetch('/api/v1/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      model_id: modelId,
      conv_id: convId,
    }),
  })

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      if (body.message) detail = body.message
    } catch {
      // response body is not JSON, use status text
      if (response.statusText) detail = `${response.status} ${response.statusText}`
    }
    yield { error: detail }
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
          const parsed = JSON.parse(content)
          yield parsed
        } catch {
          // ignore parse errors
        }
      }
    }
  }
}
