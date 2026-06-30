import { defineStore } from 'pinia'
import { ref } from 'vue'

export type ToastKind = 'info' | 'success' | 'warning' | 'error'

export interface ToastItem {
  id: number
  kind: ToastKind
  message: string
  /** Auto-dismiss timeout in ms. 0 = sticky (manual dismiss only). */
  timeout: number
}

let _nextId = 1

/**
 * Minimal toast notification store. Designed to replace the most jarring
 * blocking `alert()` calls (file errors, save failures, missing-config
 * warnings) with a non-blocking corner notification.
 *
 * `confirm()` calls are NOT replaced — those legitimately need to block.
 */
export const useToastStore = defineStore('toast', () => {
  const toasts = ref<ToastItem[]>([])

  function push(message: string, kind: ToastKind = 'info', timeout = 3500) {
    const id = _nextId++
    toasts.value.push({ id, kind, message, timeout })
    if (timeout > 0) {
      window.setTimeout(() => dismiss(id), timeout)
    }
    // Cap the stack so a runaway caller can't flood the screen.
    if (toasts.value.length > 5) {
      toasts.value.splice(0, toasts.value.length - 5)
    }
    return id
  }

  function info(message: string, timeout?: number) { return push(message, 'info', timeout) }
  function success(message: string, timeout?: number) { return push(message, 'success', timeout) }
  function warning(message: string, timeout?: number) { return push(message, 'warning', timeout) }
  function error(message: string, timeout?: number) { return push(message, 'error', timeout ?? 5000) }

  function dismiss(id: number) {
    const idx = toasts.value.findIndex((t) => t.id === id)
    if (idx >= 0) toasts.value.splice(idx, 1)
  }

  function clear() {
    toasts.value = []
  }

  return { toasts, push, info, success, warning, error, dismiss, clear }
})
