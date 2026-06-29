<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { Line } from 'vue-chartjs'
import { Chart, CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend } from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import { useAppStore } from '../stores/app'
import { on, off } from '../utils/ws'
import axios from '../utils/axios'
import SvgIcon from '../components/SvgIcon.vue'

Chart.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend, ChartDataLabels)

const app = useAppStore()
const sys = computed(() => app.systemInfo || {})
const todayHourly = ref([])
const yesterdayHourly = ref([])
const chartLoading = ref(true)

const statCards = computed(() => {
  const s = sys.value
  const u = s?.total_users ?? 0, au = s?.today_active ?? 0
  const g = s?.total_groups ?? 0, ag = s?.active_groups ?? 0
  return [
    { label: '今日消息', value: s?.today_messages ?? 0, icon: 'chatbubbles', color: 'c-blue' },
    { label: '插件处理器', value: s?.plugins_count ?? 0, icon: 'extension-puzzle', color: 'c-purple' },
    { label: '全部用户', value: `${u} (${au})`, icon: 'people', color: 'c-green' },
    { label: '全部群聊', value: `${g} (${ag})`, icon: 'group', color: 'c-orange' },
  ]
})

const ringColor = (v) => !v ? 'var(--accent)' : v > 90 ? 'var(--danger)' : v > 70 ? 'var(--warning)' : 'var(--success)'
const fmtMem = (v) => !v ? '-' : v > 1024 ? `${(v / 1024).toFixed(1)} GB` : `${Math.round(v)} MB`
const fmtBytes = (v) => { if (!v) return '-'; const g = v / 1024 ** 3; return g >= 1 ? `${g.toFixed(1)} GB` : `${(v / 1024 ** 2).toFixed(0)} MB` }
function fmtUptime(s) {
  if (!s) return '-'
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60)
  return d > 0 ? `${d}天${h}时${m}分` : h > 0 ? `${h}时${m}分` : `${m}分`
}

const chartComputed = computed(() => {
  const hr = new Date().getHours()
  const t = todayHourly.value.length === 24 ? todayHourly.value : Array(24).fill(0)
  const y = yesterdayHourly.value.length === 24 ? yesterdayHourly.value : Array(24).fill(0)
  const labels = [], data = []
  for (let x = 11; x >= 0; x--) {
    const c = (hr - x + 24) % 24, n = (c + 1) % 24
    labels.push(`${c}:00-${n}:00`)
    data.push(hr - x < 0 ? (y[c] || 0) : (t[c] || 0))
  }
  return { labels, data }
})

const chartDataset = computed(() => ({
  labels: chartComputed.value.labels,
  datasets: [{
    label: '消息数', data: chartComputed.value.data,
    borderColor: '#58a6ff', backgroundColor: 'rgba(88,166,255,0.1)',
    borderWidth: 2, pointRadius: 4, pointHoverRadius: 6,
    pointBackgroundColor: '#58a6ff', tension: 0.3, fill: true,
  }],
}))

const hasChart = computed(() => chartComputed.value.data.some(v => Number(v) > 0))

const chartOptions = {
  responsive: true, maintainAspectRatio: false,
  plugins: {
    legend: { display: false }, tooltip: { mode: 'index', intersect: false },
    datalabels: { color: '#58a6ff', font: { size: 10, weight: 600 }, anchor: 'end', align: 'top', offset: 2, formatter: v => v > 0 ? v : '' },
  },
  scales: {
    x: { grid: { color: 'rgba(128,128,128,.15)' }, ticks: { color: '#8b949e', font: { size: 10 }, maxRotation: 45, minRotation: 30 } },
    y: { beginAtZero: true, grid: { color: 'rgba(128,128,128,.15)' }, ticks: { color: '#8b949e', font: { size: 11 }, precision: 0 } },
  },
}

async function fetchChart() {
  chartLoading.value = true
  try {
    const bot_qq = app.currentBotId || ''
    const data = (await axios.get(`/api/statistics/hourly?bot_qq=${bot_qq}`)).data?.data || {}
    if (data.today_hourly_distribution?.length) todayHourly.value = data.today_hourly_distribution
    if (data.yesterday_hourly_distribution?.length) { yesterdayHourly.value = data.yesterday_hourly_distribution }
  } catch {
    todayHourly.value = []
    yesterdayHourly.value = []
  } finally {
    chartLoading.value = false
  }
}

