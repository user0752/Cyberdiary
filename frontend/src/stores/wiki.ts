import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as wikiApi from '../api/wiki'
import type { WikiPage, WikiGraphData, CompileJob, CompileProgress } from '../api/wiki'

export const useWikiStore = defineStore('wiki', () => {
  // Wiki pages
  const pages = ref<WikiPage[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const currentType = ref<string | undefined>(undefined)

  // Current page
  const currentPage = ref<WikiPage | null>(null)
  const pageLoading = ref(false)

  // Search
  const searchQuery = ref('')
  const searchResults = ref<WikiPage[]>([])

  // Graph
  const graphData = ref<WikiGraphData | null>(null)

  // Backlinks
  const backlinks = ref<WikiPage[]>([])

  // Compile
  const compileJobs = ref<CompileJob[]>([])
  const compiling = ref(false)
  const compileProgress = ref<CompileProgress | null>(null)

  async function loadPages(params?: {
    page?: number
    wiki_type?: string
    tag?: string
  }) {
    loading.value = true
    try {
      const data = await wikiApi.fetchWikiPages({
        page: params?.page ?? page.value,
        page_size: pageSize.value,
        wiki_type: params?.wiki_type ?? currentType.value,
        tag: params?.tag,
      })
      pages.value = data.items
      total.value = data.total
      page.value = data.page
      if (params?.wiki_type !== undefined) {
        currentType.value = params.wiki_type || undefined
      }
    } finally {
      loading.value = false
    }
  }

  async function loadPage(slug: string) {
    pageLoading.value = true
    try {
      currentPage.value = await wikiApi.fetchWikiPage(slug)
      // Load backlinks in parallel
      backlinks.value = await wikiApi.fetchBacklinks(slug)
    } catch {
      currentPage.value = null
      backlinks.value = []
    } finally {
      pageLoading.value = false
    }
  }

  async function updatePage(slug: string, updates: Record<string, unknown>) {
    const updated = await wikiApi.updateWikiPage(slug, updates as any)
    currentPage.value = updated
    return updated
  }

  async function deletePage(slug: string) {
    await wikiApi.deleteWikiPage(slug)
    // Remove from list if present
    pages.value = pages.value.filter((p) => p.slug !== slug)
    // Clear current page if it was the deleted one
    if (currentPage.value?.slug === slug) {
      currentPage.value = null
      backlinks.value = []
    }
  }

  async function doSearch(q: string) {
    searchQuery.value = q
    if (!q.trim()) {
      searchResults.value = []
      return
    }
    searchResults.value = await wikiApi.searchWiki(q)
  }

  async function loadGraph() {
    graphData.value = await wikiApi.fetchWikiGraph()
  }

  async function loadCompileJobs() {
    compileJobs.value = await wikiApi.fetchCompileJobs()
  }

  async function triggerCompile(memoIds: string[] | null, modelId: string) {
    compiling.value = true
    compileProgress.value = { status: 'pending', progress: 0, message: 'Starting...' }

    try {
      const job = await wikiApi.triggerCompile(memoIds, modelId)

      // Stream progress
      const stream = wikiApi.streamCompileProgress(job.id)
      for await (const progress of stream) {
        compileProgress.value = progress
        if (progress.status === 'done' || progress.status === 'failed') {
          break
        }
      }

      // Refresh jobs list
      await loadCompileJobs()
      return job
    } catch (e: any) {
      compileProgress.value = { status: 'failed', progress: 0, message: e.message || 'Failed' }
      throw e
    } finally {
      compiling.value = false
    }
  }

  function parseTags(tagsJson: string): string[] {
    try {
      return JSON.parse(tagsJson)
    } catch {
      return []
    }
  }

  return {
    pages, total, page, pageSize, loading, currentType,
    currentPage, pageLoading,
    searchQuery, searchResults,
    graphData,
    backlinks,
    compileJobs, compiling, compileProgress,
    loadPages, loadPage, updatePage, deletePage, doSearch, loadGraph,
    loadCompileJobs, triggerCompile, parseTags,
  }
})
