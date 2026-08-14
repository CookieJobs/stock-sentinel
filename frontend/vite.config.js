import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import process from 'node:process'

// 后端端口：环境变量 BACKEND_PORT > 8000
const backendPort = process.env.BACKEND_PORT || '8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../backend/static',
    emptyOutDir: true
  },
  server: {
    port: 5173,
    proxy: {
      '/api': `http://127.0.0.1:${backendPort}`
    }
  }
})
