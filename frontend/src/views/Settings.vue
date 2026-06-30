<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useSettingsStore } from '../stores/settings'
import { useToastStore } from '../stores/toast'
import client from '../api/client'

const settingsStore = useSettingsStore()
const toast = useToastStore()

interface ModelConfig {
  id: string
  provider: string
  model_name: string
  display_name: string
  api_key_enc: string
  endpoint: string
  enabled: boolean
}

const models = ref<ModelConfig[]>([])
const loading = ref(true)
const showForm = ref(false)
const editingModel = ref<ModelConfig | null>(null)
const testResults = ref<Record<string, string>>({})

const defaultChatModel = ref('')
const defaultCompileModel = ref('')

const form = ref({
  provider: 'deepseek',
  model_name: '',
  display_name: '',
  api_key: '',
  endpoint: '',
})

const providerOptions = [
  { value: 'deepseek', label: 'DeepSeek', defaultEndpoint: 'https://api.deepseek.com', hint: 'deepseek-chat / deepseek-reasoner' },
  { value: 'qwen', label: 'Alibaba DashScope', defaultEndpoint: 'https://dashscope.aliyuncs.com/compatible-mode/v1', hint: 'qwen-max / deepseek-v4-pro / glm-4 / kimi-latest' },
  { value: 'ollama', label: 'Ollama (Local)', defaultEndpoint: 'http://localhost:11434', hint: 'llama3 / qwen2.5 / mistral ...' },
  { value: 'mimo', label: 'Xiaomi MIMO', defaultEndpoint: 'https://api.xiaomimimo.com/v1', hint: 'mimo-v2.5-pro / mimo-v2-pro / mimo-v2.5 / mimo-v2-omni / mimo-v2-flash' },
]

// P2-47: validation for the model form. Endpoint must be a valid http(s) URL
// when provided; API key is required for non-ollama providers on create.
const endpointError = computed(() => {
  const v = form.value.endpoint.trim()
  if (!v) return ''
  // Allow http(s) and host:port (for local Ollama). Reject obvious typos.
  try {
    const u = new URL(v)
    if (u.protocol !== 'http:' && u.protocol !== 'https:') return '仅支持 http/https 协议'
    return ''
  } catch {
    return '请输入完整的 URL（例如 https://api.deepseek.com）'
  }
})

const apiKeyError = computed(() => {
  if (form.value.provider === 'ollama') return ''
  if (editingModel.value && !form.value.api_key) return '' // keep existing on edit
  if (!form.value.api_key.trim()) return 'API Key 不能为空'
  return ''
})

const formValid = computed(() => {
  if (!form.value.model_name.trim()) return false
  if (endpointError.value || apiKeyError.value) return false
  return true
})

const selectedProvider = computed(() => providerOptions.find(p => p.value === form.value.provider))
const providerColors: Record<string, string> = {
  deepseek: 'var(--neon-cyan)',
  qwen: 'var(--neon-yellow)',
  ollama: 'var(--neon-green)',
  mimo: 'var(--neon-orange)',
}

const themes = [
  {
    id: 'cyberpunk',
    name: 'Cyberpunk',
    desc: 'Neon nights, glitchy vibes',
    preview: 'linear-gradient(135deg, #030308 0%, #0f0f1a 100%)'
  },
  {
    id: 'dark',
    name: 'Dark',
    desc: 'Clean minimal dark theme',
    preview: 'linear-gradient(135deg, #05050a 0%, #1a1a20 100%)'
  },
  {
    id: 'light',
    name: 'Light',
    desc: 'Bright and clean UI',
    preview: 'linear-gradient(135deg, #fafafa 0%, #e8e8f0 100%)'
  },
  {
    id: 'synthwave',
    name: 'Synthwave',
    desc: '80s retrofuturistic style',
    preview: 'linear-gradient(135deg, #050110 0%, #1c1030 100%)'
  },
  {
    id: 'auto',
    name: 'Auto',
    desc: 'Follow system light/dark preference',
    preview: 'linear-gradient(135deg, #05050a 50%, #fafafa 50%)'
  }
]

function setTheme(themeId: string) {
  settingsStore.setTheme(themeId as any)
}

