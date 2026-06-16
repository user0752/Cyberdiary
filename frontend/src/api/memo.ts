import client from './client'

export interface Memo {
  id: string
  content: string
  tags: string
  memo_type: string
  source_url: string | null
  compiled: boolean
  archived: boolean
  pinned: boolean
  created_at: string
  updated_at: string
}

export interface MemoListData {
  items: Memo[]
  total: number
  page: number
  page_size: number
}

export async function fetchMemos(params: {
  page?: number
  page_size?: number
  memo_type?: string
  tag?: string
  archived?: boolean
}): Promise<MemoListData> {
  const { data } = await client.get('/memos', { params })
  return data.data
}

export async function fetchMemo(id: string): Promise<Memo> {
  const { data } = await client.get(`/memos/${id}`)
  return data.data
}

export async function createMemo(body: {
  content: string
  tags?: string[]
  memo_type?: string
  pinned?: boolean
}): Promise<Memo> {
  const { data } = await client.post('/memos', body)
  return data.data
}

export async function updateMemo(id: string, body: Record<string, unknown>): Promise<Memo> {
  const { data } = await client.patch(`/memos/${id}`, body)
  return data.data
}

export async function deleteMemo(id: string): Promise<void> {
  await client.delete(`/memos/${id}`)
}

export async function searchMemos(q: string, limit = 20): Promise<Memo[]> {
  const { data } = await client.get('/memos/search', { params: { q, limit } })
  return data.data
}
