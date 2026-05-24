<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useMemoStore } from '../stores/memo'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import MarkdownEditor from '../components/MarkdownEditor.vue'
import type { Memo } from '../api/memo'

const store = useMemoStore()

const showEditor = ref(false)
const editingMemo = ref<Memo | null>(null)
const editorContent = ref('')
const editorTags = ref('')
const editorType = ref('note')
const searchInput = ref('')
const showSearch = ref(false)

const typeLabels: Record<string, string> = {
  note: 'NOTE',
  idea: 'IDEA',
  reference: 'REF',
  log: 'LOG',
}

const typeColors: Record<string, string> = {
  note: 'var(--neon-cyan)',
  idea: 'var(--neon-yellow)',
  reference: 'var(--neon-green)',
  log: 'var(--neon-magenta)',
}

const groupedMemos = computed(() => {
  const groups: { date: string; items: Memo[] }[] = []
  const list = showSearch.value ? store.searchResults : store.memos

  for (const memo of list) {
    const date = new Date(memo.created_at).toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      weekday: 'long',
    })

    let group = groups.find((g) => g.date === date)
    if (!group) {
      group = { date, items: [] }
      groups.push(group)
    }
    group.items.push(memo)
  }
  return groups
})

function formatTime(dateStr: string) {
  return new Date(dateStr).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function getTags(tagsJson: string): string[] {
  try {
    return JSON.parse(tagsJson)
  } catch {
    return []
  }
}

function openNewMemo() {
  editingMemo.value = null
  editorContent.value = ''
  editorTags.value = ''
  editorType.value = 'note'
  showEditor.value = true
}

function openEditMemo(memo: Memo) {
  editingMemo.value = memo
  editorContent.value = memo.content
  editorTags.value = getTags(memo.tags).join(', ')
  editorType.value = memo.memo_type
  showEditor.value = true
}

async function saveMemo() {
  const tags = editorTags.value
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)

  if (editingMemo.value) {
    await store.updateMemoItem(editingMemo.value.id, {
      content: editorContent.value,
      tags,
      memo_type: editorType.value,
    })
  } else {
    await store.createMemo(editorContent.value, tags, editorType.value)
  }

  showEditor.value = false
  if (!showSearch.value) await store.loadMemos()
}

async function togglePin(memo: Memo) {
  await store.updateMemoItem(memo.id, { pinned: !memo.pinned })
}

async function toggleArchive(memo: Memo) {
  await store.updateMemoItem(memo.id, { archived: !memo.archived })
  await store.loadMemos()
}

async function deleteMemoConfirm(memo: Memo) {
  if (!confirm('确定要删除这条笔记吗？')) return
  await store.deleteMemoItem(memo.id)
}

async function handleSearch() {
  if (!searchInput.value.trim()) {
    showSearch.value = false
    store.searchResults = []
    await store.loadMemos()
    return
  }
  showSearch.value = true
  await store.doSearch(searchInput.value)
}

function clearSearch() {
  searchInput.value = ''
  showSearch.value = false
  store.searchResults = []
  store.loadMemos()
}

onMounted(() => {
  store.loadMemos()
})
</script>

