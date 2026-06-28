<template>
  <div class="log-page">
    <div class="log-toolbar">
      <div class="log-tabs">
        <button class="tab-btn" :class="{ active: activeTab === 'message' }" @click="activeTab = 'message'; loadLogs()">消息日志</button>
        <button class="tab-btn" :class="{ active: activeTab === 'framework' }" @click="activeTab = 'framework'; loadLogs()">框架日志</button>
        <button class="tab-btn" :class="{ active: activeTab === 'login' }" @click="activeTab = 'login'; loadLoginLogs()">登录日志</button>
      </div>
      <div class="log-actions">
        <label class="auto-label">
          <input type="checkbox" v-model="autoRefresh" /> 自动刷新
        </label>
        <button class="tool-btn" @click="loadLogs">刷新</button>
      </div>
    </div>

    <!-- Terminal-style log display -->
    <div class="terminal" v-if="activeTab !== 'login'">
      <div v-if="!logs.length" class="term-empty">暂无日志</div>
      <div v-for="(entry, idx) in logs" :key="idx" class="term-line">
        <span class="t-time">{{ entry.time || '' }}</span>
        <span class="t-content">{{ entry.message || entry.content || '' }}</span>
      </div>
    </div>

    <!-- Login logs table -->
    <div class="login-table-wrap" v-else>
      <table class="login-table" v-if="loginLogs.length">
        <thead>
          <tr>
            <th>IP</th>
            <th>首次访问</th>
            <th>最后访问</th>
            <th>失败次数</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="log in loginLogs" :key="log.ip">
            <td>{{ log.ip }}</td>
            <td>{{ log.first_access }}</td>
            <td>{{ log.last_access }}</td>
            <td>{{ log.fail_count }}</td>
            <td>
              <span class="status-badge" :class="log.is_banned ? 'banned' : 'normal'">
                {{ log.is_banned ? '已封禁' : '正常' }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
      <div v-else class="term-empty">暂无登录记录</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const activeTab = ref('message')
const logs = ref([])
const loginLogs = ref([])
const autoRefresh = ref(false)
let timer = null

async function loadLogs() {
  const res = await store.fetchApi(`/logs/${activeTab.value}?page=1&limit=200`)
  if (res && res.success) {
    logs.value = res.data || []
  }
}

async function loadLoginLogs() {
  const res = await store.fetchApi('/logs/login')
  if (res && res.success) {
    loginLogs.value = res.logs || []
  }
}

function onWsMessage(e) {
  const msg = e.detail
  if (msg && msg.type === 'log' && msg.data) {
    logs.value.unshift(msg.data)
    if (logs.value.length > 500) logs.value.pop()
  }
}

watch(autoRefresh, (val) => {
  if (val) {
    timer = setInterval(() => { if (activeTab.value !== 'login') loadLogs() }, 5000)
  } else {
    clearInterval(timer)
    timer = null
  }
})

onMounted(() => {
  loadLogs()
  window.addEventListener('ws-message', onWsMessage)
})

onUnmounted(() => {
  clearInterval(timer)
  window.removeEventListener('ws-message', onWsMessage)
})
</script>

<style scoped>
.log-page { display: flex; flex-direction: column; height: calc(100vh - 100px); }
.log-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px; flex-wrap: wrap; gap: 8px;
}
.log-tabs { display: flex; gap: 2px; }
.tab-btn {
  padding: 5px 14px; border: 1px solid var(--border); border-radius: 4px;
  background: transparent; color: var(--text2); cursor: pointer; font-size: 13px;
}
.tab-btn:hover { color: var(--text); border-color: var(--text3); }
.tab-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); }

.log-actions { display: flex; align-items: center; gap: 10px; }
.auto-label { color: var(--text2); font-size: 12px; cursor: pointer; display: flex; align-items: center; gap: 4px; }
.auto-label input { accent-color: var(--accent); }
.tool-btn {
  padding: 4px 10px; border: 1px solid var(--border); border-radius: 4px;
  background: transparent; color: var(--text2); cursor: pointer; font-size: 12px;
}
.tool-btn:hover { color: var(--text); border-color: var(--text3); }

.terminal {
  flex: 1; min-height: 0; overflow-y: auto;
  background: var(--bg3); border: 1px solid var(--border); border-radius: 6px;
  font-family: var(--font-mono); font-size: 13px; line-height: 1.7; padding: 6px 0;
}
.term-empty { color: var(--text3); text-align: center; padding: 40px 0; }
.term-line { padding: 1px 12px; white-space: pre-wrap; word-break: break-all; }
.term-line:hover { background: rgba(88, 101, 242, 0.04); }
.t-time { color: var(--text3); margin-right: 6px; }
.t-content { color: var(--text); }

.login-table-wrap { flex: 1; overflow-y: auto; }
.login-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
}
.login-table th {
  text-align: left; padding: 8px 12px; background: var(--bg3);
  border-bottom: 1px solid var(--border); color: var(--text2); font-weight: 600; font-size: 12px;
}
.login-table td { padding: 8px 12px; border-bottom: 1px solid var(--border); color: var(--text); }
.status-badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; }
.status-badge.normal { background: #dcfce7; color: #166534; }
.status-badge.banned { background: #fee2e2; color: #991b1b; }
</style>
