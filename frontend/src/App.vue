<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useSettingsStore } from './stores/settings'
import { useAuthStore } from './stores/auth'
import { onMounted, computed } from 'vue'

const route = useRoute()
const router = useRouter()
const settingsStore = useSettingsStore()
const authStore = useAuthStore()

const navItems = [
  { path: '/memos', label: 'MEMO', icon: '01', sub: '笔记流' },
  { path: '/wiki', label: 'WIKI', icon: '02', sub: '知识库' },
  { path: '/chat', label: 'CHAT', icon: '03', sub: 'AI对话' },
  { path: '/game', label: 'GAME', icon: '04', sub: '知识闯关' },
  { path: '/compile', label: 'COMP', icon: '05', sub: '智能编译' },
  { path: '/graph', label: 'GRAPH', icon: '06', sub: '知识图谱' },
  { path: '/settings', label: 'SYS', icon: '07', sub: '系统设置' },
]

const showAuth = computed(() => authStore.isAuthenticated)

function logout() {
  authStore.logout()
  router.push('/login')
}

onMounted(() => {
  settingsStore.init()
})
</script>

<template>
  <div class="app-layout scanlines noise">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-top">
        <div class="brand-block">
          <div class="brand-icon">
            <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M20 4L4 20L20 36L36 20L20 4Z" stroke="currentColor" stroke-width="1.5" fill="none"/>
              <path d="M20 10L10 20L20 30L30 20L20 10Z" stroke="currentColor" stroke-width="1.5" fill="none"/>
              <circle cx="20" cy="20" r="3" fill="currentColor"/>
            </svg>
          </div>
          <div class="brand-text">
            <span class="brand-title">CYBER</span>
            <span class="brand-sub">NOTE</span>
          </div>
        </div>
        <div class="status-bar">
          <span class="status-dot"></span>
          <span class="status-text">SYSTEM ONLINE</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-section-label">// NAVIGATION</div>
        <RouterLink
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: route.path.startsWith(item.path) }"
        >
          <span class="nav-index">{{ item.icon }}</span>
          <div class="nav-content">
            <span class="nav-label">{{ item.label }}</span>
            <span class="nav-sub">{{ item.sub }}</span>
          </div>
          <div class="nav-indicator"></div>
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <div v-if="showAuth" class="user-block">
          <span class="user-name">{{ authStore.username }}</span>
          <button class="logout-btn" @click="logout">LOGOUT</button>
        </div>
        <div class="footer-line"></div>
        <div class="footer-info">
          <span class="version">v0.1.0</span>
          <span class="time">{{ new Date().toLocaleDateString('zh-CN') }}</span>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="main-content cyber-grid">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  background: var(--bg-void);
  transition: background-color var(--transition-smooth);
}

.sidebar {
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  background: var(--bg-deep);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

.sidebar::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  bottom: 0;
  width: 1px;
  background: linear-gradient(
    180deg,
    var(--accent) 0%,
    var(--accent-ghost) 50%,
    transparent 100%
  );
}

.sidebar-top {
  padding: 20px 16px;
  border-bottom: 1px solid var(--border-dim);
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.brand-icon {
  width: 36px;
  height: 36px;
  color: var(--accent);
  animation: neon-pulse 3s ease-in-out infinite;
}

.brand-icon svg {
  width: 100%;
  height: 100%;
}

.brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
}

.brand-title {
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.2em;
}

.brand-sub {
  font-family: var(--font-display);
  font-size: 0.65rem;
  font-weight: 500;
  color: var(--accent);
  letter-spacing: 0.3em;
}

.status-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  background: var(--bg-primary);
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--neon-green);
  box-shadow: 0 0 8px var(--neon-green-glow);
  animation: blink 2s ease-in-out infinite;
}

.status-text {
  font-size: 0.65rem;
  font-family: var(--font-mono);
  color: var(--text-muted);
  letter-spacing: 0.1em;
}

.sidebar-nav {
  flex: 1;
  padding: 20px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-section-label {
  font-size: 0.6rem;
  font-family: var(--font-mono);
  color: var(--text-ghost);
  padding: 0 8px;
  margin-bottom: 12px;
  letter-spacing: 0.15em;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  font-size: 0.85rem;
  font-weight: 500;
  transition: all var(--transition-fast);
  text-decoration: none;
  position: relative;
  overflow: hidden;
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--accent);
  transform: scaleY(0);
  transition: transform var(--transition-fast);
}

.nav-item:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-item:hover::before {
  transform: scaleY(1);
}

.nav-item.active {
  background: var(--accent-ghost);
  color: var(--accent);
}

.nav-item.active::before {
  transform: scaleY(1);
  box-shadow: 0 0 10px var(--accent-glow);
}

.nav-index {
  font-family: var(--font-display);
  font-size: 0.65rem;
  font-weight: 600;
  color: var(--text-ghost);
  letter-spacing: 0.05em;
  min-width: 20px;
}

.nav-item.active .nav-index {
  color: var(--accent);
  text-shadow: 0 0 8px var(--accent-glow);
}

.nav-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.nav-label {
  font-family: var(--font-display);
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.1em;
}

.nav-sub {
  font-size: 0.65rem;
  color: var(--text-ghost);
  letter-spacing: 0.05em;
}

.nav-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--border);
  transition: all var(--transition-fast);
}

.nav-item:hover .nav-indicator {
  background: var(--text-muted);
}

.nav-item.active .nav-indicator {
  background: var(--accent);
  box-shadow: 0 0 8px var(--accent-glow);
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid var(--border-dim);
}

.user-block {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding: 6px 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-dim);
}

.user-name {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--accent);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.65rem;
  letter-spacing: 1px;
  cursor: pointer;
  padding: 2px 6px;
  transition: color 0.2s;
}

.logout-btn:hover {
  color: var(--neon-magenta);
}

.footer-line {
  height: 1px;
  background: linear-gradient(90deg, var(--accent-dim), transparent);
  margin-bottom: 12px;
}

.footer-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.version {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-ghost);
}

.time {
  font-family: var(--font-mono);
  font-size: 0.6rem;
  color: var(--text-ghost);
}

.main-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--bg-primary);
  position: relative;
}
</style>
