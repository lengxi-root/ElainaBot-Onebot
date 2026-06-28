<template>
  <div class="plugins-page">
    <header class="page-header">
      <h1>插件管理</h1>
      <p class="subtitle">已加载的 OneBot 插件</p>
    </header>

    <div class="plugins-grid">
      <div v-for="plugin in plugins" :key="plugin.name" class="card plugin-card">
        <div class="plugin-header">
          <h3>{{ plugin.name }}</h3>
          <span class="badge" :class="plugin.loaded ? 'badge-success' : 'badge-danger'">
            {{ plugin.loaded ? '已加载' : '未加载' }}
          </span>
        </div>
        <div class="plugin-meta">
          <span>处理器: {{ plugin.handlers }}</span>
        </div>
        <div class="plugin-actions">
          <button @click="reloadPlugin(plugin.name)" class="btn btn-secondary">重载</button>
        </div>
      </div>
      <p v-if="!plugins.length" class="empty-text">暂无插件。将插件目录放入 <code>plugins/</code> 即可自动加载。</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const plugins = ref([])

async function loadPlugins() {
  const res = await store.fetchApi('/plugins/list')
  if (res && res.success) {
    plugins.value = res.data || []
  }
}

async function reloadPlugin(name) {
  await store.postApi('/plugins/reload', { name })
  await loadPlugins()
}

onMounted(loadPlugins)
</script>

<style scoped>
.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 700;
}

.subtitle {
  color: var(--color-text-muted);
  font-size: 14px;
  margin-top: 4px;
}

.plugins-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.plugin-card {
  padding: 20px;
}

.plugin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.plugin-header h3 {
  font-size: 15px;
  font-weight: 600;
}

.plugin-meta {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-bottom: 12px;
}

.plugin-actions {
  display: flex;
  gap: 8px;
}

.empty-text {
  color: var(--color-text-muted);
  font-size: 14px;
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px;
}

.empty-text code {
  background: var(--color-bg-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 13px;
}
</style>
