<template>
  <div class="dashboard">
    <header class="page-header">
      <h1>仪表盘</h1>
      <p class="subtitle">系统运行状态概览</p>
    </header>

    <div class="stats-grid">
      <div class="stat-card card">
        <div class="stat-icon" style="background: #eef0ff; color: var(--color-primary);">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ info?.bot_count || 0 }}</span>
          <span class="stat-label">Bot 连接</span>
        </div>
      </div>

      <div class="stat-card card">
        <div class="stat-icon" style="background: #dcfce7; color: #166534;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ info?.plugin_count || 0 }}</span>
          <span class="stat-label">插件</span>
        </div>
      </div>

      <div class="stat-card card">
        <div class="stat-icon" style="background: #fef3c7; color: #92400e;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2"/><path d="M7 2v20M17 2v20M2 12h20"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ info?.module_count || 0 }}</span>
          <span class="stat-label">模块</span>
        </div>
      </div>

      <div class="stat-card card">
        <div class="stat-icon" style="background: #ede9fe; color: #5b21b6;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ info?.cpu_percent || 0 }}%</span>
          <span class="stat-label">CPU</span>
        </div>
      </div>
    </div>

    <div class="info-grid">
      <div class="card info-card">
        <h3>系统信息</h3>
        <div class="info-list">
          <div class="info-row">
            <span class="info-key">框架</span>
            <span class="info-val">{{ info?.framework_name || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="info-key">平台</span>
            <span class="info-val">{{ info?.platform || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="info-key">Python</span>
            <span class="info-val">{{ info?.python_version || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="info-key">内存</span>
            <span class="info-val">{{ formatMemory(info?.memory_used) }} / {{ formatMemory(info?.memory_total) }}</span>
          </div>
        </div>
      </div>

      <div class="card info-card">
        <h3>Bot 连接</h3>
        <div v-if="info?.bots && Object.keys(info.bots).length" class="bot-list">
          <div v-for="(type, id) in info.bots" :key="id" class="bot-item">
            <span class="badge badge-success">{{ type }}</span>
            <span class="bot-id">{{ id }}</span>
          </div>
        </div>
        <p v-else class="empty-text">暂无 Bot 连接</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const info = computed(() => store.systemInfo)

onMounted(() => {
  store.loadSystemInfo()
  setInterval(() => store.loadSystemInfo(), 10000)
})

function formatMemory(bytes) {
  if (!bytes) return '-'
  const mb = bytes / 1024 / 1024
  if (mb > 1024) return (mb / 1024).toFixed(1) + ' GB'
  return mb.toFixed(0) + ' MB'
}
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-content {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--color-text-muted);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}

.info-card {
  padding: 20px;
}

.info-card h3 {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 16px;
  color: var(--color-text);
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-key {
  font-size: 13px;
  color: var(--color-text-muted);
}

.info-val {
  font-size: 13px;
  font-weight: 500;
}

.bot-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bot-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-sm);
}

.bot-id {
  font-size: 13px;
  font-family: var(--font-mono);
}

.empty-text {
  color: var(--color-text-muted);
  font-size: 13px;
  text-align: center;
  padding: 20px;
}
</style>
