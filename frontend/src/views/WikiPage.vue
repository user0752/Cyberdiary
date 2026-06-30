<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWikiStore } from '../stores/wiki'
import { useToastStore } from '../stores/toast'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import MarkdownEditor from '../components/MarkdownEditor.vue'

const route = useRoute()
const router = useRouter()
const store = useWikiStore()
const toast = useToastStore()

const editing = ref(false)
const editTitle = ref('')
const editContent = ref('')
const editSummary = ref('')
const editTags = ref('')
const editType = ref('')

const showDeleteConfirm = ref(false)
const deleting = ref(false)

// --- Draft autosave + unsaved-changes guard (P0-5) ---
const DRAFT_KEY = 'cybernote-wiki-draft'
const initialTitle = ref('')
const initialContent = ref('')
const initialSummary = ref('')
const initialTags = ref('')
const initialType = ref('')

const isDirty = computed(
  () =>
    editTitle.value !== initialTitle.value ||
    editContent.value !== initialContent.value ||
    editSummary.value !== initialSummary.value ||
    editTags.value !== initialTags.value ||
    editType.value !== initialType.value,
)

interface WikiDraft {
  slug: string
  title: string
  content: string
  summary: string
  tags: string
  type: string
}

function saveDraft() {
  const draft: WikiDraft = {
    slug: (route.params.slug as string) || '',
    title: editTitle.value,
    content: editContent.value,
    summary: editSummary.value,
    tags: editTags.value,
    type: editType.value,
  }
  localStorage.setItem(DRAFT_KEY, JSON.stringify(draft))
}

function loadDraft(): WikiDraft | null {
  const raw = localStorage.getItem(DRAFT_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as WikiDraft
  } catch {
    return null
  }
}

function clearDraft() {
  localStorage.removeItem(DRAFT_KEY)
}

function snapshotInitial() {
  initialTitle.value = editTitle.value
  initialContent.value = editContent.value
  initialSummary.value = editSummary.value
  initialTags.value = editTags.value
  initialType.value = editType.value
}

let draftTimer: ReturnType<typeof setTimeout> | null = null
watch([editTitle, editContent, editSummary, editTags, editType], () => {
  if (!editing.value) return
  if (draftTimer) clearTimeout(draftTimer)
  draftTimer = setTimeout(saveDraft, 500)
})

const typeLabels: Record<string, string> = {
  concept: '概念',
  entity: '实体',
  comparison: '对比',
  synthesis: '综合',
  source: '来源',
}

const typeColors: Record<string, string> = {
  concept: '#6366f1',
  entity: '#22c55e',
  comparison: '#f59e0b',
  synthesis: '#ec4899',
  source: '#06b6d4',
}

async function loadPage() {
  const slug = route.params.slug as string
  if (slug) {
    await store.loadPage(slug)
  }
}

function parseTags(tagsJson: string): string[] {
  return store.parseTags(tagsJson)
}

function startEdit() {
  if (!store.currentPage) return
  const slug = (route.params.slug as string) || ''
  // Offer to restore a draft saved for THIS page, if one exists.
  const draft = loadDraft()
  if (draft && draft.slug === slug && draft.content) {
    if (confirm('检测到该页面的未保存草稿，是否恢复？')) {
      editTitle.value = draft.title
      editContent.value = draft.content
      editSummary.value = draft.summary
      editTags.value = draft.tags
      editType.value = draft.type
    } else {
      clearDraft()
      editTitle.value = store.currentPage.title
      editContent.value = store.currentPage.content
      editSummary.value = store.currentPage.summary || ''
      editTags.value = parseTags(store.currentPage.tags).join(', ')
      editType.value = store.currentPage.wiki_type
    }
  } else {
    editTitle.value = store.currentPage.title
    editContent.value = store.currentPage.content
    editSummary.value = store.currentPage.summary || ''
    editTags.value = parseTags(store.currentPage.tags).join(', ')
    editType.value = store.currentPage.wiki_type
  }
  snapshotInitial()
  editing.value = true
}

async function saveEdit() {
  if (!store.currentPage) return
  const tags = editTags.value
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)

  await store.updatePage(store.currentPage.slug, {
    title: editTitle.value,
    content: editContent.value,
    summary: editSummary.value,
    tags,
    wiki_type: editType.value,
  })
  clearDraft()
  editing.value = false
}

function cancelEdit() {
  if (isDirty.value && !confirm('有未保存的修改，确定要取消吗？')) return
  clearDraft()
  editing.value = false
}

