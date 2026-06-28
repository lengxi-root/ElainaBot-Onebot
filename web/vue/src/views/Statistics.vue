<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Chart, Filler, LineElement, PointElement, BarElement, CategoryScale, LinearScale, Legend, Tooltip, BarController, LineController } from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import { Line, Bar } from 'vue-chartjs'
import { useAppStore } from '../stores/app'
import axios from '../utils/axios'

Chart.register(Filler, LineElement, PointElement, BarElement, CategoryScale, LinearScale, Legend, Tooltip, BarController, LineController, ChartDataLabels)

const app = useAppStore()
const loading = ref(false)
const days = ref(7)
const chartData = ref(null)
const hasChart = ref(false)
const chartTab = ref('msg')
const TABS = [{ key: 'msg', label: '消息统计' }, { key: 'active', label: '活跃统计' }, { key: 'event', label: '事件统计' }]

// 拆分数据源 — 各接口独立加载, 先返回先渲染
const summary = ref({})
const active = ref({})
const top = ref({})
const events = ref({})
const totals = ref({})
const hourly = ref([])

const topGroups = computed(() => top.value?.top_groups || [])
const topUsers = computed(() => top.value?.top_users || [])
const topCmds = computed(() => top.value?.top_commands || [])

const overviewCards = computed(() => {
  const c = chartData.value
  return [
    { tab: 'msg', label: '今日消息', value: summary.value.total_messages ?? 0 },
    { tab: 'msg', label: '私聊消息', value: summary.value.private_messages ?? 0 },
    { tab: 'msg', label: '群聊消息', value: (summary.value.total_messages ?? 0) - (summary.value.private_messages ?? 0) },
    { tab: 'active', label: '活跃用户', value: active.value.active_users ?? 0 },
    { tab: 'active', label: '活跃群聊', value: active.value.active_groups ?? 0 },
    { tab: 'total', label: '总用户数', value: totals.value.total_users ?? 0 },
    { tab: 'total', label: '总群组数', value: totals.value.total_groups ?? 0 },
    { tab: 'total', label: '总好友数', value: c?.total_friends ?? 0 },
    { tab: 'event', label: '进群', value: events.value.group_join_count ?? 0 },
    { tab: 'event', label: '退群', value: events.value.group_leave_count ?? 0 },
    { tab: 'event', label: '加好友', value: events.value.friend_add_count ?? 0 },
    { tab: 'event', label: '删好友', value: events.value.friend_remove_count ?? 0 },
  ]
})

const C = { blue: { b: '#58a6ff', bg: 'rgba(88,166,255,0.08)' }, green: { b: '#3fb950', bg: 'rgba(63,185,80,0.08)' }, yellow: { b: '#d29922', bg: 'rgba(210,153,34,0.08)' }, red: { b: '#f85149', bg: 'rgba(248,81,73,0.08)' } }
function ds(label, data, color) { return { label, data, borderColor: color.b, backgroundColor: color.bg, fill: true, tension: 0.35, pointRadius: 3, borderWidth: 2 } }

const lineData = computed(() => {
  const d = chartData.value; if (!d) return { labels: [], datasets: [] }
  const labels = d.labels
  if (chartTab.value === 'msg') return { labels, datasets: [ds('总消息量', d.msg_total, C.blue), ds('私聊消息', d.msg_private, C.green), ds('群聊消息', d.msg_group, C.yellow)] }
  if (chartTab.value === 'active') return { labels, datasets: [ds('活跃用户', d.active_users, C.blue), ds('活跃群聊', d.active_groups, C.green)] }
  return { labels, datasets: [ds('进群', d.ev_group_join, C.green), ds('退群', d.ev_group_leave, C.red), ds('加好友', d.ev_friend_add, C.blue), ds('删好友', d.ev_friend_remove, C.yellow)] }
})

const barData = computed(() => ({ labels: Array.from({ length: 24 }, (_, i) => `${i}:00`), datasets: [{ label: '消息数', data: hourly.value, backgroundColor: 'rgba(88,166,255,0.45)', borderColor: '#58a6ff', borderWidth: 1 }] }))

const lineOpts = { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, plugins: { legend: { labels: { color: '#8b949e', font: { size: 12 }, usePointStyle: true, pointStyle: 'circle' } }, tooltip: { mode: 'index', intersect: false }, datalabels: { color: '#8b949e', font: { size: 10, weight: 600 }, anchor: 'end', align: 'top', offset: 2, formatter: v => v > 0 ? v : '' } }, scales: { x: { ticks: { color: '#484f58' }, grid: { color: 'rgba(48,54,61,0.6)' } }, y: { beginAtZero: true, ticks: { color: '#484f58', precision: 0 }, grid: { color: 'rgba(48,54,61,0.6)' } } } }
const barOpts = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false }, datalabels: { display: false } }, scales: { x: { ticks: { color: '#484f58', maxRotation: 0 }, grid: { display: false } }, y: { beginAtZero: true, ticks: { color: '#484f58', precision: 0 }, grid: { color: 'rgba(48,54,61,0.6)' } } } }