function onSysInfo(data) { app.systemInfo = data }
let timer
onMounted(() => { on('system_info', onSysInfo); timer = setInterval(() => app.fetchSystemInfo(), 10000); fetchChart() })
onUnmounted(() => { off('system_info', onSysInfo); clearInterval(timer) })
</script>

<template>
  <div class="dash">
    <div class="banner">
      <h2>Elaina 管理面板</h2>
      <p>运行 {{ fmtUptime(sys?.uptime) }} · {{ sys?.system_version || '' }}</p>
    </div>

    <div class="ui-stat-grid stat-grid">
      <div v-for="s in statCards" :key="s.label" :class="['ui-stat', s.color]">
        <div class="ui-stat-top">
          <div class="ui-stat-ic"><SvgIcon :name="s.icon" :size="17" /></div>
          <div class="ui-stat-label">{{ s.label }}</div>
        </div>
        <div class="ui-stat-val">{{ s.value }}</div>
      </div>
    </div>

    <div class="main-row">
      <div class="sys-col">
        <!-- CPU -->
        <div class="res-card">
          <div class="res-header"><span :title="sys?.cpu_model || ''">CPU</span></div>
          <div class="res-body">
            <div class="progress-ring">
              <svg viewBox="0 0 72 72">
                <circle cx="36" cy="36" r="30" fill="none" stroke="var(--border)" stroke-width="5" />
                <circle cx="36" cy="36" r="30" fill="none" :stroke="ringColor(sys?.cpu_percent)" stroke-width="5" stroke-linecap="round" :stroke-dasharray="188.5" :stroke-dashoffset="188.5 - 188.5 * (sys?.cpu_percent || 0) / 100" transform="rotate(-90 36 36)" />
              </svg>
              <span class="ring-text">{{ Math.round(sys?.cpu_percent || 0) }}%</span>
            </div>
            <div class="res-info">
              <div>系统 <b>{{ (sys?.cpu_percent || 0).toFixed(1) }}%</b></div>
              <div>框架 <b>{{ (sys?.framework_cpu_percent || 0).toFixed(1) }}%</b></div>
              <div>核心 <b>{{ sys?.cpu_cores || '-' }}</b></div>
            </div>
          </div>
        </div>

        <!-- Memory -->
        <div class="res-card">
          <div class="res-header"><span>内存</span><span class="res-sub">{{ fmtMem(sys?.memory_total) }}</span></div>
          <div class="res-body">
            <div class="progress-ring">
              <svg viewBox="0 0 72 72">
                <circle cx="36" cy="36" r="30" fill="none" stroke="var(--border)" stroke-width="5" />
                <circle cx="36" cy="36" r="30" fill="none" :stroke="ringColor(sys?.memory_percent)" stroke-width="5" stroke-linecap="round" :stroke-dasharray="188.5" :stroke-dashoffset="188.5 - 188.5 * (sys?.memory_percent || 0) / 100" transform="rotate(-90 36 36)" />
              </svg>
              <span class="ring-text">{{ Math.round(sys?.memory_percent || 0) }}%</span>
            </div>
            <div class="res-info">
              <div>系统 <b>{{ (sys?.memory_percent || 0).toFixed(1) }}%</b> · {{ fmtMem(sys?.memory_used) }}</div>
              <div>框架 <b>{{ (sys?.framework_memory_percent || 0).toFixed(1) }}%</b> · {{ (sys?.framework_memory_total || 0).toFixed(1) }} MB</div>
            </div>
          </div>
        </div>

        <!-- Disk -->
        <div class="res-card">
          <div class="res-header"><span>磁盘</span></div>
          <div v-if="sys?.disk_info" class="res-body">
            <div class="progress-ring">
              <svg viewBox="0 0 72 72">
                <circle cx="36" cy="36" r="30" fill="none" stroke="var(--border)" stroke-width="5" />
                <circle cx="36" cy="36" r="30" fill="none" :stroke="ringColor(sys?.disk_info?.percent)" stroke-width="5" stroke-linecap="round" :stroke-dasharray="188.5" :stroke-dashoffset="188.5 - 188.5 * (sys?.disk_info?.percent || 0) / 100" transform="rotate(-90 36 36)" />
              </svg>
              <span class="ring-text">{{ Math.round(sys?.disk_info?.percent || 0) }}%</span>
            </div>
            <div class="res-info">
              <div>总计 <b>{{ fmtBytes(sys.disk_info.total) }}</b></div>
              <div>已用 <b>{{ fmtBytes(sys.disk_info.used) }}</b> ({{ sys.disk_info.percent }}%)</div>
              <div>可用 <b>{{ fmtBytes(sys.disk_info.free) }}</b></div>
            </div>
          </div>
        </div>

        <!-- Runtime -->
        <div class="res-card">
          <div class="res-header"><span>运行状态</span></div>
          <div class="res-info-full">
            <div>启动时间 <b>{{ sys?.start_time || '-' }}</b></div>
            <div>框架运行 <b>{{ fmtUptime(sys?.uptime) }}</b></div>
            <div>系统运行 <b>{{ fmtUptime(sys?.system_uptime) }}</b></div>
          </div>
        </div>
      </div>

      <div class="chart-col">
        <div class="res-card chart-card">
          <div class="res-header"><span>最近 12 小时消息分布</span></div>
          <div class="chart-wrap">
            <Line v-if="hasChart" :data="chartDataset" :options="chartOptions" :plugins="[ChartDataLabels]" />
            <div v-else class="chart-empty">{{ chartLoading ? '等待加载...' : '暂无消息' }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dash {
  width:100%
}
.banner {
  background:linear-gradient(135deg,var(--accent),var(--accent-light));
  border-radius:12px;
  padding:24px 28px;
  margin-bottom:20px
}
.banner h2 {
  color:#fff;
  font-size:20px;
  font-weight:700;
  margin:0 0 4px
}
.banner p {
  color:#ffffffb3;
  font-size:13px;
  margin:0
}
.stat-grid {
  grid-template-columns:repeat(4,1fr)
}
.main-row {
  display:flex;
  gap:12px;
  align-items:start
}
.sys-col {
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:12px;
  width:520px;
  flex-shrink:0
}
.chart-col {
  flex:1;
  min-width:0
}
.res-card {
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:var(--radius);
  box-shadow:var(--shadow-sm);
  padding:18px
}
.res-header {
  display:flex;
  justify-content:space-between;
  align-items:center;
  margin-bottom:12px
}
.res-header span:first-child {
  color:var(--text);
  font-weight:600;
  font-size:14px
}
.res-sub {
  color:var(--text3);
  font-size:11px;
  max-width:60%;
  text-align:right;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap
}
.res-body {
  display:flex;
  align-items:center;
  gap:12px
}
.progress-ring {
  position:relative;
  width:56px;
  height:56px;
  flex-shrink:0
}
.progress-ring svg {
  width:100%;
  height:100%
}
.ring-text {
  position:absolute;
  top:0;
  right:0;
  bottom:0;
  left:0;
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:11px;
  font-weight:600;
  color:var(--text)
}
.res-info {
  font-size:12px;
  color:var(--text2);
  line-height:1.7
}
.res-info b {
  color:var(--text)
}
.res-info-full {
  font-size:13px;
  color:var(--text2);
  line-height:2
}
.res-info-full b {
  color:var(--text)
}
.chart-card {
  display:flex;
  flex-direction:column
}
.chart-wrap {
  min-height:280px;
  position:relative
}
.chart-empty {
  color:var(--text3);
  text-align:center;
  padding-top:80px;
  font-size:13px
}
@media(max-width:767px) {
  .stat-grid {
  grid-template-columns:repeat(2,1fr)
}
.main-row {
  flex-direction:column
}
.sys-col {
  width:100%;
  grid-template-columns:1fr 1fr
}
.chart-wrap {
  min-height:200px
}
.banner {
  padding:16px 18px
}
.banner h2 {
  font-size:17px
}
}
@media(max-width:400px) {
  .sys-col {
  grid-template-columns:1fr
}
.stat-grid {
  gap:8px
}
}
</style>