async function loadModels() {
  loading.value = true
  try {
    const { data } = await client.get('/models')
    models.value = data.data
    await settingsStore.fetchDefaults()
    defaultChatModel.value = settingsStore.defaultChatModel
    defaultCompileModel.value = settingsStore.defaultCompileModel
    const firstEnabled = models.value.find(m => m.enabled)
    if (firstEnabled) {
      // Only auto-fill if saved default is empty OR the saved model no longer exists
      if (!defaultChatModel.value || !models.value.some(m => m.id === defaultChatModel.value)) {
        defaultChatModel.value = firstEnabled.id
      }
      if (!defaultCompileModel.value || !models.value.some(m => m.id === defaultCompileModel.value)) {
        defaultCompileModel.value = firstEnabled.id
      }
    }
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

const enabledModels = computed(() => models.value.filter(m => m.enabled))

async function saveDefaults() {
  if (!(await settingsStore.saveDefaults(defaultChatModel.value, defaultCompileModel.value))) {
    // Save failed — revert to server state and re-apply auto-fill
    defaultChatModel.value = settingsStore.defaultChatModel
    defaultCompileModel.value = settingsStore.defaultCompileModel
    const firstEnabled = models.value.find(m => m.enabled)
    if (firstEnabled) {
      if (!defaultChatModel.value) defaultChatModel.value = firstEnabled.id
      if (!defaultCompileModel.value) defaultCompileModel.value = firstEnabled.id
    }
  }
}

function openAdd() {
  editingModel.value = null
  form.value = { provider: 'deepseek', model_name: '', display_name: '', api_key: '', endpoint: '' }
  showForm.value = true
}

function openEdit(model: ModelConfig) {
  editingModel.value = model
  form.value = {
    provider: model.provider,
    model_name: model.model_name,
    display_name: model.display_name,
    api_key: '',
    endpoint: model.endpoint || '',
  }
  showForm.value = true
}

async function saveModel() {
  // P2-47: re-check computed guards in case the user hit Enter before blur.
  if (!formValid.value) return
  const body: Record<string, string> = {
    provider: form.value.provider,
    model_name: form.value.model_name,
    display_name: form.value.display_name || form.value.model_name,
    api_key: form.value.api_key,
    endpoint: form.value.endpoint,
  }
  try {
    if (editingModel.value) {
      const updateBody: Record<string, unknown> = {}
      if (form.value.display_name) updateBody.display_name = form.value.display_name
      if (form.value.api_key) updateBody.api_key = form.value.api_key
      if (form.value.endpoint) updateBody.endpoint = form.value.endpoint
      await client.put(`/models/${editingModel.value.id}`, updateBody)
    } else {
      await client.post('/models', body)
    }
    showForm.value = false
    await loadModels()
  } catch (e: any) {
    toast.error('保存失败: ' + (e.message || 'Unknown error'))
  }
}

async function toggleModel(model: ModelConfig) {
  await client.put(`/models/${model.id}`, { enabled: !model.enabled })
  await loadModels()
}

async function deleteModel(id: string) {
  if (!confirm('Delete this model configuration?')) return
  await client.delete(`/models/${id}`)
  await loadModels()
}

async function testModel(id: string) {
  testResults.value[id] = 'Testing...'
  try {
    const { data } = await client.post(`/models/${id}/test`)
    testResults.value[id] = data.data?.ok ? `SUCCESS: ${data.data.message}` : `FAILED: ${data.data?.message || 'Connection failed'}`
  } catch {
    testResults.value[id] = 'FAILED: Request error'
  }
}

async function detectOllama() {
  try {
    const { data } = await client.get('/models/ollama/list')
    if (data.data?.length) {
      toast.success('检测到 Ollama 模型:\n' + data.data.map((m: any) => m.name).join('\n'), 8000)
    } else {
      toast.warning('未检测到本地 Ollama 模型，请确认 Ollama 正在运行。')
    }
  } catch { toast.error('无法连接到 Ollama') }
}

onMounted(loadModels)
</script>

<template>
  <div class="settings-view">
    <div class="settings-content">
      <header class="page-header">
        <div class="page-title-block">
          <h1 class="page-title">SYSTEM CONFIG</h1>
          <p class="page-subtitle">系统配置 — 模型管理与偏好设定</p>
        </div>
      </header>

      <div class="notice">
        <svg class="notice-icon" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
        </svg>
        <div class="notice-content">
          <strong>API KEY SECURITY</strong>
          <p>All API Keys are encrypted with AES-256-GCM before storage. Never stored in plaintext.</p>
        </div>
      </div>

      <section class="section">
        <div class="section-header">
          <h2>
            <svg viewBox="0 0 24 24" fill="currentColor" class="section-icon">
              <path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58a.49.49 0 00.12-.61l-1.92-3.32a.49.49 0 00-.59-.22l-2.39.96a7.03 7.03 0 00-1.62-.94l-.36-2.54A.483.483 0 0012 2h-1c-.25 0-.46.18-.5.42l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96a.49.49 0 00-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58a.49.49 0 00-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.36 1.03.7 1.62.94l.36 2.54c.04.24.25.42.5.42h1c.25 0 .46-.18.5-.42l.36-2.54c.59-.24 1.13-.57 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
            </svg>
            MODEL MANAGEMENT
          </h2>
          <div class="section-actions">
            <button class="btn btn-ghost" @click="detectOllama">
              <svg viewBox="0 0 20 20" fill="currentColor"><circle cx="10" cy="10" r="8"/><path d="M10 6v4l3 3" stroke="var(--bg-primary)" stroke-width="2" fill="none"/></svg>
              DETECT OLLAMA
            </button>
            <button class="btn btn-primary" @click="openAdd">+ ADD MODEL</button>
          </div>
        </div>

        <div v-if="loading" class="loading">
          <div class="loading-spinner"></div>
          <span>LOADING...</span>
        </div>

        <table v-else-if="models.length > 0" class="model-table">
          <thead>
            <tr>
              <th>MODEL NAME</th>
              <th>PROVIDER</th>
              <th>STATUS</th>
              <th>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in models" :key="m.id">
              <td class="model-name">{{ m.display_name || m.model_name }}</td>
              <td>
                <span class="provider-badge" :style="{ borderColor: providerColors[m.provider], color: providerColors[m.provider] }">
                  {{ { deepseek: 'DeepSeek', qwen: 'DashScope', ollama: 'Ollama', mimo: 'Xiaomi MIMO' }[m.provider] || m.provider }}
                </span>
              </td>
              <td>
                <button
                  class="status-badge"
                  :class="{ enabled: m.enabled }"
                  @click="toggleModel(m)"
                >
                  <span class="status-dot"></span>
                  {{ m.enabled ? 'ENABLED' : 'DISABLED' }}
                </button>
              </td>
              <td class="actions">
                <button class="btn btn-ghost btn-sm" @click="testModel(m.id)">TEST</button>
                <button class="btn btn-ghost btn-sm" @click="openEdit(m)">EDIT</button>
                <button class="btn btn-danger btn-sm" @click="deleteModel(m.id)">DELETE</button>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-else class="empty-hint">
          No models configured. Click "Add Model" to start.
        </div>

        <div v-for="(result, id) in testResults" :key="id" class="test-result" :class="{ success: result.includes('SUCCESS') }">
          <span class="result-icon">{{ result.includes('SUCCESS') ? '✓' : '✕' }}</span>
          <span class="result-text">{{ result }}</span>
        </div>
      </section>

      <section class="section">
        <h2 class="section-title">
          <svg viewBox="0 0 24 24" fill="currentColor" class="section-icon">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
          </svg>
          DEFAULT MODEL CONFIG
        </h2>
        <p class="section-desc">Set the default model for different modules.</p>

        <div class="defaults-grid">
          <div class="default-item">
            <label>CHAT MODEL</label>
            <select v-model="defaultChatModel" @change="saveDefaults" class="field">
              <option value="" disabled>Select...</option>
              <option v-for="m in enabledModels" :key="m.id" :value="m.id">
                {{ m.display_name || m.model_name }}
              </option>
            </select>
            <span class="field-hint">Model used by AI Chat Assistant</span>
          </div>

          <div class="default-item">
            <label>COMPILE MODEL</label>
            <select v-model="defaultCompileModel" @change="saveDefaults" class="field">
              <option value="" disabled>Select...</option>
              <option v-for="m in enabledModels" :key="m.id" :value="m.id">
                {{ m.display_name || m.model_name }}
              </option>
            </select>
            <span class="field-hint">Model used by Wiki Compile Engine</span>
          </div>
        </div>

        <div v-if="enabledModels.length === 0" class="empty-hint">
          Add and enable at least one model above first.
        </div>
      </section>

      <section class="section">
        <h2 class="section-title">
          <svg viewBox="0 0 24 24" fill="currentColor" class="section-icon">
            <path d="M12 3c-4.97 0-9 4.03-9 9s4.03 9 9 9 9-4.03 9-9-4.03-9-9-9zm0 16c-3.86 0-7-3.14-7-7s3.14-7 7-7 7 3.14 7 7-3.14 7-7 7zm1-11h-2v3H8v2h3v3h2v-3h3v-2h-3V8z"/>
          </svg>
          THEME CONFIG
        </h2>
        <p class="section-desc">Choose your preferred visual theme.</p>

        <div class="theme-grid">
          <div
            v-for="theme in themes"
            :key="theme.id"
            class="theme-card"
            :class="{ active: settingsStore.theme === theme.id }"
            @click="setTheme(theme.id)"
          >
            <div class="theme-preview" :style="{ background: theme.preview }"></div>
            <span class="theme-name">{{ theme.name }}</span>
            <span class="theme-desc">{{ theme.desc }}</span>
          </div>
        </div>
      </section>
    </div>

    <Teleport to="body">
      <div v-if="showForm" class="dialog-overlay" @click.self="showForm = false" @keydown.esc.window="showForm = false">
        <div class="dialog">
          <div class="dialog-header">
            <h2>{{ editingModel ? '[EDIT]' : '[NEW]' }} MODEL CONFIG</h2>
            <button class="btn-icon" @click="showForm = false">
              <svg viewBox="0 0 20 20" fill="currentColor"><path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"/></svg>
            </button>
          </div>

          <div class="dialog-body">
            <label>PROVIDER</label>
            <select v-model="form.provider" class="field">
              <option v-for="p in providerOptions" :key="p.value" :value="p.value">{{ p.label }}</option>
            </select>

            <label>MODEL NAME</label>
            <input v-model="form.model_name" class="field" :placeholder="selectedProvider?.hint || 'Model name'" />
            <span class="field-hint" v-if="selectedProvider?.hint">{{ selectedProvider.hint }}</span>

            <label>DISPLAY NAME</label>
            <input v-model="form.display_name" class="field" placeholder="Optional, for UI display" />

            <template v-if="form.provider !== 'ollama'">
              <label>API KEY</label>
              <input
                v-model="form.api_key"
                type="password"
                class="field"
                :class="{ invalid: apiKeyError }"
                :placeholder="editingModel ? 'Leave empty to keep current' : 'Enter API Key'"
              />
              <span v-if="apiKeyError" class="field-error">{{ apiKeyError }}</span>
            </template>

            <label>API ENDPOINT</label>
            <input
              v-model="form.endpoint"
              class="field"
              :class="{ invalid: endpointError }"
              :placeholder="providerOptions.find(p => p.value === form.provider)?.defaultEndpoint"
            />
            <span v-if="endpointError" class="field-error">{{ endpointError }}</span>
          </div>

          <div class="dialog-footer">
            <button class="btn btn-ghost" @click="showForm = false">CANCEL</button>
            <button class="btn btn-primary" @click="saveModel" :disabled="!formValid">
              SAVE
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.settings-view {
  height: 100%;
  overflow-y: auto;
}

.settings-content {
  max-width: 900px;
  margin: 0 auto;
  padding: 32px;
}

.page-header {
  margin-bottom: 28px;
}

.page-title-block {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.title-prefix {
  font-family: var(--font-mono);
  font-size: 1.2rem;
  color: var(--accent);
  opacity: 0.6;
}

.page-title {
  font-family: var(--font-display);
  font-size: 1.4rem;
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

.notice {
  display: flex;
  gap: 16px;
  background: var(--accent-ghost);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius-md);
  padding: 16px 20px;
  margin-bottom: 32px;
}

.notice-icon {
  width: 24px;
  height: 24px;
  color: var(--accent);
  flex-shrink: 0;
}

.notice-content strong {
  display: block;
  font-family: var(--font-display);
  font-size: 0.85rem;
  color: var(--accent);
  letter-spacing: 0.1em;
  margin-bottom: 6px;
}

.notice-content p {
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

.section {
  margin-bottom: 40px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h2,
.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-display);
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.1em;
}

.section-icon {
  width: 20px;
  height: 20px;
  color: var(--accent);
}

.section-title {
  margin-bottom: 8px;
}

.section-desc {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin-bottom: 20px;
}

.section-actions {
  display: flex;
  gap: 10px;
}

.section-actions .btn-ghost {
  gap: 6px;
}

.section-actions .btn-ghost svg {
  width: 14px;
  height: 14px;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 40px;
}

.loading-spinner {
  width: 28px;
  height: 28px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.loading span {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-muted);
  letter-spacing: 0.2em;
}

.model-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.model-table th {
  text-align: left;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  color: var(--text-muted);
  font-family: var(--font-display);
  font-weight: 500;
  font-size: 0.7rem;
  letter-spacing: 0.15em;
}

.model-table td {
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-dim);
}

.model-name {
  font-family: var(--font-mono);
  font-weight: 500;
  color: var(--text-primary);
}

.provider-badge {
  display: inline-block;
  padding: 3px 10px;
  border: 1px solid;
  border-radius: var(--radius-sm);
  font-family: var(--font-display);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 12px;
  border-radius: var(--radius-sm);
  font-family: var(--font-display);
  font-size: 0.65rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  background: rgba(255, 71, 87, 0.1);
  color: var(--error);
  border: 1px solid rgba(255, 71, 87, 0.2);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.status-badge.enabled {
  background: rgba(0, 255, 136, 0.1);
  color: var(--neon-green);
  border-color: rgba(0, 255, 136, 0.2);
}

.status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.actions {
  display: flex;
  gap: 6px;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 0.7rem;
}

.test-result {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  padding: 10px 14px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.test-result.success {
  border-color: var(--neon-green);
  background: rgba(0, 255, 136, 0.05);
}

.result-icon {
  font-size: 0.9rem;
}

.test-result.success .result-icon { color: var(--neon-green); }
.test-result:not(.success) .result-icon { color: var(--error); }

.result-text {
  color: var(--text-secondary);
}

.empty-hint {
  text-align: center;
  padding: 32px;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.defaults-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.default-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.default-item label {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: 0.1em;
}

.field {
  width: 100%;
  padding: 10px 14px;
  font-size: 0.85rem;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  transition: border-color 0.15s, box-shadow 0.15s;
}

select.field {
  cursor: pointer;
}

/* P2-47: inline validation state for endpoint + api_key */
.field.invalid {
  border-color: var(--error);
}

.field.invalid:focus {
  box-shadow: 0 0 0 2px rgba(255, 71, 87, 0.2);
}

.field-error {
  font-size: 0.7rem;
  color: var(--error);
  margin-top: 2px;
}

.field-hint {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(3, 3, 8, 0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.dialog {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  width: 500px;
  max-width: 90vw;
  max-height: 90vh;
  overflow-y: auto;
  position: relative;
}

.dialog::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--accent), var(--neon-magenta));
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-dim);
}

.dialog-header h2 {
  font-family: var(--font-display);
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--accent);
  letter-spacing: 0.1em;
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

.dialog-body {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dialog-body label {
  font-family: var(--font-display);
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: 0.08em;
  margin-top: 12px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--border-dim);
}

.theme-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-top: 16px;
}

.theme-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  background: var(--bg-card);
  border: 2px solid var(--border-dim);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-smooth);
}

.theme-card:hover {
  border-color: var(--border);
  transform: translateY(-2px);
}

.theme-card.active {
  border-color: var(--accent);
  box-shadow: 0 0 16px var(--accent-ghost);
}

.theme-preview {
  width: 100%;
  height: 80px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

.theme-name {
  font-family: var(--font-display);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.05em;
}

.theme-desc {
  font-size: 0.75rem;
  color: var(--text-muted);
}

@media (max-width: 600px) {
  .theme-grid {
    grid-template-columns: 1fr;
  }
}
</style>
