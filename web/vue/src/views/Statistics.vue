<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { Chart, Filler, LineElement, PointElement, BarElement, CategoryScale, LinearScale, Legend, Tooltip, BarController, LineController } from 'chart.js'
import ChartDataLabels from 'chartjs-plugin-datalabels'
import { Line, Bar } from 'vue-chartjs'
import { useAppStore } from '../stores/app'
import axios from '../utils/axios'
import SvgIcon from '../components/SvgIcon.vue'

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
    { tab: 'msg', label: '今日消息', value: summary.value.total_messages ?? 0, icon: 'chatbubbles', color: 'c-blue' },
    { tab: 'msg', label: '私聊消息', value: summary.value.private_messages ?? 0, icon: 'chatbubbles', color: 'c-teal' },
    { tab: 'msg', label: '群聊消息', value: (summary.value.total_messages ?? 0) - (summary.value.private_messages ?? 0), icon: 'group', color: 'c-purple' },
    { tab: 'active', label: '活跃用户', value: active.value.active_users ?? 0, icon: 'people', color: 'c-green' },
    { tab: 'active', label: '活跃群聊', value: active.value.active_groups ?? 0, icon: 'group', color: 'c-orange' },
    { tab: 'total', label: '总用户数', value: totals.value.total_users ?? 0, icon: 'people', color: 'c-blue' },
    { tab: 'total', label: '总群组数', value: totals.value.total_groups ?? 0, icon: 'group', color: 'c-purple' },
    { tab: 'total', label: '总好友数', value: c?.total_friends ?? 0, icon: 'people', color: 'c-teal' },
    { tab: 'event', label: '进群', value: events.value.group_join_count ?? 0, icon: 'plus', color: 'c-green' },
    { tab: 'event', label: '退群', value: events.value.group_leave_count ?? 0, icon: 'minus', color: 'c-red' },
    { tab: 'event', label: '加好友', value: events.value.friend_add_count ?? 0, icon: 'plus', color: 'c-cyan' },
    { tab: 'event', label: '删好友', value: events.value.friend_remove_count ?? 0, icon: 'trash', color: 'c-orange' },
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

const lineOpts = { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false }, plugins: { legend: { labels: { color: '#5b6675', font: { size: 12 }, usePointStyle: true, pointStyle: 'circle' } }, tooltip: { mode: 'index', intersect: false }, datalabels: { color: '#97a1b0', font: { size: 10, weight: 600 }, anchor: 'end', align: 'top', offset: 2, formatter: v => v > 0 ? v : '' } }, scales: { x: { ticks: { color: '#97a1b0' }, grid: { color: 'rgba(120,130,150,0.12)' } }, y: { beginAtZero: true, ticks: { color: '#97a1b0', precision: 0 }, grid: { color: 'rgba(120,130,150,0.12)' } } } }
const barOpts = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false }, datalabels: { display: false } }, scales: { x: { ticks: { color: '#97a1b0', maxRotation: 0 }, grid: { display: false } }, y: { beginAtZero: true, ticks: { color: '#97a1b0', precision: 0 }, grid: { color: 'rgba(120,130,150,0.12)' } } } }

