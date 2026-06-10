import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import client from '../api/client'

export type Theme = 'cyberpunk' | 'dark' | 'light' | 'synthwave'

export interface ModelConfig {
  id: string
  provider: 'deepseek' | 'qwen' | 'ollama' | 'mimo'
  model_name: string
  display_name: string
  api_key_enc: string
  endpoint: string
  enabled: boolean
}

export const useSettingsStore = defineStore('settings', () => {
  const models = ref<ModelConfig[]>([])
  const defaultChatModel = ref('')
  const defaultCompileModel = ref('')
  const theme = ref<Theme>('cyberpunk')

  // Load theme from localStorage on initialization
  function loadTheme() {
    const saved = localStorage.getItem('cybernote-theme')
    if (saved && ['cyberpunk', 'dark', 'light', 'synthwave'].includes(saved)) {
      theme.value = saved as Theme
    }
    applyTheme(theme.value)
  }

  // Save theme to localStorage and apply
  function setTheme(newTheme: Theme) {
    theme.value = newTheme
    localStorage.setItem('cybernote-theme', newTheme)
    applyTheme(newTheme)
  }

  // Apply theme to DOM
  function applyTheme(themeName: Theme) {
    const root = document.documentElement
    root.setAttribute('data-theme', themeName)
  }

  async function fetchModels() {
    try {
      const res = await client.get('/models')
      if (res.data.code === 0) models.value = res.data.data
    } catch (e) {
      console.error('Failed to fetch models:', e)
    }
  }

  async function fetchDefaults() {
    try {
      const res = await client.get('/models/defaults')
      if (res.data.code === 0 && res.data.data) {
        defaultChatModel.value = res.data.data.default_chat_model || ''
        defaultCompileModel.value = res.data.data.default_compile_model || ''
      }
    } catch (e) {
      console.error('Failed to fetch defaults:', e)
    }
  }

  async function saveDefaults(chatId: string, compileId: string): Promise<boolean> {
    try {
      const res = await client.put('/models/defaults', {
        default_chat_model: chatId,
        default_compile_model: compileId,
      })
      if (res.data.code === 0) {
        defaultChatModel.value = chatId
        defaultCompileModel.value = compileId
        return true
      }
      return false
    } catch (e) {
      console.error('Failed to save defaults:', e)
      return false
    }
  }

  /** Load models + defaults, auto-select first enabled model if no default set */
  async function init() {
    loadTheme()
    await Promise.all([fetchModels(), fetchDefaults()])
    // Auto-select first enabled model as fallback
    const firstEnabled = models.value.find((m) => m.enabled)
    if (firstEnabled) {
      if (!defaultChatModel.value) defaultChatModel.value = firstEnabled.id
      if (!defaultCompileModel.value) defaultCompileModel.value = firstEnabled.id
    }
  }

  return { 
    models, 
    defaultChatModel, 
    defaultCompileModel, 
    theme, 
    setTheme,
    fetchModels, 
    fetchDefaults, 
    saveDefaults, 
    init 
  }
})
