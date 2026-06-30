<script setup lang="ts">
import { ref, nextTick, watch, onUnmounted } from 'vue'
import { useChatStore } from '../stores/chat'
import MarkdownRenderer from './MarkdownRenderer.vue'

const store = useChatStore()
const inputText = ref('')
const messagesContainer = ref<HTMLDivElement>()
const textareaRef = ref<HTMLTextAreaElement>()
const copiedId = ref<string | null>(null)
// Whether the user is currently pinned to the bottom of the chat (auto-scroll
// eligible). Set false on manual upward scroll; true again when they scroll
// back to the bottom or click the "new messages" button.
const atBottom = ref(true)
const props = defineProps<{
  modelId: string
}>()

function isNearBottom(): boolean {
  const el = messagesContainer.value
  if (!el) return true
  // 80px threshold — user is considered "at bottom" within this band.
  return el.scrollHeight - el.scrollTop - el.clientHeight < 80
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value && atBottom.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

function handleScroll() {
  atBottom.value = isNearBottom()
}

function jumpToBottom() {
  atBottom.value = true
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || store.streaming) return
  inputText.value = ''
  // Reset textarea height after clearing the value.
  if (textareaRef.value) textareaRef.value.style.height = 'auto'
  // Sending implies user wants to follow the new response.
  atBottom.value = true
  await store.sendMessage(text, props.modelId)
  scrollToBottom()
}

function handleStop() {
  store.stopStreaming()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// P1-17: auto-grow textarea up to the CSS max-height (150px).
function autoGrow() {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 150) + 'px'
}

async function copyMessage(id: string, content: string) {
  try {
    await navigator.clipboard.writeText(content)
    copiedId.value = id
    setTimeout(() => {
      if (copiedId.value === id) copiedId.value = null
    }, 1500)
  } catch {
    /* clipboard API may be unavailable in insecure contexts */
  }
}

// P2-34: throttle scroll-to-bottom during streaming. A long LLM response
// can emit hundreds of chunks per second; without throttling each chunk
// schedules a nextTick + scroll, jankying the main thread. Coalesce to
// at most one scroll per animation frame.
let _scrollRafScheduled = false
function scheduleScrollToBottom() {
  if (_scrollRafScheduled) return
  _scrollRafScheduled = true
  requestAnimationFrame(() => {
    _scrollRafScheduled = false
    if (messagesContainer.value && atBottom.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

watch(() => store.streamContent, scheduleScrollToBottom)

// P2-33: cancel any in-flight stream when the component unmounts. Without
// this, navigating away mid-stream leaves the AbortController dangling and
// the store's streaming flag stuck true, so the next ChatView mount thinks
// a stream is already running.
onUnmounted(() => {
  if (store.streaming) {
    store.stopStreaming()
  }
})
</script>

<template>
  <div class="chat-window">
    <div ref="messagesContainer" class="chat-messages" @scroll="handleScroll">
      <div v-if="store.messages.length === 0 && !store.streaming" class="empty-state">
        <div class="empty-visual">
          <svg viewBox="0 0 80 80" fill="none">
            <circle cx="40" cy="40" r="30" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
            <circle cx="40" cy="40" r="20" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
            <circle cx="40" cy="40" r="10" stroke="currentColor" stroke-width="1.5" opacity="0.3"/>
            <circle cx="40" cy="40" r="3" fill="currentColor" opacity="0.5"/>
          </svg>
        </div>
        <p class="empty-title">AI ASSISTANT</p>
        <p class="empty-hint">Ask anything, I will answer based on your knowledge base</p>
      </div>

      <div
        v-for="msg in store.messages"
        :key="msg.id"
        class="message"
        :class="msg.role"
      >
        <div class="message-avatar" :class="msg.role">
          <svg v-if="msg.role === 'user'" viewBox="0 0 24 24" fill="currentColor">
            <circle cx="12" cy="8" r="4"/>
            <path d="M12 14c-4 0-8 2-8 4v2h16v-2c0-2-4-4-8-4z"/>
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <div class="message-content" :class="msg.role">
          <div class="message-header">
            <span class="message-role">{{ msg.role === 'user' ? 'USER' : 'AI' }}</span>
            <button
              v-if="msg.role === 'assistant' && msg.content"
              class="msg-action-btn"
              :title="copiedId === msg.id ? '已复制' : '复制'"
              :aria-label="copiedId === msg.id ? '已复制' : '复制消息'"
              @click="copyMessage(msg.id, msg.content)"
            >
              <svg v-if="copiedId !== msg.id" viewBox="0 0 16 16" fill="currentColor">
                <path d="M3 3h9v9H3V3zm-2 2v10h10v-2H2V5z"/>
              </svg>
              <svg v-else viewBox="0 0 16 16" fill="currentColor">
                <path d="M13.5 4.5L6 12l-3.5-3.5 1-1L6 10l6.5-6.5 1 1z"/>
              </svg>
            </button>
          </div>
          <MarkdownRenderer v-if="msg.role === 'assistant'" :content="msg.content" />
          <p v-else>{{ msg.content }}</p>
        </div>
      </div>

      <div v-if="store.streaming && store.streamContent" class="message assistant">
        <div class="message-avatar assistant">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <div class="message-content assistant">
          <div class="message-header">
            <span class="message-role">AI</span>
          </div>
          <MarkdownRenderer :content="store.streamContent" />
          <span class="streaming-cursor">▌</span>
        </div>
      </div>

      <div v-if="store.streaming && !store.streamContent" class="message assistant">
        <div class="message-avatar assistant">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
          </svg>
        </div>
        <div class="message-content assistant typing">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>

    <!-- P1-14: floating "new messages" button when the user has scrolled up -->
    <button
      v-if="!atBottom"
      class="scroll-to-bottom-btn"
      type="button"
      aria-label="滚动到最新消息"
      @click="jumpToBottom"
    >
      <svg viewBox="0 0 16 16" fill="currentColor">
        <path d="M8 12L3 7l1.5-1.5L8 9l3.5-3.5L13 7l-5 5z"/>
      </svg>
    </button>

    <div class="chat-input-area">
      <div class="input-wrapper">
        <textarea
          ref="textareaRef"
          v-model="inputText"
          placeholder="TYPE YOUR MESSAGE..."
          @keydown="handleKeydown"
          @input="autoGrow"
          :disabled="store.streaming"
          rows="1"
          aria-label="聊天输入框"
        ></textarea>
        <div class="input-indicator">
          <span v-if="store.streaming" class="status-indicator">TRANSMITTING</span>
        </div>
      </div>
      <!-- P1-15: send button becomes a stop button during streaming -->
      <button
        v-if="!store.streaming"
        class="btn btn-primary send-btn"
        @click="handleSend"
        :disabled="!inputText.trim()"
        aria-label="发送消息"
      >
        <svg viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 18l8-8-8-8-1.5 1.5L15 8l-6.5 6.5L10 18z"/>
        </svg>
        <span>SEND</span>
      </button>
      <button
        v-else
        class="btn btn-stop send-btn"
        @click="handleStop"
        aria-label="停止生成"
      >
        <svg viewBox="0 0 20 20" fill="currentColor">
          <rect x="5" y="5" width="10" height="10" rx="1.5"/>
        </svg>
        <span>STOP</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-window {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  position: relative;
}

.chat-window::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 50% 0%, rgba(0, 245, 255, 0.02) 0%, transparent 50%);
  pointer-events: none;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  position: relative;
}

.message {
  display: flex;
  gap: 14px;
  max-width: 85%;
  animation: messageIn 200ms ease;
}

@keyframes messageIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message.assistant {
  align-self: flex-start;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid var(--border);
}

.message-avatar svg {
  width: 18px;
  height: 18px;
}

.message-avatar.user {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

.message-avatar.assistant {
  background: var(--accent-ghost);
  border-color: var(--accent-dim);
  color: var(--accent);
}

.message-content {
  padding: 14px 18px;
  border-radius: var(--radius-md);
  font-size: 0.9rem;
  line-height: 1.7;
  position: relative;
}

.message-content.user {
  background: linear-gradient(135deg, var(--bg-tertiary), var(--bg-secondary));
  border: 1px solid var(--border);
  color: var(--text-primary);
}

.message-content.assistant {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  color: var(--text-primary);
}

.message-content.assistant::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, var(--accent-dim), transparent);
}

.message-header {
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-dim);
}

