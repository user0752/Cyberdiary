import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('error', () => {
            // Suppress ECONNREFUSED noise when backend is not yet ready
          });
        },
      },
    },
  },
  build: {
    // P2-27: split heavy vendor deps into their own chunks so that the main
    // app bundle stays small and the big libs (three/d3/codemirror) can be
    // cached independently across deploys. Hashed filenames + nginx 1y
    // immutable cache on /assets/ make this a one-time download per user.
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('three')) return 'three'
            if (id.includes('d3-force') || id.includes('d3-quadtree')) return 'd3'
            if (id.includes('@codemirror')) return 'codemirror'
            if (id.includes('markdown-it') || id.includes('highlight.js')) return 'markdown'
            if (id.includes('vue') || id.includes('pinia')) return 'vue'
          }
          return undefined
        },
      },
    },
  },
})
