<template>
  <div class="dashboard">
    <header class="page-header">
      <h1>仪表盘</h1>
      <p class="subtitle">系统运行状态概览</p>
    </header>

    <div class="stats-grid">
      <div class="stat-card card" v-for="stat in statCards" :key="stat.label">
        <div class="stat-icon" :style="{ background: stat.bg, color: stat.color }">
          <span v-html="stat.icon"></span>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ stat.value }}</span>
          <span class="stat-label">{{ stat.label }}</span>
        </div>
      </div>
    </div>

    <div class="main-row">
      <div class="sys-col">
        <!-- CPU -->
        <div class="card res-card">
          <div class="res-header">CPU</div>
          <div class="res-body">
            <div class="progress-ring">
              <svg viewBox="0 0 72 72">
                <circle cx="36" cy="36" r="30" fill="none" stroke="#e5e7eb" stroke-width="6"/>
                <circle cx="36" cy="36" r="30" fill="none" stroke="var(--color-primary)" stroke-width="6"
                  stroke-linecap="round"
                  :stroke-dasharray="188.5"
                  :stroke-dashoffset="188.5 - 188.5 * (info?.cpu_percent || 0) / 100"
                  transform="rotate(-90 36 36)"/>
              </svg>
              <span class="ring-text">{{ info?.cpu_percent || 0 }}%</span>
            </div>
            <div class="res-info">
              <span>{{ info?.cpu_cores || '-' }} 核</span>
              <span class="res-sub">{{ info?.cpu_model || '-' }}</span>
            </div>
          </div>
        </div>

        <!-- Memory -->
        <div class="card res-card">
          <div class="res-header">内存</div>
          <div class="res-body">
            <div class="progress-ring">
              <svg viewBox="0 0 72 72">
                <circle cx="36" cy="36" r="30" fill="none" stroke="#e5e7eb" stroke-width="6"/>
                <circle cx="36" cy="36" r="30" fill="none" stroke="var(--color-success)" stroke-width="6"
                  stroke-linecap="round"
                  :stroke-dasharray="188.5"
                  :stroke-dashoffset="188.5 - 188.5 * (info?.memory_percent || 0) / 100"
                  transform="rotate(-90 36 36)"/>
              </svg>
              <span class="ring-text">{{ info?.memory_percent || 0 }}%</span>
            </div>
            <div class="res-info">
              <span>{{ fmtMB(info?.memory_used) }} / {{ fmtMB(info?.memory_total) }}</span>
              <span class="res-sub">框架: {{ fmtMB(info?.framework_memory_total) }}</span>
            </div>
          </div>
        </div>

        <!-- Disk -->
        <div class="card res-card" v-if="info?.disk_info">
          <div class="res-header">磁盘</div>
          <div class="res-body">
            <div class="progress-ring">
              <svg viewBox="0 0 72 72">
                <circle cx="36" cy="36" r="30" fill="none" stroke="#e5e7eb" stroke-width="6"/>
                <circle cx="36" cy="36" r="30" fill="none" stroke="var(--color-warning)" stroke-width="6"
                  stroke-linecap="round"
                  :stroke-dasharray="188.5"
                  :stroke-dashoffset="188.5 - 188.5 * (info?.disk_info?.percent || 0) / 100"
                  transform="rotate(-90 36 36)"/>
              </svg>
              <span class="ring-text">{{ info?.disk_info?.percent || 0 }}%</span>
            </div>
            <div class="res-info">
              <span>{{ fmtBytes(info?.disk_info?.used) }} / {{ fmtBytes(info?.disk_info?.total) }}</span>
              <span class="res-sub">可用: {{ fmtBytes(info?.disk_info?.free) }}</span>
            </div>
          </div>
        </div>

        <!-- Uptime -->
        <div class="card res-card">
          <div class="res-header">运行信息</div>
          <div class="res-info-full">
            <div class="info-row"><span>框架运行</span><span>{{ fmtDuration(info?.uptime) }}</span></div>
            <div class="info-row"><span>系统运行</span><span>{{ fmtDuration(info?.system_uptime) }}</span></div>
            <div class="info-row"><span>启动时间</span><span>{{ info?.start_time || '-' }}</span></div>
            <div class="info-row"><span>平台</span><span>{{ info?.platform || '-' }}</span></div>
            <div class="info-row"><span>Python</span><span>{{ info?.python_version || '-' }}</span></div>
          </div>
        </div>
      </div>

      <!-- Bots -->
      <div class="bots-col">
        <div class="card bots-card">
          <div class="res-header">Bot 连接</div>
          <div v-if="store.bots.length" class="bot-list">
            <div v-for="bot in store.bots" :key="bot.self_id" class="bot-row">
              <div class="bot-avatar">{{ (bot.name || 'B')[0] }}</div>
              <div class="bot-info">
                <span class="bot-name">{{ bot.name || `Bot ${bot.self_id}` }}</span>
                <span class="bot-id">ID: {{ bot.self_id || bot.appid }}</span>
              </div>
              <span class="badge badge-success">{{ bot.status || 'online' }}</span>
            </div>
          </div>
          <p v-else class="empty-text">暂无 Bot 连接</p>
        </div>

        <!-- Recent messages -->
        <div class="card bots-card">
          <div class="res-header">最近消息</div>
          <div v-if="recentMessages.length" class="msg-list">
            <div v-for="msg in recentMessages" :key="msg.id" class="msg-row">
              <span class="msg-time">{{ (msg.timestamp || '').slice(11, 16) }}</span>
              <span class="msg-sender">{{ msg.user_id }}</span>
              <span class="msg-content">{{ msg.content }}</span>
            </div>
          </div>
          <p v-else class="empty-text">暂无消息</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const info = computed(() => store.systemInfo)
