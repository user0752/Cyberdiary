<script setup lang="ts">
import { useToastStore } from '../stores/toast'

const store = useToastStore()

const icons: Record<string, string> = {
  info: 'M8 10h1v4H8v-4zm0-3h1v1H8V7zm.5-5a8 8 0 100 16 8 8 0 000-16z',
  success: 'M12 2a10 10 0 100 20 10 10 0 000-20zm-3.5 9.5L10 13l5-5-1-1-4 4-1.5-1.5-1 1z',
  warning: 'M12 2L2 20h20L12 2zm-1 6h2v6h-2V8zm0 8h2v2h-2v-2z',
  error: 'M12 2a10 10 0 100 20 10 10 0 000-20zm5 13.5L13.5 12 17 8.5 15.5 7 12 10.5 8.5 7 7 8.5 10.5 12 7 15.5 8.5 17 12 13.5 15.5 17 17 15.5z',
}
</script>

<template>
  <div class="toast-container" aria-live="polite" aria-atomic="false">
    <TransitionGroup name="toast">
      <div
        v-for="t in store.toasts"
        :key="t.id"
        class="toast"
        :class="t.kind"
        role="alert"
      >
        <svg class="toast-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path :d="icons[t.kind]" />
        </svg>
        <span class="toast-message">{{ t.message }}</span>
        <button
          class="toast-close"
          type="button"
          aria-label="关闭通知"
          @click="store.dismiss(t.id)"
        >
          <svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 10000;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 360px;
  width: calc(100vw - 32px);
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-bright);
  border-left: 3px solid var(--accent);
  border-radius: var(--radius-md);
  box-shadow: var(--glow-md);
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: var(--text-primary);
  pointer-events: auto;
  backdrop-filter: blur(10px);
}

.toast.info { border-left-color: var(--accent); }
.toast.success { border-left-color: var(--neon-green); }
.toast.warning { border-left-color: var(--neon-yellow); }
.toast.error { border-left-color: var(--error); }

.toast.info .toast-icon { color: var(--accent); }
.toast.success .toast-icon { color: var(--neon-green); }
.toast.warning .toast-icon { color: var(--neon-yellow); }
.toast.error .toast-icon { color: var(--error); }

.toast-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  margin-top: 1px;
}

.toast-message {
  flex: 1;
  line-height: 1.5;
  word-break: break-word;
  white-space: pre-line;
}

.toast-close {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: color var(--transition-fast), background var(--transition-fast);
}

.toast-close:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.toast-close svg {
  width: 12px;
  height: 12px;
}

/* Vue TransitionGroup animations */
.toast-enter-active,
.toast-leave-active {
  transition: all var(--transition-smooth);
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(40px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(40px);
}

.toast-move {
  transition: transform var(--transition-smooth);
}

@media (max-width: 768px) {
  .toast-container {
    top: 8px;
    right: 8px;
    left: 8px;
    width: auto;
    max-width: none;
  }
}
</style>
