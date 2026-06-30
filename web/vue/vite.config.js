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
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (/[\\/]node_modules[\\/](@vue|vue|vue-router|pinia)[\\/]/.test(id)) return 'vue'
          if (/[\\/]node_modules[\\/](chart\.js|vue-chartjs|chartjs-plugin-datalabels|@kurkle)[\\/]/.test(id)) return 'charts'
          if (/[\\/]node_modules[\\/](naive-ui|vueuc|@css-render|css-render|seemly|treemate|vooks|evtd|@juggle|date-fns|lodash|lodash-es)[\\/]/.test(id)) return 'naive'
          return 'vendor'
        },
      },
    },
  },
})
