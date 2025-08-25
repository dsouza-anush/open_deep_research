import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './ui/src'),
    },
  },
  build: {
    outDir: '../src/open_deep_research/static',
    emptyOutDir: true,
    assetsDir: 'assets',
  },
  root: 'ui',
  server: {
    proxy: {
      '/research': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/config': 'http://localhost:8000',
      '/debug': 'http://localhost:8000'
    }
  }
})