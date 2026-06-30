<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const errorMsg = ref('')

// P2-46: client-side validation aligned with backend constraints.
// Username: 3-100 chars, [a-z0-9_-]. Password: min 6 chars on register,
// non-empty on login (the backend re-validates either way).
const USERNAME_RE = /^[a-z0-9_-]{3,100}$/

const usernameError = computed(() => {
  const v = username.value.trim()
  if (!v) return ''
  if (!USERNAME_RE.test(v)) return '用户名只能包含小写字母、数字、下划线、连字符（3-100 字符）'
  return ''
})

const passwordError = computed(() => {
  const v = password.value
  if (!v) return ''
  if (mode.value === 'register' && v.length < 6) return '密码至少 6 个字符'
  return ''
})

const canSubmit = computed(() => {
  if (authStore.loading) return false
  if (!username.value.trim() || !password.value) return false
  if (usernameError.value || passwordError.value) return false
  return true
})

async function submit() {
  // Trim before sending so leading/trailing spaces don't silently fail auth.
  username.value = username.value.trim()
  if (!USERNAME_RE.test(username.value)) {
    errorMsg.value = '用户名格式不正确'
    return
  }
  if (mode.value === 'register' && password.value.length < 6) {
    errorMsg.value = '密码至少 6 个字符'
    return
  }
  errorMsg.value = ''
  const ok = mode.value === 'login'
    ? await authStore.login(username.value, password.value)
    : await authStore.register(username.value, password.value)
  if (ok) {
    // Return to the page the user was trying to access before 401, if any.
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    router.push(redirect || '/memos')
  } else {
    errorMsg.value = authStore.error || '操作失败'
  }
}

function toggleMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  errorMsg.value = ''
}
</script>

<template>
  <div class="auth-view">
    <div class="auth-card">
      <div class="auth-header">
        <div class="brand-icon">
          <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M20 4L4 20L20 36L36 20L20 4Z" stroke="currentColor" stroke-width="1.5" fill="none"/>
            <path d="M20 10L10 20L20 30L30 20L20 10Z" stroke="currentColor" stroke-width="1.5" fill="none"/>
            <circle cx="20" cy="20" r="3" fill="currentColor"/>
          </svg>
        </div>
        <h1 class="auth-title">CYBER<span>NOTE</span></h1>
        <p class="auth-subtitle">// {{ mode === 'login' ? 'ACCESS TERMINAL' : 'NEW IDENTITY' }}</p>
      </div>

      <form class="auth-form" @submit.prevent="submit">
        <div class="field">
          <label class="field-label">USERNAME</label>
          <input
            v-model="username"
            type="text"
            class="field-input"
            :class="{ invalid: usernameError }"
            placeholder="3-100 chars, a-z 0-9 _ -"
            autocomplete="username"
            autocapitalize="none"
            spellcheck="false"
          />
          <p v-if="usernameError" class="field-error">{{ usernameError }}</p>
        </div>

        <div class="field">
          <label class="field-label">PASSWORD</label>
          <input
            v-model="password"
            type="password"
            class="field-input"
            :class="{ invalid: passwordError }"
            :placeholder="mode === 'register' ? 'min 6 chars' : 'password'"
            :autocomplete="mode === 'register' ? 'new-password' : 'current-password'"
          />
          <p v-if="passwordError" class="field-error">{{ passwordError }}</p>
        </div>

        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

        <button type="submit" class="submit-btn" :disabled="!canSubmit">
          {{ authStore.loading ? 'PROCESSING...' : (mode === 'login' ? 'LOGIN' : 'REGISTER') }}
        </button>
      </form>

      <div class="auth-footer">
        <span v-if="mode === 'login'">No account?</span>
        <span v-else>Already registered?</span>
        <button class="toggle-btn" @click="toggleMode">
          {{ mode === 'login' ? 'Register' : 'Login' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-view {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-void);
  position: relative;
  overflow: hidden;
}

.auth-view::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 20% 30%, var(--accent-glow), transparent 40%),
    radial-gradient(circle at 80% 70%, var(--neon-magenta-glow), transparent 40%);
  pointer-events: none;
}

.auth-card {
  position: relative;
  width: 380px;
  max-width: 90vw;
  padding: 40px 32px;
  background: var(--bg-card);
  border: 1px solid var(--border-bright);
  box-shadow: var(--glow-md);
  z-index: 1;
}

.auth-header {
  text-align: center;
  margin-bottom: 32px;
}

.brand-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto 16px;
  color: var(--accent);
  filter: drop-shadow(0 0 8px var(--accent-glow));
}

.auth-title {
  font-size: 24px;
  font-weight: 900;
  letter-spacing: 4px;
  color: var(--text-primary);
  margin: 0;
}

.auth-title span {
  color: var(--accent);
}

.auth-subtitle {
  font-size: 11px;
  color: var(--text-muted);
  letter-spacing: 2px;
  margin-top: 8px;
  font-family: var(--font-mono);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 10px;
  letter-spacing: 2px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.field-input {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  color: var(--text-primary);
  padding: 10px 12px;
  font-size: 14px;
  font-family: var(--font-mono);
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.field-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-ghost);
}

.field-input::placeholder {
  color: var(--text-ghost);
}

/* P2-46: inline validation state */
.field-input.invalid {
  border-color: var(--error);
}

.field-input.invalid:focus {
  box-shadow: 0 0 0 2px rgba(255, 71, 87, 0.2);
}

.field-error {
  color: var(--error);
  font-size: 11px;
  margin: 0;
  font-family: var(--font-mono);
}

.error-msg {
  color: var(--error);
  font-size: 12px;
  margin: 0;
  font-family: var(--font-mono);
}

.submit-btn {
  margin-top: 8px;
  padding: 12px;
  background: transparent;
  border: 1px solid var(--accent);
  color: var(--accent);
  font-size: 13px;
  letter-spacing: 3px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s;
  font-family: var(--font-mono);
}

.submit-btn:hover:not(:disabled) {
  background: var(--accent);
  color: var(--bg-void);
  box-shadow: var(--glow-sm);
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.auth-footer {
  margin-top: 24px;
  text-align: center;
  font-size: 12px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.toggle-btn {
  background: none;
  border: none;
  color: var(--accent);
  cursor: pointer;
  margin-left: 6px;
  text-decoration: underline;
  font-size: 12px;
  font-family: var(--font-mono);
}

.toggle-btn:hover {
  color: var(--accent-hover);
}
</style>
