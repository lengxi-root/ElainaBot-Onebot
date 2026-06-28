<template>
  <div class="logs-page">
    <header class="page-header">
      <h1>系统日志</h1>
      <p class="subtitle">框架运行日志</p>
    </header>

    <div class="card logs-container">
      <div class="logs-toolbar">
        <select v-model="logType" @change="loadLogs" class="filter-select">
          <option value="message">消息日志</option>
          <option value="framework">框架日志</option>
        </select>
        <button @click="loadLogs" class="btn btn-secondary">刷新</button>
      </div>

      <div class="logs-list">
        <div v-for="entry in logs" :key="entry.id" class="log-item">
          <span class="log-time">{{ entry.timestamp }}</span>
          <span class="log-level" :class="'level-' + (entry.level || 'INFO').toLowerCase()">
            {{ entry.level || 'INFO' }}
          </span>
          <span class="log-content">{{ entry.content }}</span>
        </div>
        <p v-if="!logs.length" class="empty-text">暂无日志</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const logType = ref('message')
const logs = ref([])

async function loadLogs() {
  const res = await store.fetchApi(`/logs/${logType.value}`)
  if (res && res.success) {
    logs.value = res.data || []
  }
}

onMounted(loadLogs)
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

.logs-container {
  padding: 0;
  overflow: hidden;
}

.logs-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border-light);
}

.filter-select {
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  outline: none;
  background: var(--color-bg);
}

.logs-list {
  max-height: 600px;
  overflow-y: auto;
  padding: 12px 20px;
}

.log-item {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border-light);
  font-size: 13px;
}

.log-item:last-child {
  border-bottom: none;
}

.log-time {
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: nowrap;
}

.log-level {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
  white-space: nowrap;
}

.level-info {
  background: #eef0ff;
  color: var(--color-primary);
}

.level-warning {
  background: #fef3c7;
  color: #92400e;
}

.level-error {
  background: #fee2e2;
  color: #991b1b;
}

.log-content {
  color: var(--color-text);
  word-break: break-all;
}

.empty-text {
  color: var(--color-text-muted);
  font-size: 13px;
  text-align: center;
  padding: 40px;
}
</style>
