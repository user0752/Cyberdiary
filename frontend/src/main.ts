import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router, { fetchAuthMode } from './router'
import './styles/global.css'

const app = createApp(App)

// Global error handler — prevents white-screen on uncaught render errors
app.config.errorHandler = (err, _instance, info) => {
  console.error('[Vue Error]', err, '\nComponent:', info)
}

app.use(createPinia())

// Fetch auth mode before mounting so the router guard has the correct value.
// This determines whether the login page is shown (jwt) or skipped (none).
await fetchAuthMode()

app.use(router)
app.mount('#app')
