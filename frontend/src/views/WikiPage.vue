<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWikiStore } from '../stores/wiki'
import MarkdownRenderer from '../components/MarkdownRenderer.vue'
import MarkdownEditor from '../components/MarkdownEditor.vue'

const route = useRoute()
const router = useRouter()
const store = useWikiStore()

const editing = ref(false)
const editTitle = ref('')
const editContent = ref('')
const editSummary = ref('')
const editTags = ref('')
const editType = ref('')

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
  editTitle.value = store.currentPage.title
  editContent.value = store.currentPage.content
  editSummary.value = store.currentPage.summary || ''
  editTags.value = parseTags(store.currentPage.tags).join(', ')
  editType.value = store.currentPage.wiki_type
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
  editing.value = false
}

function cancelEdit() {
  editing.value = false
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

watch(() => route.params.slug, loadPage)
</script>

<template>
  <div class="wiki-page-view">
    <!-- Loading -->
    <div v-if="store.pageLoading" class="loading-indicator">
      <span>加载中...</span>
    </div>

    <!-- Not Found -->
    <div v-else-if="!store.currentPage" class="empty-state">
      <span class="empty-icon">📄</span>
      <p>Wiki 页面不存在</p>
      <button class="btn btn-ghost" @click="router.push('/wiki')">返回 Wiki 列表</button>
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

          <button class="btn btn-ghost edit-btn" @click="startEdit">✏️ 编辑</button>
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
  </div>
</template>

<style scoped>
.wiki-page-view {
  height: 100%;
  overflow-y: auto;
}

.loading-indicator {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: var(--text-muted);
}

.empty-icon {
  font-size: 3rem;
  opacity: 0.5;
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