<template>
  <div class="memo-flow">
    <header class="flow-header">
      <div class="header-left">
        <div class="page-title-block">
          <span class="title-prefix">//</span>
          <h1 class="page-title">MEMO STREAM</h1>
        </div>
        <div class="stat-block" v-if="store.total">
          <span class="stat-value">{{ store.total }}</span>
          <span class="stat-label">RECORDS</span>
        </div>
      </div>
      <div class="header-right">
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
        <button class="btn btn-primary" @click="openNewMemo">
          <span class="btn-plus">+</span>
          <span>NEW</span>
        </button>
      </div>
    </header>

    <div class="flow-content">
      <div v-if="!store.loading && groupedMemos.length === 0" class="empty-state">
        <div class="empty-visual">
          <svg viewBox="0 0 80 80" fill="none">
            <rect x="10" y="20" width="60" height="8" rx="2" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
            <rect x="10" y="36" width="45" height="8" rx="2" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
            <rect x="10" y="52" width="55" height="8" rx="2" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
          </svg>
        </div>
        <p>{{ showSearch ? 'NO MATCHES FOUND' : 'NO MEMOS YET' }}</p>
        <p class="empty-hint">{{ showSearch ? 'Try different keywords' : 'Start recording your thoughts' }}</p>
        <button v-if="!showSearch" class="btn btn-ghost" @click="openNewMemo">CREATE FIRST MEMO</button>
      </div>

      <div v-if="store.loading" class="loading-indicator">
        <div class="loading-bar">
          <div class="loading-progress"></div>
        </div>
        <span>LOADING...</span>
      </div>

      <div v-for="group in groupedMemos" :key="group.date" class="date-group">
        <div class="date-divider">
          <span class="date-line"></span>
          <span class="date-text">{{ group.date }}</span>
          <span class="date-count">[ {{ group.items.length }} ]</span>
          <span class="date-line"></span>
        </div>

        <div class="memo-cards">
          <div
            v-for="memo in group.items"
            :key="memo.id"
            class="memo-card"
            :class="{ pinned: memo.pinned }"
          >
            <div class="card-accent" :style="{ background: typeColors[memo.memo_type] }"></div>
            <div class="card-header">
              <div class="card-meta">
                <span class="memo-type-badge" :style="{ color: typeColors[memo.memo_type] }">
                  {{ typeLabels[memo.memo_type] || memo.memo_type }}
                </span>
                <span class="memo-time">{{ formatTime(memo.created_at) }}</span>
                <span v-if="memo.pinned" class="pin-badge">
                  <svg viewBox="0 0 16 16" fill="currentColor"><path d="M9.5 1.5L8 0l-1.5 1.5L5 0 3.5 1.5 2 0v2l2 2-5 5v4h2v-3l4-4 1 1 4 4v3h2V7l-5-5 2-2V0L9.5 1.5z"/></svg>
                  PINNED
                </span>
              </div>
              <div class="card-actions">
                <button class="btn-icon" @click="togglePin(memo)" :title="memo.pinned ? '取消置顶' : '置顶'">
                  <svg viewBox="0 0 20 20" fill="currentColor"><path d="M9.5 1.5L8 0l-1.5 1.5L5 0 3.5 1.5 2 0v2l2 2-5 5v4h2v-3l4-4 1 1 4 4v3h2V7l-5-5 2-2V0L9.5 1.5z"/></svg>
                </button>
                <button class="btn-icon" @click="openEditMemo(memo)" title="编辑">
                  <svg viewBox="0 0 20 20" fill="currentColor"><path d="M12.28 2.28l3.44 3.44-9.72 9.72-3.44-3.44 9.72-9.72zm-.72-1.06l1.06 1.06-9.72 9.72-1.06-1.06 9.72-9.72z"/></svg>
                </button>
                <button class="btn-icon" @click="toggleArchive(memo)" :title="memo.archived ? '取消归档' : '归档'">
                  <svg viewBox="0 0 20 20" fill="currentColor"><path d="M4 3h12v2H4V3zm0 4h12v10H4V7zm2 2v6h8V9H6z"/></svg>
                </button>
                <button class="btn-icon btn-danger-icon" @click="deleteMemoConfirm(memo)" title="删除">
                  <svg viewBox="0 0 20 20" fill="currentColor"><path d="M6 3v2h8V3H6zm-2 4v10h12V7H4zm3 2h2v8H7V9zm4 0h2v8h-2V9z"/></svg>
                </button>
              </div>
            </div>

            <div class="card-body" @click="openEditMemo(memo)">
              <MarkdownRenderer :content="memo.content" />
            </div>

            <div class="card-tags" v-if="getTags(memo.tags).length">
              <span v-for="tag in getTags(memo.tags)" :key="tag" class="cyber-tag">{{ tag }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="store.total > store.pageSize && !showSearch" class="pagination">
        <button
          class="btn btn-ghost"
          :disabled="store.page <= 1"
          @click="store.loadMemos({ page: store.page - 1 })"
        >
          ← PREV
        </button>
        <span class="page-info">{{ store.page }} / {{ Math.ceil(store.total / store.pageSize) }}</span>
        <button
          class="btn btn-ghost"
          :disabled="store.page >= Math.ceil(store.total / store.pageSize)"
          @click="store.loadMemos({ page: store.page + 1 })"
        >
          NEXT →
        </button>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="showEditor" class="editor-overlay" @click.self="showEditor = false">
        <div class="editor-drawer">
          <div class="editor-header">
            <h2>{{ editingMemo ? '[EDIT]' : '[NEW]' }} MEMO</h2>
            <button class="btn-icon close-btn" @click="showEditor = false">
              <svg viewBox="0 0 20 20" fill="currentColor"><path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"/></svg>
            </button>
          </div>

          <div class="editor-meta">
            <select v-model="editorType" class="type-select">
              <option value="note">NOTE</option>
              <option value="idea">IDEA</option>
              <option value="reference">REF</option>
              <option value="log">LOG</option>
            </select>
            <input
              v-model="editorTags"
              type="text"
              placeholder="TAGS (comma separated)"
              class="tag-input"
            />
          </div>

          <div class="editor-body">
            <MarkdownEditor v-model="editorContent" placeholder="Write something... Markdown supported" />
          </div>

          <div class="editor-footer">
            <button class="btn btn-ghost" @click="showEditor = false">CANCEL</button>
            <button class="btn btn-primary" @click="saveMemo" :disabled="!editorContent.trim()">
              {{ editingMemo ? 'UPDATE' : 'CREATE' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.memo-flow {
  height: 100%;
  display: flex;
  flex-direction: column;
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 32px;
}

.flow-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 28px 0 20px;
  border-bottom: 1px solid var(--border-dim);
  flex-shrink: 0;
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
  width: 180px;
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

.btn-plus {
  font-weight: 700;
}

.flow-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0 40px;
}

.loading-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 60px 0;
}

.loading-bar {
  width: 200px;
  height: 2px;
  background: var(--bg-tertiary);
  border-radius: 1px;
  overflow: hidden;
}

.loading-progress {
  height: 100%;
  width: 40%;
  background: var(--accent);
  box-shadow: var(--glow-sm);
  animation: loading 1.5s ease-in-out infinite;
}

@keyframes loading {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(350%); }
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

.date-group {
  margin-bottom: 32px;
}

.date-divider {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.date-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, var(--border), transparent);
}

