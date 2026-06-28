<template>
  <div class="dash">
    <!-- Banner -->
    <div class="banner">
      <h2>{{ frameworkName }} 管理面板</h2>
      <p>运行时长: {{ uptimeStr }} | {{ platformStr }}</p>
    </div>

    <!-- Stat Grid (4 columns) -->
    <div class="stat-grid">
      <div class="stat-card" v-for="s in stats" :key="s.label">
        <div class="stat-icon">
          <SvgIcon :name="s.icon" :size="22" :color="s.color" />
        </div>
        <div class="stat-value">{{ s.value }}</div>
        <div class="stat-label">{{ s.label }}</div>
      </div>
    </div>

    <!-- Main Row: sys-col (2x2) + chart-col -->
    <div class="main-row">
      <div class="sys-col">
        <!-- CPU -->
        <div class="res-card">
          <div class="res-header">
            <span>CPU</span>
            <span class="res-sub" :title="info.cpu_model || ''">{{ info.cpu_model || '-' }}</span>
          </div>
          <div class="res-body">
            <div class="progress-ring">
              <svg viewBox="0 0 72 72">
                <circle cx="36" cy="36" r="28" stroke="var(--border)" stroke-width="6" fill="none"/>
                <circle cx="36" cy="36" r="28" :stroke="ringColor(info.cpu_percent)" stroke-width="6" fill="none"
                  stroke-linecap="round" :stroke-dasharray="175.93" :stroke-dashoffset="175.93 - (175.93 * (info.cpu_percent||0) / 100)"
                  style="transform: rotate(-90deg); transform-origin: center;" />
              </svg>
              <span class="ring-text">{{ info.cpu_percent || 0 }}%</span>
            </div>
            <div class="res-info">
              <div>核心: <b>{{ info.cpu_cores || '-' }}</b></div>
            </div>
          </div>
        </div>

        <!-- Memory -->
        <div class="res-card">
          <div class="res-header">
            <span>内存</span>
            <span class="res-sub">{{ info.memory_used || '-' }} / {{ info.memory_total || '-' }}</span>
          </div>
          <div class="res-body">
            <div class="progress-ring">
              <svg viewBox="0 0 72 72">
                <circle cx="36" cy="36" r="28" stroke="var(--border)" stroke-width="6" fill="none"/>
                <circle cx="36" cy="36" r="28" :stroke="ringColor(info.memory_percent)" stroke-width="6" fill="none"
                  stroke-linecap="round" :stroke-dasharray="175.93" :stroke-dashoffset="175.93 - (175.93 * (info.memory_percent||0) / 100)"
                  style="transform: rotate(-90deg); transform-origin: center;" />
              </svg>
              <span class="ring-text">{{ info.memory_percent || 0 }}%</span>
            </div>
            <div class="res-info">
              <div>使用率: <b>{{ info.memory_percent || 0 }}%</b></div>
            </div>
          </div>
        </div>

        <!-- Disk -->
        <div class="res-card">
          <div class="res-header">
            <span>磁盘</span>
            <span class="res-sub">{{ diskUsed }} / {{ diskTotal }}</span>
          </div>
          <div class="res-body" v-if="diskPercent >= 0">
            <div class="progress-ring">
              <svg viewBox="0 0 72 72">
                <circle cx="36" cy="36" r="28" stroke="var(--border)" stroke-width="6" fill="none"/>
                <circle cx="36" cy="36" r="28" :stroke="ringColor(diskPercent)" stroke-width="6" fill="none"
                  stroke-linecap="round" :stroke-dasharray="175.93" :stroke-dashoffset="175.93 - (175.93 * diskPercent / 100)"
                  style="transform: rotate(-90deg); transform-origin: center;" />
              </svg>
              <span class="ring-text">{{ diskPercent }}%</span>
            </div>
            <div class="res-info">
              <div>可用: <b>{{ diskFree }}</b></div>
            </div>
          </div>
        </div>

        <!-- Uptime -->
        <div class="res-card">
          <div class="res-header"><span>运行信息</span></div>
          <div class="res-info-full">
            <div>框架运行: <b>{{ uptimeStr }}</b></div>
            <div>系统运行: <b>{{ fmtUptime(info.system_uptime) }}</b></div>
            <div>启动时间: <b>{{ info.start_time || '-' }}</b></div>
            <div>Python: <b>{{ info.python_version || '-' }}</b></div>
          </div>
        </div>
      </div>

      <!-- Chart Column: hourly distribution -->
      <div class="chart-col">
        <div class="res-card chart-card">
          <div class="res-header"><span>24小时消息分布</span></div>
          <div class="chart-wrap">
            <div class="bar-chart" v-if="hourlyData.length">
              <div class="bar-item" v-for="(count, idx) in hourlyData" :key="idx">
                <div class="bar-fill" :style="{ height: barHeight(count) + '%' }"></div>
                <span class="bar-label">{{ idx }}</span>
              </div>
            </div>
            <div class="chart-empty" v-else>暂无数据</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import SvgIcon from '../components/SvgIcon.vue'

