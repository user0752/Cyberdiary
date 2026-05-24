import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
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
  ],
})

export default router
