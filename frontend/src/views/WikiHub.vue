<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useWikiStore } from '../stores/wiki'
import { useSettingsStore } from '../stores/settings'
import ForceGraph from '../components/ForceGraph.vue'

const router = useRouter()
const store = useWikiStore()
const settingsStore = useSettingsStore()

const viewMode = ref<'list' | 'graph'>('list')
const activeType = ref<string>('')
const searchInput = ref('')
const showSearch = ref(false)
const showCompilePanel = ref(false)

const wikiTypes = [
  { value: '', label: 'ALL', icon: '◈' },
  { value: 'concept', label: 'CONCEPT', icon: '◆' },
  { value: 'entity', label: 'ENTITY', icon: '◉' },
  { value: 'comparison', label: 'COMPARE', icon: '◇' },
  { value: 'synthesis', label: 'SYNTHESIS', icon: '◐' },
  { value: 'source', label: 'SOURCE', icon: '◎' },
]

const typeColors: Record<string, string> = {
  concept: 'var(--neon-cyan)',
  entity: 'var(--neon-green)',
  comparison: 'var(--neon-yellow)',
  synthesis: 'var(--neon-magenta)',
  source: '#a855f7',
}

const typeLabels: Record<string, string> = {
  concept: 'CONCEPT',
  entity: 'ENTITY',
  comparison: 'COMPARE',
  synthesis: 'SYNTHESIS',
  source: 'SOURCE',
}

const displayPages = computed(() => {
  return showSearch.value ? store.searchResults : store.pages
})

const filteredPages = computed(() => {
  if (!activeType.value) return displayPages.value
  return displayPages.value.filter((p) => p.wiki_type === activeType.value)
})

function setType(type: string) {
  activeType.value = type
  if (!showSearch.value) {
    store.loadPages({ wiki_type: type || undefined })
  }
}

async function handleSearch() {
  if (!searchInput.value.trim()) {
    showSearch.value = false
    store.searchResults = []
    await store.loadPages({ wiki_type: activeType.value || undefined })
    return
  }
  showSearch.value = true
  await store.doSearch(searchInput.value)
}

function clearSearch() {
  searchInput.value = ''
  showSearch.value = false
  store.searchResults = []
  store.loadPages({ wiki_type: activeType.value || undefined })
}

function goToPage(slug: string) {
  router.push(`/wiki/${slug}`)
}

