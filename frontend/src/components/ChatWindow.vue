<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import MarkdownRenderer from './MarkdownRenderer.vue'

const store = useChatStore()
const inputText = ref('')
const messagesContainer = ref<HTMLDivElement>()
const props = defineProps<{
  modelId: string
}>()

function scrollToBottom() {
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
  await store.sendMessage(text, props.modelId)
  scrollToBottom()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

watch(() => store.streamContent, scrollToBottom)
</script>

<template>
  <div class="chat-window">
    <div ref="messagesContainer" class="chat-messages">
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

    <div class="chat-input-area">
      <div class="input-wrapper">
        <textarea
          v-model="inputText"
          placeholder="TYPE YOUR MESSAGE..."
          @keydown="handleKeydown"
          :disabled="store.streaming"
          rows="1"
        ></textarea>
        <div class="input-indicator">
          <span v-if="store.streaming" class="status-indicator">TRANSMITTING</span>
        </div>
      </div>
      <button
        class="btn btn-primary send-btn"
        @click="handleSend"
        :disabled="!inputText.trim() || store.streaming"
      >
        <svg viewBox="0 0 20 20" fill="currentColor">
          <path d="M10 18l8-8-8-8-1.5 1.5L15 8l-6.5 6.5L10 18z"/>
        </svg>
        <span>SEND</span>
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
