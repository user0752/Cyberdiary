import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import * as authApi from '../api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('cybernote-token'))
  const username = ref<string | null>(localStorage.getItem('cybernote-username'))
  const loading = ref(false)
  const error = ref<string | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  function setAuth(t: string, u: string) {
    token.value = t
    username.value = u
    localStorage.setItem('cybernote-token', t)
    localStorage.setItem('cybernote-username', u)
  }

  function clearAuth() {
    token.value = null
    username.value = null
    localStorage.removeItem('cybernote-token')
    localStorage.removeItem('cybernote-username')
  }

  async function register(user: string, pass: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const res = await authApi.register(user, pass)
      setAuth(res.access_token, res.username)
      return true
    } catch (e: any) {
      error.value = e.message || 'Registration failed'
      return false
    } finally {
      loading.value = false
    }
  }

  async function login(user: string, pass: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const res = await authApi.login(user, pass)
      setAuth(res.access_token, res.username)
      return true
    } catch (e: any) {
      error.value = e.message || 'Login failed'
      return false
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    // Notify backend to revoke the token's jti (best-effort), then clear
    // local state regardless of the response.
    await authApi.logout()
    clearAuth()
  }

  return {
    token,
    username,
    loading,
    error,
    isAuthenticated,
    register,
    login,
    logout,
  }
})
