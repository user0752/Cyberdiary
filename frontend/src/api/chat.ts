import client from './client'
import { streamSSE } from '@/composables/useSSEStream'

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
  signal?: AbortSignal,
): AsyncGenerator<{ content?: string; error?: string; conv_id?: string }, void, unknown> {
  try {
    for await (const chunk of streamSSE<{
      content?: string
      error?: string
      conv_id?: string
    }>('/api/v1/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        model_id: modelId,
        conv_id: convId,
      }),
      signal,
    })) {
      yield chunk
    }
  } catch (err: unknown) {
    // Don't report errors from intentional abort
    if (err instanceof DOMException && err.name === 'AbortError') return
    const detail = err instanceof Error ? err.message : String(err)
    yield { error: detail }
  }
}