.message-role {
  font-family: var(--font-display);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.15em;
  color: var(--accent);
}

.message.user .message-role {
  color: var(--text-muted);
}

.message-content :deep(p) {
  margin: 0;
}

.streaming-cursor {
  display: inline-block;
  color: var(--accent);
  animation: blink 0.8s infinite;
  margin-left: 2px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.typing {
  display: flex;
  gap: 6px;
  align-items: center;
  padding: 16px 20px !important;
  background: var(--bg-secondary) !important;
  border: 1px solid var(--border) !important;
}

.typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  animation: typingPulse 1.4s infinite ease-in-out;
}

.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typingPulse {
  0%, 60%, 100% { transform: scale(1); opacity: 0.5; }
  30% { transform: scale(1.2); opacity: 1; }
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.empty-visual {
  width: 80px;
  height: 80px;
  margin-bottom: 24px;
  color: var(--text-ghost);
  animation: pulse 3s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.3; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.05); }
}

.empty-title {
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: 0.2em;
  margin-bottom: 8px;
}

.empty-hint {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--text-muted);
  text-align: center;
  max-width: 300px;
}

.chat-input-area {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--border-dim);
  background: var(--bg-secondary);
  position: relative;
}

.chat-input-area::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent-dim), transparent);
}

.input-wrapper {
  flex: 1;
  position: relative;
}

.input-wrapper textarea {
  width: 100%;
  resize: none;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 16px;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: var(--text-primary);
  outline: none;
  min-height: 48px;
  max-height: 150px;
  transition: all var(--transition-fast);
}

.input-wrapper textarea:focus {
  border-color: var(--accent);
  box-shadow: var(--glow-sm);
}

.input-indicator {
  position: absolute;
  right: 12px;
  bottom: 12px;
}

.status-indicator {
  font-family: var(--font-mono);
  font-size: 0.6rem;
  color: var(--accent);
  letter-spacing: 0.1em;
  animation: blink 1s infinite;
}

.send-btn {
  padding: 10px 20px;
  font-size: 0.8rem;
  gap: 8px;
  align-self: flex-end;
}

.send-btn svg {
  width: 14px;
  height: 14px;
}
</style>