async function fetchStats() {
  const bot_qq = app.currentBotId || ''
  const q = `bot_qq=${bot_qq}`
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
async function fetchChart() { try { const r = await axios.get(`/api/statistics/chart?days=${days.value}&bot_qq=${app.currentBotId || ''}`); chartData.value = r.data?.data || null; hasChart.value = !!chartData.value } catch {} }
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
    <div class="ui-page-head">
      <div class="ui-page-head-main">
        <div class="ui-page-icon"><SvgIcon name="stats-chart" :size="24" /></div>
        <div>
          <h1 class="ui-page-title">数据看板</h1>
          <div class="ui-page-sub">查看消息收发统计和插件触发情况</div>
        </div>
      </div>
      <div class="ui-page-actions">
        <label class="ui-chip">
          <SvgIcon name="stats-chart" :size="15" style="opacity:.6" />
          <select v-model="days" @change="refresh">
            <option :value="7">近 7 天</option><option :value="14">近 14 天</option><option :value="30">近 30 天</option>
          </select>
        </label>
        <button class="ui-btn" @click="refresh" :disabled="loading">
          <SvgIcon name="refresh" :size="15" />{{ loading ? '加载中' : '刷新' }}
        </button>
      </div>
    </div>

    <div class="ui-sec-head">
      <div class="ui-sec-icon"><SvgIcon name="people" :size="17" /></div>
      <div class="ui-sec-title">数据概览</div>
    </div>
    <div class="ui-stat-grid">
      <div v-for="card in overviewCards" :key="card.label" :class="['ui-stat', card.color, { active: chartTab === card.tab }]" @click="chartTab = card.tab">
        <div class="ui-stat-top">
          <div class="ui-stat-ic"><SvgIcon :name="card.icon" :size="17" /></div>
          <div class="ui-stat-label">{{ card.label }}</div>
        </div>
        <div class="ui-stat-val">{{ card.value }}</div>
      </div>
    </div>

    <div class="ui-card chart-panel">
      <div class="chart-tabs">
        <button v-for="t in TABS" :key="t.key" :class="['ui-pill', { active: chartTab === t.key }]" @click="chartTab = t.key">{{ t.label }}</button>
      </div>
      <div class="chart-box">
        <Line v-if="hasChart" :key="chartTab" :data="lineData" :options="lineOpts" />
        <div v-else class="chart-empty">暂无数据</div>
      </div>
    </div>

    <div v-if="hourly.length" class="ui-card chart-panel">
      <div class="chart-panel-title">今日每小时消息分布</div>
      <div class="chart-box short"><Bar :data="barData" :options="barOpts" /></div>
    </div>

    <div class="bottom-row">
      <div v-if="topCmds.length" class="ui-card rank-card">
        <h3><span class="ui-sec-icon" style="width:26px;height:26px"><SvgIcon name="extension-puzzle" :size="15" /></span>命令排行</h3>
        <div v-for="(c, i) in topCmds" :key="c.command" class="rank-item">
          <span :class="['rank-idx', 'r' + i]">{{ i + 1 }}</span>
          <span class="rank-name">{{ c.command }}</span>
          <span class="rank-val">{{ c.count }}</span>
        </div>
      </div>
      <div v-if="topGroups.length" class="ui-card rank-card">
        <h3><span class="ui-sec-icon" style="width:26px;height:26px"><SvgIcon name="group" :size="15" /></span>群消息排行</h3>
        <div v-for="(g, i) in topGroups" :key="g.group_id" class="rank-item">
          <span :class="['rank-idx', 'r' + i]">{{ i + 1 }}</span>
          <span class="rank-name">{{ g.group_id }}</span>
          <span class="rank-val">{{ g.message_count }}</span>
        </div>
      </div>
      <div v-if="topUsers.length" class="ui-card rank-card">
        <h3><span class="ui-sec-icon" style="width:26px;height:26px"><SvgIcon name="people" :size="15" /></span>用户消息排行</h3>
        <div v-for="(u, i) in topUsers" :key="u.user_id" class="rank-item">
          <span :class="['rank-idx', 'r' + i]">{{ i + 1 }}</span>
          <span class="rank-name">{{ u.user_id }}</span>
          <span class="rank-val">{{ u.message_count }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.stats-page {
  width:100%
}
.ui-stat.active {
  border-color:var(--cc);
  box-shadow:0 0 0 1.5px var(--cc)
}
.ui-stat { cursor:pointer; -webkit-user-select:none; user-select:none }
.chart-panel {
  margin-bottom:16px;
  overflow:hidden
}
.chart-panel-title {
  padding:16px 18px 0;
  color:var(--text);
  font-size:15px;
  font-weight:700
}
.chart-tabs {
  display:flex;
  gap:6px;
  padding:14px 16px;
  border-bottom:1px solid var(--border)
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
  gap:14px;
  margin-bottom:16px
}
.rank-card {
  padding:18px
}
.rank-card h3 {
  display:flex;
  align-items:center;
  gap:8px;
  color:var(--text);
  font-size:15px;
  font-weight:700;
  margin:0 0 12px
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
@media(max-width:767px) {
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
}
</style>