async function fetchStats() {
  const appid = app.currentBotId || ''
  const q = `appid=${appid}`
  // 并行请求所有拆分接口, 各自独立更新 — 先到先渲染
  const tasks = [
    axios.get(`/api/statistics/summary?${q}`).then(r => { summary.value = r.data?.data || {} }).catch(() => {}),
    axios.get(`/api/statistics/active?${q}`).then(r => { active.value = r.data?.data || {} }).catch(() => {}),
    axios.get(`/api/statistics/top?${q}`).then(r => { top.value = r.data?.data || {} }).catch(() => {}),
    axios.get(`/api/statistics/events?${q}`).then(r => { events.value = r.data?.data || {} }).catch(() => {}),
    axios.get(`/api/statistics/totals?${q}`).then(r => { totals.value = r.data?.data || {} }).catch(() => {}),
    axios.get(`/api/statistics/hourly?${q}`).then(r => {
      const d = r.data?.data || {}
      hourly.value = d.today_hourly_distribution || []
    }).catch(() => {}),
  ]
  await Promise.all(tasks)
}
async function fetchChart() { try { const r = await axios.get(`/api/statistics/chart?days=${days.value}&appid=${app.currentBotId || ''}`); chartData.value = r.data?.data || null; hasChart.value = !!chartData.value } catch {} }
async function refresh() { loading.value = true; await Promise.all([fetchStats(), fetchChart()]); loading.value = false }

// 等待机器人列表加载完成 (单机器人会被自动选中) 后再发起首次统计请求,
// 避免先用空 appid 查一次、自动选中后再用真实 appid 查一次, 造成数据库重复全表扫描
let ready = false
watch(() => app.currentBotId, () => { if (ready) refresh() })
onMounted(async () => {
  await app.ensureBots()
  ready = true
  refresh()
})
</script>

