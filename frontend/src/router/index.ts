import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

// Cached auth mode — fetched once on app boot via fetchAuthMode().
// Defaults to 'jwt' (secure) until the backend responds.
let _authMode: 'jwt' | 'none' = 'jwt'

export async function fetchAuthMode(): Promise<void> {
  try {
    const res = await fetch('/api/config')
    if (res.ok) {
      const body = await res.json()
      if (body?.data?.auth_mode === 'none') _authMode = 'none'
    }
  } catch {
    // Network error — keep 'jwt' default (safer)
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
    { path: '/', redirect: '/memos' },
    {
      path: '/memos',
      name: 'memos',
      component: () => import('../views/MemoFlow.vue'),
    },
    {
      path: '/wiki',
      name: 'wiki',
      component: () => import('../views/WikiHub.vue'),
    },
    {
      path: '/wiki/:slug',
      name: 'wiki-page',
      component: () => import('../views/WikiPage.vue'),
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('../views/ChatView.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/Settings.vue'),
    },
    {
      path: '/game',
      name: 'game',
      component: () => import('../views/GameArena.vue'),
    },
    {
      path: '/compile',
      name: 'compile',
      component: () => import('../views/MultiAgentCompileView.vue'),
    },
    {
      path: '/graph',
      name: 'graph',
      component: () => import('../views/KnowledgeGraphView.vue'),
    },
  ],
})

// Navigation guard — redirect to /login when JWT auth is required but no token.
// In 'none' mode the backend doesn't require tokens, so we skip the guard.
router.beforeEach((to) => {
  const authStore = useAuthStore()
  if (to.name === 'login') {
    if (authStore.isAuthenticated) {
      return { name: 'memos' }
    }
    return true
  }
  if (_authMode === 'jwt' && !authStore.isAuthenticated) {
    return { name: 'login' }
  }
  return true
})

export default router