const recentMessages = ref([])
let timer = null

const statCards = computed(() => {
  const s = info.value || {}
  return [
    { label: '今日消息', value: s.today_messages || 0, bg: '#eef0ff', color: 'var(--color-primary)', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>' },
    { label: 'Bot 连接', value: s.bot_count || 0, bg: '#dcfce7', color: '#166534', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>' },
    { label: '插件', value: s.plugin_count || 0, bg: '#fef3c7', color: '#92400e', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>' },
    { label: '模块', value: s.module_count || 0, bg: '#ede9fe', color: '#5b21b6', icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="2"/><path d="M7 2v20M17 2v20M2 12h20"/></svg>' },
  ]
})

function fmtMB(mb) {
  if (!mb && mb !== 0) return '-'
  if (mb > 1024) return (mb / 1024).toFixed(1) + ' GB'
  return Math.round(mb) + ' MB'
}

function fmtBytes(bytes) {
  if (!bytes) return '-'
  const gb = bytes / (1024 ** 3)
  if (gb >= 1) return gb.toFixed(1) + ' GB'
  return (bytes / (1024 ** 2)).toFixed(0) + ' MB'
}

function fmtDuration(seconds) {
  if (!seconds && seconds !== 0) return '-'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}天 ${h}时 ${m}分`
  if (h > 0) return `${h}时 ${m}分`
  return `${m}分`
}

async function loadRecent() {
  const res = await store.fetchApi('/messages/recent')
  if (res && res.success) {
    recentMessages.value = (res.data || []).slice(0, 10)
  }
}

onMounted(() => {
  store.loadSystemInfo()
  store.fetchBots()
  loadRecent()
  timer = setInterval(() => {
    store.loadSystemInfo()
    store.fetchBots()
  }, 10000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.page-header { margin-bottom: 20px; }
.page-header h1 { font-size: 22px; font-weight: 700; }
.subtitle { color: var(--color-text-muted); font-size: 13px; margin-top: 2px; }

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card { padding: 16px; display: flex; align-items: center; gap: 12px; }
.stat-icon {
  width: 40px; height: 40px; border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.stat-content { display: flex; flex-direction: column; }
.stat-value { font-size: 20px; font-weight: 700; line-height: 1.2; }
.stat-label { font-size: 12px; color: var(--color-text-muted); }

.main-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.sys-col, .bots-col { display: flex; flex-direction: column; gap: 12px; }

.res-card { padding: 16px; }
.res-header { font-size: 14px; font-weight: 600; margin-bottom: 12px; color: var(--color-text); }
.res-body { display: flex; align-items: center; gap: 16px; }
.res-sub { font-size: 11px; color: var(--color-text-muted); display: block; margin-top: 2px; }

.progress-ring { position: relative; width: 72px; height: 72px; flex-shrink: 0; }
.progress-ring svg { width: 100%; height: 100%; }
.ring-text {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 600;
}
.res-info { font-size: 13px; }

.res-info-full { display: flex; flex-direction: column; gap: 6px; }
.info-row {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 13px; padding: 2px 0;
}
.info-row span:first-child { color: var(--color-text-muted); }
.info-row span:last-child { font-weight: 500; }

.bots-card { padding: 16px; }
.bot-list { display: flex; flex-direction: column; gap: 8px; }
.bot-row {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; background: var(--color-bg-secondary); border-radius: var(--radius-sm);
}
.bot-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), #7c3aed);
  color: white; display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 600; flex-shrink: 0;
}
.bot-info { flex: 1; display: flex; flex-direction: column; }
.bot-name { font-size: 13px; font-weight: 600; }
.bot-id { font-size: 11px; color: var(--color-text-muted); font-family: var(--font-mono); }

.msg-list { display: flex; flex-direction: column; gap: 4px; max-height: 300px; overflow-y: auto; }
.msg-row { display: flex; gap: 8px; font-size: 12px; padding: 4px 0; border-bottom: 1px solid var(--color-border-light); }
.msg-time { color: var(--color-text-muted); flex-shrink: 0; font-family: var(--font-mono); }
.msg-sender { color: var(--color-primary); flex-shrink: 0; max-width: 80px; overflow: hidden; text-overflow: ellipsis; }
.msg-content { color: var(--color-text); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.empty-text { color: var(--color-text-muted); font-size: 13px; text-align: center; padding: 20px; }

@media (max-width: 900px) {
  .main-row { grid-template-columns: 1fr; }
}
</style>
