import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  base: '/web/',
  server: {
    proxy: {
      '/api': 'http://localhost:5201',
      '/ws': { target: 'ws://localhost:5201', ws: true },
    },
  },
  build: {
    target: 'es2015',
    outDir: '../dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        chunkFileNames: 'assets/[name].js',
        entryFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name].[ext]',
      },
    },
  },
})
