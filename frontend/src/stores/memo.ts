import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as memoApi from '../api/memo'
import type { Memo } from '../api/memo'

export const useMemoStore = defineStore('memo', () => {
  const memos = ref<Memo[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const searchQuery = ref('')
  const searchResults = ref<Memo[]>([])

  async function loadMemos(params?: {
    page?: number
    memo_type?: string
    tag?: string
    archived?: boolean
  }) {
    loading.value = true
    try {
      const data = await memoApi.fetchMemos({
        page: params?.page ?? page.value,
        page_size: pageSize.value,
        memo_type: params?.memo_type,
        tag: params?.tag,
        archived: params?.archived,
      })
      memos.value = data.items
      total.value = data.total
      page.value = data.page
    } finally {
      loading.value = false
    }
  }

  async function createMemo(content: string, tags: string[] = [], type = 'note') {
    const memo = await memoApi.createMemo({ content, tags, memo_type: type })
    memos.value.unshift(memo)
    total.value++
    return memo
  }

  async function updateMemoItem(id: string, updates: Record<string, unknown>) {
    const updated = await memoApi.updateMemo(id, updates)
    const idx = memos.value.findIndex((m) => m.id === id)
    if (idx >= 0) memos.value[idx] = updated
    return updated
  }

  async function deleteMemoItem(id: string) {
    await memoApi.deleteMemo(id)
    memos.value = memos.value.filter((m) => m.id !== id)
    total.value--
  }

  async function doSearch(q: string) {
    searchQuery.value = q
    if (!q.trim()) {
      searchResults.value = []
      return
    }
    searchResults.value = await memoApi.searchMemos(q)
  }

  function parseTags(tagsJson: string): string[] {
    try {
      return JSON.parse(tagsJson)
    } catch {
      return []
    }
  }

  return {
    memos, total, page, pageSize, loading, searchQuery, searchResults,
    loadMemos, createMemo, updateMemoItem, deleteMemoItem, doSearch, parseTags,
  }
})
