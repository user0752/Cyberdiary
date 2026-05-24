<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useChatStore } from '../stores/chat'
import { useSettingsStore } from '../stores/settings'
import ChatWindow from '../components/ChatWindow.vue'

interface ModelItem {
  id: string
  provider: string
  model_name: string
  display_name: string
  enabled: boolean
}

const store = useChatStore()
const settingsStore = useSettingsStore()
const models = ref<ModelItem[]>([])
const selectedModelId = ref('')

const providerColors: Record<string, string> = {
  deepseek: 'var(--neon-cyan)',
  qwen: 'var(--neon-yellow)',
  ollama: 'var(--neon-green)',
}

onMounted(async () => {
  await settingsStore.init()
  models.value = settingsStore.models.filter((m) => m.enabled)
  if (settingsStore.defaultChatModel && models.value.some(m => m.id === settingsStore.defaultChatModel)) {
    selectedModelId.value = settingsStore.defaultChatModel
  } else if (models.value.length > 0) {
    selectedModelId.value = models.value[0].id
  }
  await store.loadConversations()
})

function formatDate(dateStr: string) {
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 86400000) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<template>
  <div class="chat-view">
    <aside class="chat-sidebar">
      <div class="sidebar-header">
        <div class="header-title">
          <span class="title-prefix">//</span>
          <span class="title-text">SESSIONS</span>
        </div>
        <button class="btn btn-primary new-chat-btn" @click="store.newConversation()">
          <span>+</span>
          <span>NEW</span>
        </button>
      </div>

      <div class="conversation-list">
        <div
          v-for="conv in store.conversations"
          :key="conv.id"
          class="conv-item"
          :class="{ active: conv.id === store.currentConvId }"
          @click="store.selectConversation(conv.id)"
        >
          <div class="conv-indicator"></div>
          <div class="conv-content">
            <div class="conv-title">{{ conv.title }}</div>
            <div class="conv-meta">
              <span>{{ formatDate(conv.updated_at) }}</span>
            </div>
          </div>
          <button
            class="conv-delete"
            @click.stop="store.deleteConv(conv.id)"
            title="删除"
          >
            <svg viewBox="0 0 16 16" fill="currentColor">
              <path d="M4 3v1h8V3H4zm-2 3v8h10V6H2zm3 2h2v6H5V8zm4 0h2v6H9V8z"/>
            </svg>
          </button>
        </div>

        <div v-if="store.conversations.length === 0" class="no-convs">
          <div class="no-convs-icon">
            <svg viewBox="0 0 40 40" fill="none">
              <rect x="5" y="8" width="30" height="24" rx="2" stroke="currentColor" stroke-width="1.5"/>
              <path d="M10 16h20M10 22h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </div>
          <span>NO SESSIONS</span>
        </div>
      </div>
    </aside>

    <div class="chat-main">
      <div class="chat-topbar">
        <div class="model-selector">
          <span class="selector-label">MODEL:</span>
          <select v-model="selectedModelId" class="model-select">
            <option v-for="m in models" :key="m.id" :value="m.id">
              {{ m.display_name || m.model_name }}
            </option>
          </select>
          <div class="model-provider" v-if="models.find(m => m.id === selectedModelId)">
            <span class="provider-dot" :style="{ background: providerColors[models.find(m => m.id === selectedModelId)?.provider || ''] }"></span>
          </div>
        </div>
        <span v-if="models.length === 0" class="no-model-hint">
          Configure models in <a href="/settings">SETTINGS</a>
        </span>
      </div>

      <ChatWindow :key="selectedModelId" :model-id="selectedModelId" />
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  height: 100%;
  display: flex;
}

.chat-sidebar {
  width: 280px;
  min-width: 280px;
  background: var(--bg-deep);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  position: relative;
}

.chat-sidebar::before {
  content: '';
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(180deg, transparent, var(--accent-dim), transparent);
}

.sidebar-header {
  padding: 20px 16px;
  border-bottom: 1px solid var(--border-dim);
}

.header-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 14px;
}

.title-prefix {
  font-family: var(--font-mono);
  font-size: 0.9rem;
  color: var(--accent);
  opacity: 0.6;
}

.title-text {
  font-family: var(--font-display);
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.15em;
}

.new-chat-btn {
  width: 100%;
  justify-content: center;
  padding: 10px;
  font-size: 0.8rem;
  gap: 6px;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-bottom: 4px;
  position: relative;
}

.conv-item:hover {
  background: var(--bg-hover);
}

.conv-item.active {
  background: var(--accent-ghost);
}

.conv-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 2px;
  height: 60%;
  background: var(--accent);
  border-radius: 1px;
}

.conv-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--border);
  flex-shrink: 0;
  transition: all var(--transition-fast);
}

.conv-item:hover .conv-indicator,
.conv-item.active .conv-indicator {
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent-glow);
}

.conv-content {
  flex: 1;
  min-width: 0;
}

.conv-title {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
}

.conv-meta {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-muted);
}

.conv-delete {
  opacity: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.conv-delete svg {
  width: 12px;
  height: 12px;
}

.conv-item:hover .conv-delete {
  opacity: 1;
}

.conv-delete:hover {
  background: rgba(255, 71, 87, 0.1);
  color: #ff4757;
}

.no-convs {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  gap: 12px;
}

.no-convs-icon {
  width: 40px;
  height: 40px;
  color: var(--text-ghost);
}

.no-convs-icon svg {
  width: 100%;
  height: 100%;
}

.no-convs span {
  font-family: var(--font-display);
  font-size: 0.7rem;
  color: var(--text-muted);
  letter-spacing: 0.1em;
}

.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-topbar {
  display: flex;
  align-items: center;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border-dim);
  background: var(--bg-secondary);
  flex-shrink: 0;
}

.model-selector {
  display: flex;
  align-items: center;
  gap: 10px;
}

.selector-label {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-muted);
  letter-spacing: 0.1em;
}

.model-select {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  padding: 6px 12px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  min-width: 180px;
  cursor: pointer;
}

.model-provider {
  display: flex;
  align-items: center;
}

.provider-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  box-shadow: 0 0 6px currentColor;
}

.no-model-hint {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
}

.no-model-hint a {
  color: var(--accent);
}
</style>
