import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router, { fetchAuthMode } from './router'
import { useToastStore } from './stores/toast'
import './styles/global.css'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

// P2-51: global error handler — prevents white-screen on uncaught render
// errors and surfaces them as a toast so the user knows something went
// wrong instead of staring at a frozen UI. Pinia must be registered first
// so useToastStore() can resolve the store at error time.
app.config.errorHandler = (err, _instance, info) => {
  console.error('[Vue Error]', err, '\nComponent:', info)
  try {
    const toast = useToastStore(pinia)
    const msg = err instanceof Error ? err.message : String(err)
    toast.error('界面渲染错误: ' + msg)
  } catch {
    // toast store unavailable — console.error above is the fallback
  }
}

// Fetch auth mode before mounting so the router guard has the correct value.
// This determines whether the login page is shown (jwt) or skipped (none).
await fetchAuthMode()

app.use(router)
app.mount('#app')
