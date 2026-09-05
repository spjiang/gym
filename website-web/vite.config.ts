import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5175,
    proxy: {
      '/api': 'http://127.0.0.1:18000',
      '/media': {
        target: 'http://127.0.0.1:8900',
        rewrite: (path) => path.replace(/^\/media/, '/public'),
      },
    },
  },
})
