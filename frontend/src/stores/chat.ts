import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as chatApi from '../api/chat'
import type { Conversation, ChatMessage } from '../api/chat'

export const useChatStore = defineStore('chat', () => {
  const conversations = ref<Conversation[]>([])
  const currentConvId = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const streaming = ref(false)
  const streamContent = ref('')

  async function loadConversations() {
    conversations.value = await chatApi.fetchConversations()
  }

  async function selectConversation(convId: string) {
    currentConvId.value = convId
    messages.value = await chatApi.fetchMessages(convId)
  }

  async function newConversation() {
    currentConvId.value = null
    messages.value = []
    streamContent.value = ''
  }

  async function deleteConv(convId: string) {
    await chatApi.deleteConversation(convId)
    if (currentConvId.value === convId) {
      currentConvId.value = null
      messages.value = []
    }
    await loadConversations()
  }

  async function sendMessage(content: string, modelId: string) {
    if (!content.trim() || streaming.value) return

    // Add user message immediately
    const userMsg: ChatMessage = {
      id: 'temp-' + Date.now(),
      conv_id: currentConvId.value || '',
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }
    messages.value.push(userMsg)

    streaming.value = true
    streamContent.value = ''

    try {
      const stream = chatApi.chatStream(content, modelId, currentConvId.value)

      for await (const chunk of stream) {
        if (chunk.error) {
          streamContent.value += `\n\n**错误:** ${chunk.error}`
          break
        }
        if (chunk.conv_id && !currentConvId.value) {
          currentConvId.value = chunk.conv_id
          userMsg.conv_id = chunk.conv_id
        }
        if (chunk.content) {
          streamContent.value += chunk.content
        }
      }
    } catch (e: any) {
      streamContent.value += `\n\n**错误:** ${e.message || '连接失败'}`
    }

    // Add assistant message to list
    if (streamContent.value) {
      messages.value.push({
        id: 'temp-' + Date.now(),
        conv_id: currentConvId.value || '',
        role: 'assistant',
        content: streamContent.value,
        created_at: new Date().toISOString(),
      })
    }

    streaming.value = false
    streamContent.value = ''

    // Reload conversations to update title
    await loadConversations()
  }

  return {
    conversations, currentConvId, messages, streaming, streamContent,
    loadConversations, selectConversation, newConversation, deleteConv, sendMessage,
  }
})