.date-line:last-child {
  background: linear-gradient(270deg, var(--border), transparent);
}

.date-text {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: 0.1em;
  white-space: nowrap;
}

.date-count {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-ghost);
}

.memo-cards {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.memo-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px 18px 16px 22px;
  transition: all var(--transition-smooth);
  position: relative;
  overflow: hidden;
}

.memo-card::before {
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

.memo-card:hover {
  border-color: var(--border-bright);
  box-shadow: var(--glow-sm);
  transform: translateX(4px);
}

.memo-card:hover::before {
  opacity: 1;
}

.memo-card.pinned {
  border-color: var(--accent-dim);
}

.memo-card.pinned::before {
  opacity: 1;
}

.card-accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  opacity: 0.6;
  transition: opacity var(--transition-fast);
}

.memo-card:hover .card-accent {
  opacity: 1;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.memo-type-badge {
  font-family: var(--font-display);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  padding: 2px 8px;
  background: currentColor;
  background: rgba(0, 245, 255, 0.1);
  border-radius: var(--radius-sm);
}

.memo-type-badge::before {
  content: '[';
}

.memo-type-badge::after {
  content: ']';
}

.memo-time {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-muted);
}

.pin-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--accent);
  letter-spacing: 0.05em;
}

.pin-badge svg {
  width: 10px;
  height: 10px;
}

.card-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.memo-card:hover .card-actions {
  opacity: 1;
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
  color: var(--accent);
}

.btn-danger-icon:hover {
  color: #ff4757;
  background: rgba(255, 71, 87, 0.1);
}

.card-body {
  cursor: pointer;
  max-height: 250px;
  overflow: hidden;
  position: relative;
  padding-left: 4px;
}

.card-body::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 4px;
  right: 0;
  height: 50px;
  background: linear-gradient(transparent, var(--bg-card));
  pointer-events: none;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-dim);
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

.editor-overlay {
  position: fixed;
  inset: 0;
  background: rgba(3, 3, 8, 0.85);
  display: flex;
  justify-content: flex-end;
  z-index: 1000;
  animation: fadeIn 150ms ease;
  backdrop-filter: blur(4px);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.editor-drawer {
  width: 700px;
  max-width: 100vw;
  height: 100vh;
  background: var(--bg-secondary);
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  animation: slideIn 200ms ease;
  position: relative;
}

.editor-drawer::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(180deg, var(--accent), transparent);
}

@keyframes slideIn {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-dim);
}

.editor-header h2 {
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: 0.1em;
}

.close-btn {
  width: 32px;
  height: 32px;
}

.close-btn svg {
  width: 16px;
  height: 16px;
}

.editor-meta {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-dim);
  background: var(--bg-primary);
}

.type-select {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  padding: 8px 12px;
  font-family: var(--font-display);
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  min-width: 100px;
}

.tag-input {
  flex: 1;
  font-size: 0.8rem;
  font-family: var(--font-mono);
}

.editor-body {
  flex: 1;
  padding: 16px 24px;
  overflow: hidden;
}

.editor-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--border-dim);
  background: var(--bg-primary);
}
</style>