async function handleDelete() {
  if (!store.currentPage) return
  deleting.value = true
  try {
    await store.deletePage(store.currentPage.slug)
    router.push('/wiki')
  } catch (e) {
    toast.error('删除失败，请重试')
  } finally {
    deleting.value = false
    showDeleteConfirm.value = false
  }
}

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function goToPage(slug: string) {
  router.push(`/wiki/${slug}`)
}

onMounted(loadPage)

// When navigating to another wiki page, exit edit mode. Any unsaved draft
// is already persisted to localStorage and will be offered for restore when
// the user re-opens the editor on that page.
watch(() => route.params.slug, () => {
  editing.value = false
  loadPage()
})
</script>

<template>
  <div class="wiki-page-view">
    <!-- Loading -->
    <div v-if="store.pageLoading" class="loading-indicator">
      <div class="loading-spinner"></div>
      <span>LOADING PAGE...</span>
    </div>

    <!-- Not Found -->
    <div v-else-if="!store.currentPage" class="empty-state">
      <div class="empty-visual">
        <svg viewBox="0 0 80 80" fill="none">
          <rect x="15" y="15" width="50" height="50" rx="4" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
          <line x1="25" y1="30" x2="55" y2="30" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
          <line x1="25" y1="40" x2="45" y2="40" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
        </svg>
      </div>
      <p>WIKI PAGE NOT FOUND</p>
      <p class="empty-hint">该页面可能已被删除或从未存在</p>
      <button class="btn btn-primary" @click="router.push('/wiki')">返回 Wiki 列表</button>
    </div>

    <!-- Page Content -->
    <div v-else class="page-container">
      <!-- Breadcrumb -->
      <div class="breadcrumb">
        <button class="btn btn-ghost" @click="router.push('/wiki')">📚 Wiki</button>
        <span class="separator">/</span>
        <span class="current">{{ store.currentPage.title }}</span>
      </div>

      <!-- Edit Mode -->
      <div v-if="editing" class="edit-mode">
        <div class="edit-header">
          <h2>编辑 Wiki 页面</h2>
          <div class="edit-actions">
            <button class="btn btn-ghost" @click="cancelEdit">取消</button>
            <button class="btn btn-primary" @click="saveEdit">保存</button>
          </div>
        </div>

        <div class="edit-fields">
          <div class="field-row">
            <label>标题</label>
            <input v-model="editTitle" type="text" class="edit-input" />
          </div>
          <div class="field-row">
            <label>类型</label>
            <select v-model="editType" class="edit-select">
              <option value="concept">概念</option>
              <option value="entity">实体</option>
              <option value="comparison">对比</option>
              <option value="synthesis">综合</option>
              <option value="source">来源</option>
            </select>
          </div>
          <div class="field-row">
            <label>摘要</label>
            <input v-model="editSummary" type="text" class="edit-input" placeholder="一句话摘要" />
          </div>
          <div class="field-row">
            <label>标签</label>
            <input v-model="editTags" type="text" class="edit-input" placeholder="逗号分隔" />
          </div>
          <div class="field-body">
            <label>内容</label>
            <div class="editor-wrap">
              <MarkdownEditor v-model="editContent" placeholder="Wiki 页面内容 (Markdown)" />
            </div>
          </div>
        </div>
      </div>

      <!-- View Mode -->
      <div v-else class="view-mode">
        <!-- Page Header -->
        <div class="page-header">
          <div class="header-meta">
            <span
              class="type-badge"
              :style="{
                background: (typeColors[store.currentPage.wiki_type] || '#6366f1') + '20',
                color: typeColors[store.currentPage.wiki_type] || '#6366f1'
              }"
            >
              {{ typeLabels[store.currentPage.wiki_type] || store.currentPage.wiki_type }}
            </span>
            <span class="version-badge">v{{ store.currentPage.version }}</span>
            <span class="date-badge">{{ formatDate(store.currentPage.updated_at) }}</span>
          </div>

          <h1 class="page-title">{{ store.currentPage.title }}</h1>

          <p class="page-summary" v-if="store.currentPage.summary">
            {{ store.currentPage.summary }}
          </p>

          <div class="page-tags" v-if="parseTags(store.currentPage.tags).length">
            <span v-for="tag in parseTags(store.currentPage.tags)" :key="tag" class="badge">
              {{ tag }}
            </span>
          </div>

          <div class="header-actions">
            <button class="btn btn-ghost edit-btn" @click="startEdit">✏️ 编辑</button>
            <button class="btn btn-ghost delete-btn" @click="showDeleteConfirm = true">🗑️ 删除</button>
          </div>
        </div>

        <!-- Content -->
        <div class="page-content">
          <MarkdownRenderer :content="store.currentPage.content" />
        </div>

        <!-- Backlinks -->
        <div v-if="store.backlinks.length" class="backlinks-section">
          <h3 class="section-title">反向链接</h3>
          <div class="backlinks-list">
            <button
              v-for="bl in store.backlinks"
              :key="bl.id"
              class="backlink-item"
              @click="goToPage(bl.slug)"
            >
              <span
                class="type-dot"
                :style="{ background: typeColors[bl.wiki_type] || '#6366f1' }"
              ></span>
              <span class="backlink-title">{{ bl.title }}</span>
            </button>
          </div>
        </div>

        <!-- Source Memos -->
        <div class="source-section" v-if="store.currentPage.source_memo_ids && store.currentPage.source_memo_ids !== '[]'">
          <h3 class="section-title">来源笔记</h3>
          <div class="source-ids">
            <span
              v-for="memoId in JSON.parse(store.currentPage.source_memo_ids)"
              :key="memoId"
              class="source-id"
            >
              {{ memoId.slice(0, 8) }}...
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Delete Confirmation Modal -->
    <Teleport to="body">
      <div v-if="showDeleteConfirm" class="modal-overlay" @click.self="showDeleteConfirm = false" @keydown.esc.window="showDeleteConfirm = false">
        <div class="modal-box">
          <h3 class="modal-title">确认删除</h3>
          <p class="modal-text">
            确定要删除「<strong>{{ store.currentPage?.title }}</strong>」吗？<br />
            此操作不可撤销，关联的链接也会被清除。
          </p>
          <div class="modal-actions">
            <button class="btn btn-ghost" :disabled="deleting" @click="showDeleteConfirm = false">取消</button>
            <button class="btn btn-danger" :disabled="deleting" @click="handleDelete">
              {{ deleting ? '删除中...' : '确认删除' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.wiki-page-view {
  height: 100%;
  overflow-y: auto;
}

.loading-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  height: 100%;
  color: var(--text-muted);
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.loading-indicator span {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  letter-spacing: 0.2em;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  padding: 40px;
}

.empty-visual {
  width: 80px;
  height: 80px;
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
  margin-top: 4px;
}

.empty-state .btn {
  margin-top: 12px;
}

.page-container {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 32px 48px;
}

/* Breadcrumb */
.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  font-size: 0.85rem;
}

.separator {
  color: var(--text-muted);
}

.current {
  color: var(--text-secondary);
}

/* Edit Mode */
.edit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.edit-header h2 {
  font-size: 1.1rem;
  font-weight: 600;
}

.edit-actions {
  display: flex;
  gap: 10px;
}

.edit-fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-row label, .field-body label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.edit-input {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  font-size: 0.9rem;
  color: var(--text-primary);
}

.edit-select {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  font-size: 0.85rem;
  color: var(--text-primary);
}

.field-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.editor-wrap {
  height: 400px;
}

/* View Mode */
.page-header {
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border);
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.type-badge {
  padding: 3px 10px;
  border-radius: 100px;
  font-weight: 500;
  font-size: 0.75rem;
}

.version-badge {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.date-badge {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.page-title {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 10px;
  line-height: 1.3;
}

.page-summary {
  font-size: 0.95rem;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 12px;
}

.page-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}

.edit-btn {
  margin-top: 4px;
  font-size: 0.85rem;
}

.delete-btn {
  margin-top: 4px;
  font-size: 0.85rem;
  color: var(--error);
}

.delete-btn:hover {
  background: rgba(239, 68, 68, 0.13);
}

.header-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-box {
  background: var(--bg-secondary, #fff);
  border-radius: var(--radius-md, 8px);
  padding: 24px;
  max-width: 400px;
  width: 90%;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.modal-title {
  font-size: 1.05rem;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--text-primary);
}

.modal-text {
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 20px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.btn-danger {
  background: var(--error);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm, 6px);
  padding: 6px 16px;
  font-size: 0.85rem;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-danger:hover:not(:disabled) {
  background: var(--error);
  filter: brightness(1.15);
}

.btn-danger:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Content */
.page-content {
  margin-bottom: 32px;
}

/* Backlinks */
.backlinks-section, .source-section {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid var(--border);
}

.section-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.backlinks-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.backlink-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  color: var(--text-primary);
  transition: all var(--transition-fast);
  text-align: left;
}

.backlink-item:hover {
  background: var(--bg-hover);
}

.type-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.backlink-title {
  font-weight: 500;
}

/* Source IDs */
.source-ids {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.source-id {
  font-size: 0.75rem;
  font-family: var(--font-mono);
  color: var(--text-muted);
  background: var(--bg-tertiary);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}
</style>