function parseTags(tagsJson: string): string[] {
  try {
    return JSON.parse(tagsJson)
  } catch {
    return []
  }
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

async function handleCompile() {
  let modelId = settingsStore.defaultCompileModel
  const modelExists = settingsStore.models.some(m => m.id === modelId && m.enabled)
  if (!modelId || !modelExists) {
    // Fallback: pick first enabled model
    const fallback = settingsStore.models.find(m => m.enabled)
    if (fallback) {
      modelId = fallback.id
      settingsStore.defaultCompileModel = fallback.id
      settingsStore.saveDefaults(settingsStore.defaultChatModel, fallback.id)
    } else {
      alert('请先在设置中配置并启用一个编译模型')
      return
    }
  }
  await store.triggerCompile(null, modelId)
  await store.loadPages()
}

function toggleView(mode: 'list' | 'graph') {
  viewMode.value = mode
  if (mode === 'graph' && !store.graphData) {
    store.loadGraph()
  }
}

onMounted(() => {
  store.loadPages()
  store.loadCompileJobs()
  settingsStore.init()
})
</script>

<template>
  <div class="wiki-hub">
    <header class="hub-header">
      <div class="header-left">
        <div class="page-title-block">
          <h1 class="page-title">WIKI BASE</h1>
          <p class="page-subtitle">知识基座 — 编译后的结构化知识体系</p>
        </div>
        <div class="stat-block" v-if="store.total">
          <span class="stat-value">{{ store.total }}</span>
          <span class="stat-label">PAGES</span>
        </div>
      </div>
      <div class="header-right">
        <div class="view-toggle">
          <button
            class="toggle-btn"
            :class="{ active: viewMode === 'list' }"
            @click="toggleView('list')"
            title="列表视图"
          >
            <svg viewBox="0 0 20 20" fill="currentColor">
              <rect x="3" y="4" width="14" height="2" rx="1"/>
              <rect x="3" y="9" width="14" height="2" rx="1"/>
              <rect x="3" y="14" width="14" height="2" rx="1"/>
            </svg>
          </button>
          <button
            class="toggle-btn"
            :class="{ active: viewMode === 'graph' }"
            @click="toggleView('graph')"
            title="图谱视图"
          >
            <svg viewBox="0 0 20 20" fill="currentColor">
              <circle cx="5" cy="5" r="2"/>
              <circle cx="15" cy="5" r="2"/>
              <circle cx="10" cy="15" r="2"/>
              <path d="M5 7v3l5 5M15 7v3l-5 5M7 5h6" stroke="currentColor" stroke-width="1.5" fill="none"/>
            </svg>
          </button>
        </div>
        <div class="search-box">
          <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/>
            <path d="m21 21-4.35-4.35"/>
          </svg>
          <input
            v-model="searchInput"
            type="text"
            placeholder="SEARCH..."
            @keyup.enter="handleSearch"
            @keyup.escape="clearSearch"
          />
          <button v-if="showSearch" class="btn-clear" @click="clearSearch">×</button>
        </div>
        <button class="btn btn-primary compile-btn" @click="showCompilePanel = !showCompilePanel">
          <svg viewBox="0 0 20 20" fill="currentColor" class="compile-icon">
            <path d="M10 2l8 4-8 4-8-4 8-4zm0 8l8 4-8 4-8-4 8-4zm0 8l8 4-8 4-8-4 8-4z"/>
          </svg>
          COMPILE
        </button>
      </div>
    </header>

    <div v-if="showCompilePanel" class="compile-panel">
      <div class="panel-header">
        <h3>
          <svg viewBox="0 0 20 20" fill="currentColor" class="panel-icon">
            <path d="M10 2L2 6l8 4 8-4-8-4zM2 14l8 4 8-4M2 10l8 4 8-4"/>
          </svg>
          LLM COMPILE ENGINE
        </h3>
        <button class="btn-icon" @click="showCompilePanel = false">
          <svg viewBox="0 0 20 20" fill="currentColor"><path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"/></svg>
        </button>
      </div>
      <p class="panel-desc">Compile uncompiled memos into structured Wiki pages using LLM.</p>

      <div class="compile-actions">
        <button
          class="btn btn-primary"
          @click="handleCompile"
          :disabled="store.compiling"
        >
          {{ store.compiling ? 'COMPILING...' : 'START COMPILE' }}
        </button>
      </div>

      <div v-if="store.compiling && store.compileProgress" class="compile-progress">
        <div class="progress-bar">
          <div
            class="progress-fill"
            :style="{ width: store.compileProgress.progress + '%' }"
          ></div>
        </div>
        <span class="progress-text">{{ store.compileProgress.message }}</span>
      </div>

      <div v-if="store.compileJobs.length" class="job-history">
        <h4>// COMPILE HISTORY</h4>
        <div v-for="job in store.compileJobs.slice(0, 5)" :key="job.id" class="job-item">
          <span class="job-status" :class="job.status">
            <span v-if="job.status === 'done'">✓</span>
            <span v-else-if="job.status === 'running'">⟳</span>
            <span v-else-if="job.status === 'failed'">✕</span>
            <span v-else>○</span>
          </span>
          <span class="job-summary">{{ job.result_summary || job.error_msg || 'Pending...' }}</span>
          <span class="job-date">{{ formatDate(job.created_at) }}</span>
        </div>
      </div>
    </div>

    <div class="hub-content">
      <div v-if="viewMode === 'graph'" class="graph-view">
        <ForceGraph
          v-if="store.graphData"
          :nodes="store.graphData.nodes"
          :edges="store.graphData.edges"
        />
        <div v-else class="empty-state">
          <div class="loading-spinner"></div>
          <p>LOADING GRAPH...</p>
        </div>
      </div>

      <div v-else class="list-view">
        <div class="type-filters">
          <button
            v-for="t in wikiTypes"
            :key="t.value"
            class="filter-chip"
            :class="{ active: activeType === t.value }"
            :style="activeType === t.value && t.value ? { borderColor: typeColors[t.value], color: typeColors[t.value] } : {}"
            @click="setType(t.value)"
          >
            <span class="chip-icon" :style="t.value ? { color: typeColors[t.value] } : {}">{{ t.icon }}</span>
            <span>{{ t.label }}</span>
          </button>
        </div>

        <div v-if="store.loading" class="loading-indicator">
          <div class="loading-spinner"></div>
          <span>LOADING...</span>
        </div>

        <div v-if="!store.loading && filteredPages.length === 0" class="empty-state">
          <div class="empty-visual">
            <svg viewBox="0 0 80 80" fill="none">
              <rect x="15" y="15" width="50" height="50" rx="4" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
              <line x1="25" y1="30" x2="55" y2="30" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
              <line x1="25" y1="40" x2="45" y2="40" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
              <line x1="25" y1="50" x2="50" y2="50" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
            </svg>
          </div>
          <p>{{ showSearch ? 'NO MATCHES FOUND' : 'NO WIKI PAGES YET' }}</p>
          <p class="empty-hint">{{ showSearch ? 'Try different keywords' : 'Compile memos to generate Wiki pages' }}</p>
        </div>

        <div class="wiki-cards">
          <div
            v-for="page in filteredPages"
            :key="page.id"
            class="wiki-card"
            @click="goToPage(page.slug)"
          >
            <div class="card-header">
              <span
                class="type-badge"
                :style="{ color: typeColors[page.wiki_type] || 'var(--accent)', borderColor: typeColors[page.wiki_type] || 'var(--accent)' }"
              >
                {{ typeLabels[page.wiki_type] || page.wiki_type }}
              </span>
              <span class="card-date">{{ formatDate(page.updated_at) }}</span>
            </div>

            <h3 class="card-title">{{ page.title }}</h3>

            <p class="card-summary" v-if="page.summary">{{ page.summary }}</p>

            <div class="card-tags" v-if="parseTags(page.tags).length">
              <span v-for="tag in parseTags(page.tags)" :key="tag" class="cyber-tag">{{ tag }}</span>
            </div>

            <div class="card-meta">
              <span class="version-tag">v{{ page.version }}</span>
            </div>

            <div class="card-hover-indicator">
              <svg viewBox="0 0 20 20" fill="currentColor">
                <path d="M6 4l8 6-8 6V4z"/>
              </svg>
            </div>
          </div>
        </div>

        <div v-if="store.total > store.pageSize && !showSearch" class="pagination">
          <button
            class="btn btn-ghost"
            :disabled="store.page <= 1"
            @click="store.loadPages({ page: store.page - 1, wiki_type: activeType || undefined })"
          >
            ← PREV
          </button>
          <span class="page-info">{{ store.page }} / {{ Math.ceil(store.total / store.pageSize) }}</span>
          <button
            class="btn btn-ghost"
            :disabled="store.page >= Math.ceil(store.total / store.pageSize)"
            @click="store.loadPages({ page: store.page + 1, wiki_type: activeType || undefined })"
          >
            NEXT →
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wiki-hub {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.hub-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 28px 32px 20px;
  border-bottom: 1px solid var(--border-dim);
  flex-shrink: 0;
  flex-wrap: wrap;
  gap: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}

.page-title-block {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.title-prefix {
  font-family: var(--font-mono);
  font-size: 1rem;
  color: var(--accent);
  opacity: 0.6;
}

.page-title {
  font-family: var(--font-display);
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.15em;
}

.page-subtitle {
  font-family: var(--font-sans);
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-top: 4px;
  letter-spacing: 0.04em;
}

.stat-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.stat-value {
  font-family: var(--font-display);
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--accent);
  line-height: 1;
}

.stat-label {
  font-size: 0.6rem;
  color: var(--text-muted);
  letter-spacing: 0.1em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.view-toggle {
  display: flex;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.toggle-btn {
  padding: 8px 12px;
  color: var(--text-muted);
  transition: all var(--transition-fast);
  display: flex;
  align-items: center;
  justify-content: center;
}

.toggle-btn svg {
  width: 16px;
  height: 16px;
}

.toggle-btn.active {
  background: var(--accent-ghost);
  color: var(--accent);
}

.toggle-btn:hover:not(.active) {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.search-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 0 12px;
  transition: all var(--transition-fast);
}

.search-box:focus-within {
  border-color: var(--accent);
  box-shadow: var(--glow-sm);
}

.search-icon {
  width: 16px;
  height: 16px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.search-box input {
  border: none;
  background: none;
  padding: 10px 0;
  width: 160px;
  font-size: 0.8rem;
  font-family: var(--font-mono);
  letter-spacing: 0.05em;
}

.search-box input:focus {
  outline: none;
  box-shadow: none;
}

.btn-clear {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-tertiary);
  border-radius: 50%;
  font-size: 0.9rem;
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.btn-clear:hover {
  background: var(--error);
  color: white;
}

.compile-btn {
  gap: 8px;
}

.compile-icon {
  width: 14px;
  height: 14px;
}

.compile-panel {
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-dim);
  padding: 20px 32px;
  flex-shrink: 0;
  animation: slideDown 200ms ease;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.panel-header h3 {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-display);
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: 0.1em;
}

.panel-icon {
  width: 18px;
  height: 18px;
}

.btn-icon {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  transition: all var(--transition-fast);
}

.btn-icon svg {
  width: 14px;
  height: 14px;
}

.btn-icon:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.panel-desc {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 14px;
  letter-spacing: 0.02em;
}

.compile-actions {
  margin-bottom: 14px;
}

.compile-progress {
  margin-bottom: 14px;
}

.progress-bar {
  height: 3px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--neon-magenta));
  border-radius: 2px;
  transition: width 0.3s ease;
  box-shadow: 0 0 10px var(--accent-glow);
}

.progress-text {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.job-history h4 {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  font-weight: 500;
  margin-bottom: 10px;
  color: var(--text-muted);
  letter-spacing: 0.1em;
}

.job-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  font-size: 0.8rem;
  border-bottom: 1px solid var(--border-dim);
}

.job-status {
  font-size: 0.9rem;
}

.job-status.done { color: var(--neon-green); }
.job-status.running { color: var(--neon-yellow); }
.job-status.failed { color: var(--error); }

.job-summary {
  flex: 1;
  color: var(--text-secondary);
  font-family: var(--font-mono);
  font-size: 0.75rem;
}

.job-date {
  color: var(--text-ghost);
  font-size: 0.7rem;
}

.hub-content {
  flex: 1;
  overflow-y: auto;
}

.graph-view {
  height: 100%;
  min-height: 500px;
}

.list-view {
  padding: 20px 32px 40px;
}

.type-filters {
  display: flex;
  gap: 10px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 500;
  font-family: var(--font-display);
  letter-spacing: 0.08em;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  transition: all var(--transition-fast);
}

.chip-icon {
  font-size: 0.9rem;
  transition: color var(--transition-fast);
}

.filter-chip:hover {
  border-color: var(--accent-dim);
  color: var(--text-primary);
}

.filter-chip.active {
  background: var(--accent-ghost);
  color: var(--accent);
  border-color: var(--accent);
}

.loading-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 60px 0;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-indicator span {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  letter-spacing: 0.2em;
}

.empty-state {
  padding: 80px 0;
}

.empty-visual {
  width: 80px;
  height: 80px;
  margin: 0 auto 24px;
  color: var(--text-ghost);
}

.empty-state p {
  font-family: var(--font-display);
  font-size: 0.9rem;
  letter-spacing: 0.15em;
  color: var(--text-muted);
  text-align: center;
}

.empty-hint {
  font-size: 0.75rem !important;
  color: var(--text-ghost) !important;
  margin-top: 8px;
}

.wiki-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.wiki-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 18px 20px;
  cursor: pointer;
  transition: all var(--transition-smooth);
  position: relative;
  overflow: hidden;
}

.wiki-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent-dim), transparent);
  opacity: 0;
  transition: opacity var(--transition-smooth);
}

.wiki-card:hover {
  border-color: var(--border-bright);
  transform: translateY(-2px);
  box-shadow: var(--glow-sm);
}

.wiki-card:hover::before {
  opacity: 1;
}

.wiki-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.type-badge {
  font-family: var(--font-display);
  font-size: 0.6rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  padding: 3px 10px;
  border: 1px solid;
  border-radius: var(--radius-sm);
}

.card-date {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-muted);
}

.card-title {
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  line-height: 1.4;
  letter-spacing: 0.02em;
}

.card-summary {
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.5;
  margin-bottom: 12px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.wiki-card .card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.version-tag {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-ghost);
  padding: 2px 6px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
}

.card-hover-indicator {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0;
  transition: all var(--transition-fast);
  color: var(--accent);
}

.card-hover-indicator svg {
  width: 16px;
  height: 16px;
}

.wiki-card:hover .card-hover-indicator {
  opacity: 1;
  transform: translateY(-50%) translateX(4px);
}

.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 24px;
  padding: 32px 0;
}

.page-info {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  letter-spacing: 0.1em;
}
</style>
