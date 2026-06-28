<template>
  <div class="logs-page">
    <header class="page-header">
      <h1>日志查看</h1>
      <p class="subtitle">框架运行日志</p>
    </header>

    <div class="card logs-container">
      <div class="logs-toolbar">
        <div class="log-tabs">
          <button
            v-for="tab in logTabs"
            :key="tab.key"
            :class="{ active: currentTab === tab.key }"
            @click="switchTab(tab.key)"
          >{{ tab.label }}</button>
        </div>
        <div class="toolbar-right">
          <button class="btn btn-secondary btn-sm" @click="loadLogs">刷新</button>
          <label class="auto-refresh">
            <input type="checkbox" v-model="autoRefresh" @change="toggleAutoRefresh" />
            <span>自动刷新</span>
          </label>
        </div>
      </div>

      <template v-if="currentTab !== 'login'">
        <div class="logs-body">
          <div v-for="(log, idx) in logs" :key="idx" class="log-entry">
            <span class="log-ts">{{ log.timestamp || '' }}</span>
            <span v-if="log.level" class="log-level" :class="'level-' + (log.level || '').toLowerCase()">{{ log.level }}</span>
            <span class="log-msg">{{ log.content || log.message || log.raw || JSON.stringify(log) }}</span>
          </div>
          <p v-if="!logs.length" class="empty-text">暂无日志</p>
        </div>
        <div class="logs-footer">
          <span>共 {{ total }} 条</span>
          <div class="page-btns">
            <button class="btn btn-secondary btn-sm" :disabled="page <= 1" @click="page--; loadLogs()">上一页</button>
            <span>{{ page }}</span>
            <button class="btn btn-secondary btn-sm" @click="page++; loadLogs()">下一页</button>
          </div>
        </div>
      </template>

      <template v-else>
        <div class="logs-body">
          <table class="login-table">
            <thead>
              <tr>
                <th>IP</th>
                <th>首次访问</th>
                <th>最近访问</th>
                <th>失败次数</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in loginLogs" :key="log.ip">
                <td class="mono">{{ log.ip }}</td>
                <td>{{ log.first_access?.slice(0, 19) }}</td>
                <td>{{ log.last_access?.slice(0, 19) }}</td>
                <td>{{ log.fail_count }}</td>
                <td>
                  <span class="badge" :class="log.is_banned ? 'badge-danger' : 'badge-success'">
                    {{ log.is_banned ? '已封禁' : '正常' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="!loginLogs.length" class="empty-text">暂无登录记录</p>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const currentTab = ref('message')
const logs = ref([])
const loginLogs = ref([])
const page = ref(1)
const total = ref(0)
const autoRefresh = ref(false)
let refreshTimer = null

const logTabs = [
  { key: 'message', label: '消息日志' },
  { key: 'framework', label: '框架日志' },
  { key: 'login', label: '登录日志' },
]

function switchTab(tab) {
  currentTab.value = tab
  page.value = 1
  loadLogs()
}

async function loadLogs() {
  if (currentTab.value === 'login') {
    const res = await store.fetchApi('/logs/login')
    if (res && res.success) {
      loginLogs.value = res.logs || []
    }
    return
  }

  const res = await store.fetchApi(`/logs/${currentTab.value}?page=${page.value}&limit=100`)
  if (res && res.success) {
    logs.value = res.data || []
    total.value = res.total || 0
  }
}

function toggleAutoRefresh() {
  if (refreshTimer) clearInterval(refreshTimer)
  if (autoRefresh.value) {
    refreshTimer = setInterval(loadLogs, 5000)
  }
}

// Listen for WS log pushes
function onWsMessage(e) {
  const msg = e.detail
  if (msg.type === 'new_log' && msg.data) {
    const logType = msg.data.log_type
    if (logType === currentTab.value && page.value === 1) {
      logs.value.unshift(msg.data)
      if (logs.value.length > 100) logs.value.pop()
    }
  }
}

onMounted(() => {
  loadLogs()
  window.addEventListener('ws-message', onWsMessage)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  window.removeEventListener('ws-message', onWsMessage)
})
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 22px; font-weight: 700; }
.subtitle { color: var(--color-text-muted); font-size: 13px; margin-top: 2px; }

.logs-container { padding: 0; overflow: hidden; display: flex; flex-direction: column; height: calc(100vh - 140px); }

.logs-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px; border-bottom: 1px solid var(--color-border-light); flex-shrink: 0;
}
.toolbar-right { display: flex; align-items: center; gap: 12px; }

.log-tabs { display: flex; gap: 2px; }
.log-tabs button {
  padding: 6px 12px; border: none; background: none; font-size: 13px;
  color: var(--color-text-muted); border-radius: 4px; cursor: pointer;
  font-family: inherit; transition: all var(--transition);
}
.log-tabs button.active { background: var(--color-primary-light); color: var(--color-primary); font-weight: 500; }
.log-tabs button:hover:not(.active) { background: var(--color-bg-tertiary); }

.auto-refresh { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--color-text-muted); cursor: pointer; }
.auto-refresh input { cursor: pointer; }

.btn-sm { font-size: 12px; padding: 4px 10px; }

.logs-body { flex: 1; overflow-y: auto; padding: 0; }

.log-entry {
  display: flex; gap: 8px; padding: 4px 16px; font-size: 12px;
  border-bottom: 1px solid var(--color-border-light); align-items: baseline;
  font-family: var(--font-mono); line-height: 1.6;
}
.log-entry:hover { background: var(--color-bg-secondary); }
.log-ts { color: var(--color-text-muted); flex-shrink: 0; font-size: 11px; }
.log-level { flex-shrink: 0; font-size: 11px; font-weight: 500; padding: 0 4px; border-radius: 2px; }
.level-error, .level-critical { color: var(--color-danger); background: #fee2e2; }
.level-warning { color: #92400e; background: #fef3c7; }
.level-info { color: #166534; background: #dcfce7; }
.level-debug { color: var(--color-text-muted); }
.log-msg { flex: 1; word-break: break-all; }

.logs-footer {
  padding: 8px 16px; border-top: 1px solid var(--color-border-light);
  display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
  font-size: 12px; color: var(--color-text-muted);
}
.page-btns { display: flex; align-items: center; gap: 8px; }

.login-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.login-table th {
  text-align: left; padding: 8px 16px; background: var(--color-bg-secondary);
  font-weight: 600; font-size: 12px; color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border);
}
.login-table td { padding: 8px 16px; border-bottom: 1px solid var(--color-border-light); }
.mono { font-family: var(--font-mono); font-size: 12px; }

.empty-text { color: var(--color-text-muted); font-size: 13px; text-align: center; padding: 40px; }
</style>
