import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  base: '/web/',
  build: {
    outDir: resolve(__dirname, '../dist'),
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:5003',
      '/ws': {
        target: 'ws://localhost:5003',
        ws: true,
      },
    },
  },
})