<template>
  <div class="stats-page">
    <div class="stats-header">
      <div class="stats-actions">
        <select v-model="days" class="ctrl-select" @change="refresh"><option :value="7">近 7 天</option><option :value="14">近 14 天</option><option :value="30">近 30 天</option></select>
        <button class="refresh-btn" @click="refresh" :disabled="loading">{{ loading ? '加载中...' : '刷新' }}</button>
      </div>
    </div>

    <div class="chart-panel">
      <div class="chart-tabs">
        <button v-for="t in TABS" :key="t.key" :class="['chart-tab', { active: chartTab === t.key }]" @click="chartTab = t.key">{{ t.label }}</button>
      </div>
      <div class="chart-box">
        <Line v-if="hasChart" :key="chartTab" :data="lineData" :options="lineOpts" />
        <div v-else class="chart-empty">暂无数据</div>
      </div>
    </div>

    <div v-if="hourly.length" class="chart-panel">
      <div class="chart-panel-title">今日每小时消息分布</div>
      <div class="chart-box short"><Bar :data="barData" :options="barOpts" /></div>
    </div>

    <div class="bottom-row">
      <div v-if="topCmds.length" class="rank-card">
        <h3>命令排行</h3>
        <div v-for="(c, i) in topCmds" :key="c.command" class="rank-item">
          <span :class="['rank-idx', 'r' + i]">{{ i + 1 }}</span>
          <span class="rank-name">{{ c.command }}</span>
          <span class="rank-val">{{ c.count }}</span>
        </div>
      </div>
      <div v-if="topGroups.length" class="rank-card">
        <h3>群消息排行</h3>
        <div v-for="(g, i) in topGroups" :key="g.group_id" class="rank-item">
          <span :class="['rank-idx', 'r' + i]">{{ i + 1 }}</span>
          <span class="rank-name">{{ g.group_id }}</span>
          <span class="rank-val">{{ g.message_count }}</span>
        </div>
      </div>
      <div v-if="topUsers.length" class="rank-card">
        <h3>用户消息排行</h3>
        <div v-for="(u, i) in topUsers" :key="u.user_id" class="rank-item">
          <span :class="['rank-idx', 'r' + i]">{{ i + 1 }}</span>
          <span class="rank-name">{{ u.user_id }}</span>
          <span class="rank-val">{{ u.message_count }}</span>
        </div>
      </div>
    </div>

    <div class="overview-row">
      <div v-for="card in overviewCards" :key="card.label" :class="['ov-card', { active: chartTab === card.tab }]" @click="chartTab = card.tab">
        <div class="ov-val">{{ card.value }}</div>
        <div class="ov-label">{{ card.label }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats-page {
  width:100%
}
.stats-header {
  display:flex;
  align-items:center;
  justify-content:space-between;
  margin-bottom:16px
}
.stats-header h2 {
  color:var(--text);
  font-size:18px;
  font-weight:700;
  margin:0
}
.stats-actions {
  display:flex;
  gap:8px;
  align-items:center
}
.ctrl-select {
  background:var(--bg3);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:6px;
  padding:4px 8px;
  font-size:13px;
  cursor:pointer;
  outline:none
}
.refresh-btn {
  background:var(--accent);
  color:#fff;
  border:none;
  border-radius:6px;
  padding:5px 14px;
  font-size:13px;
  cursor:pointer;
  transition:opacity .15s
}
.refresh-btn:hover {
  opacity:.85
}
.refresh-btn:disabled {
  opacity:.45;
  cursor:default
}
.overview-row {
  display:grid;
  grid-template-columns:repeat(6,1fr);
  gap:8px;
  margin-bottom:14px
}
.ov-card {
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:8px;
  padding:10px 8px;
  text-align:center;
  cursor:pointer;
  transition:all .15s;
  -webkit-user-select:none;
  -moz-user-select:none;
  user-select:none
}
.ov-card:hover {
  border-color:var(--accent)
}
.ov-card.active {
  border-color:var(--accent);
  box-shadow:0 0 0 1px var(--accent)
}
.ov-val {
  color:var(--text);
  font-size:16px;
  font-weight:700;
  line-height:1.2
}
.ov-label {
  color:var(--text2);
  font-size:11px;
  margin-top:2px
}
.chart-panel {
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:10px;
  margin-bottom:14px;
  overflow:hidden
}
.chart-panel-title {
  padding:12px 16px 0;
  color:var(--text);
  font-size:14px;
  font-weight:600
}
.chart-tabs {
  display:flex;
  border-bottom:1px solid var(--border)
}
.chart-tab {
  flex:1;
  padding:10px 0;
  text-align:center;
  border:none;
  background:none;
  color:var(--text2);
  font-size:13px;
  cursor:pointer;
  position:relative;
  transition:color .15s;
  font-weight:500
}
.chart-tab:hover {
  color:var(--text)
}
.chart-tab.active {
  color:var(--accent);
  font-weight:600
}
.chart-tab.active:after {
  content:"";
  position:absolute;
  left:20%;
  right:20%;
  bottom:0;
  height:2px;
  background:var(--accent);
  border-radius:2px
}
.chart-box {
  height:300px;
  padding:16px;
  position:relative
}
.chart-box.short {
  height:200px
}
.chart-empty {
  color:var(--text3);
  text-align:center;
  padding-top:130px
}
.bottom-row {
  display:grid;
  grid-template-columns:repeat(3,1fr);
  gap:12px;
  margin-bottom:14px
}
.rank-card {
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:10px;
  padding:14px
}
.rank-card h3 {
  color:var(--text);
  font-size:14px;
  font-weight:600;
  margin:0 0 8px
}
.rank-item {
  display:flex;
  align-items:center;
  gap:8px;
  padding:5px 0;
  border-bottom:1px solid var(--border);
  font-size:13px
}
.rank-item:last-child {
  border-bottom:none
}
.rank-idx {
  width:20px;
  height:20px;
  border-radius:4px;
  display:flex;
  align-items:center;
  justify-content:center;
  font-size:11px;
  font-weight:700;
  flex-shrink:0;
  background:var(--border);
  color:var(--text2)
}
.rank-idx.r0 {
  background:#d29922;
  color:#fff
}
.rank-idx.r1 {
  background:#8b949e;
  color:#fff
}
.rank-idx.r2 {
  background:#8b6914;
  color:#fff
}
.rank-name {
  flex:1;
  color:var(--text);
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  font-family:monospace
}
.rank-val {
  color:var(--accent);
  font-weight:600;
  flex-shrink:0
}
@media(max-width:1200px) {
  .overview-row {
  grid-template-columns:repeat(4,1fr)
}
}
@media(max-width:767px) {
  .overview-row {
  grid-template-columns:repeat(3,1fr);
  gap:6px
}
.ov-card {
  padding:8px 4px
}
.ov-val {
  font-size:14px
}
.ov-label {
  font-size:10px
}
.bottom-row {
  grid-template-columns:1fr
}
.chart-box {
  height:220px;
  padding:10px
}
.chart-box.short {
  height:160px
}
.chart-tabs {
  overflow-x:auto
}
.stats-actions {
  flex-wrap:wrap
}
}
@media(max-width:400px) {
  .overview-row {
  grid-template-columns:repeat(2,1fr)
}
}
</style>