const store = useAppStore()
const hourlyData = ref([])

const info = computed(() => store.systemInfo || {})
const frameworkName = computed(() => info.value.framework_name || 'Elaina')
const platformStr = computed(() => info.value.platform || '-')
const uptimeStr = computed(() => {
  const s = info.value.uptime
  if (!s && s !== 0) return '-'
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}天${h}时${m}分`
  if (h > 0) return `${h}时${m}分`
  return `${m}分`
})

const diskInfo = computed(() => info.value.disk_info || {})
function fmtBytes(bytes) {
  if (!bytes) return '-'
  const gb = bytes / (1024 ** 3)
  return gb >= 1 ? gb.toFixed(1) + ' GB' : (bytes / (1024 ** 2)).toFixed(0) + ' MB'
}
const diskUsed = computed(() => fmtBytes(diskInfo.value.used))
const diskTotal = computed(() => fmtBytes(diskInfo.value.total))
const diskFree = computed(() => fmtBytes(diskInfo.value.free))
const diskPercent = computed(() => diskInfo.value.percent ?? -1)

const stats = computed(() => [
  { label: '今日消息', value: info.value.today_messages || 0, icon: 'chatbubbles', color: 'var(--accent)' },
  { label: '机器人', value: info.value.bot_count || 0, icon: 'server', color: 'var(--success)' },
  { label: '插件', value: info.value.plugin_count || 0, icon: 'extension-puzzle', color: 'var(--warning)' },
  { label: '模块', value: info.value.module_count || 0, icon: 'cog', color: 'var(--info)' },
])

function fmtUptime(s) {
  if (!s && s !== 0) return '-'
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}天${h}时${m}分`
  if (h > 0) return `${h}时${m}分`
  return `${m}分`
}

function ringColor(percent) {
  if (percent > 80) return 'var(--danger)'
  if (percent > 60) return 'var(--warning)'
  return 'var(--accent)'
}

function barHeight(count) {
  const max = Math.max(...hourlyData.value, 1)
  return max > 0 ? (count / max) * 100 : 0
}

async function loadHourly() {
  const res = await store.fetchApi('/statistics')
  if (res && res.success) {
    hourlyData.value = res.hourly || []
  }
}

onMounted(() => {
  loadHourly()
})
</script>

<style scoped>
.dash { width: 100%; }

.banner {
  background: linear-gradient(135deg, var(--accent), var(--accent-light));
  border-radius: 12px;
  padding: 24px 28px;
  margin-bottom: 20px;
}
.banner h2 { color: #fff; font-size: 20px; font-weight: 700; margin: 0 0 4px; }
.banner p { color: rgba(255,255,255,0.7); font-size: 13px; margin: 0; }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  text-align: center;
}
.stat-icon { margin: 0 auto 10px; display: flex; align-items: center; justify-content: center; }
.stat-value { color: var(--text); font-size: 24px; font-weight: 700; }
.stat-label { color: var(--text2); font-size: 12px; margin-top: 2px; }

.main-row { display: flex; gap: 12px; align-items: start; }
.sys-col { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; width: 520px; flex-shrink: 0; }
.chart-col { flex: 1; min-width: 0; }

.res-card {
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
}
.res-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.res-header span:first-child { color: var(--text); font-weight: 600; font-size: 14px; }
.res-sub {
  color: var(--text3);
  font-size: 11px;
  max-width: 60%;
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.res-body { display: flex; align-items: center; gap: 12px; }
.progress-ring { position: relative; width: 56px; height: 56px; flex-shrink: 0; }
.progress-ring svg { width: 100%; height: 100%; }
.ring-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  color: var(--text);
}
.res-info { font-size: 12px; color: var(--text2); line-height: 1.7; }
.res-info b { color: var(--text); }
.res-info-full { font-size: 12px; color: var(--text2); line-height: 1.9; }
.res-info-full b { color: var(--text); }

.chart-card { height: 100%; display: flex; flex-direction: column; }
.chart-wrap { flex: 1; min-height: 200px; display: flex; align-items: flex-end; }
.chart-empty { color: var(--text3); text-align: center; width: 100%; padding: 40px 0; font-size: 13px; }

.bar-chart {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  width: 100%;
  height: 160px;
  padding-top: 8px;
}
.bar-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  justify-content: flex-end;
}
.bar-fill {
  width: 100%;
  max-width: 20px;
  background: linear-gradient(180deg, var(--accent), var(--accent-light));
  border-radius: 3px 3px 0 0;
  min-height: 2px;
  transition: height 0.3s;
}
.bar-label { font-size: 10px; color: var(--text3); margin-top: 4px; }
</style>
