import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './styles/global.css'

const app = createApp(App)

// Global error handler — prevents white-screen on uncaught render errors
app.config.errorHandler = (err, _instance, info) => {
  console.error('[Vue Error]', err, '\nComponent:', info)
}

app.use(createPinia())
app.use(router)
app.mount('#app')
