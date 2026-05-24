import axios from 'axios'

const api = axios.create({ baseURL: '/api/v1' })

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

export interface ApiRes<T> {
  code: number
  message: string
  data: T
}

export async function fetchMemos(params: {
  page?: number
  page_size?: number
  memo_type?: string
  tag?: string
  archived?: boolean
}): Promise<MemoListData> {
  const { data } = await api.get<ApiRes<MemoListData>>('/memos', { params })
  return data.data
}

export async function fetchMemo(id: string): Promise<Memo> {
  const { data } = await api.get<ApiRes<Memo>>(`/memos/${id}`)
  return data.data
}

export async function createMemo(body: {
  content: string
  tags?: string[]
  memo_type?: string
  pinned?: boolean
}): Promise<Memo> {
  const { data } = await api.post<ApiRes<Memo>>('/memos', body)
  return data.data
}

export async function updateMemo(id: string, body: Record<string, unknown>): Promise<Memo> {
  const { data } = await api.patch<ApiRes<Memo>>(`/memos/${id}`, body)
  return data.data
}

export async function deleteMemo(id: string): Promise<void> {
  await api.delete(`/memos/${id}`)
}

export async function searchMemos(q: string, limit = 20): Promise<Memo[]> {
  const { data } = await api.get<ApiRes<Memo[]>>('/memos/search', { params: { q, limit } })
  return data.data
}
