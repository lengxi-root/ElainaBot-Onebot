<template>
  <div class="stats-page">
    <div class="stats-header">
      <h2>数据统计</h2>
      <div class="stats-actions">
        <button class="refresh-btn" @click="loadData" :disabled="loading">刷新</button>
      </div>
    </div>

    <!-- Overview Row -->
    <div class="overview-row">
      <div class="ov-card" v-for="s in overviewStats" :key="s.label">
        <div class="ov-val">{{ s.value }}</div>
        <div class="ov-label">{{ s.label }}</div>
      </div>
    </div>

    <!-- Chart Panel: hourly -->
    <div class="chart-panel">
      <div class="chart-panel-title">24小时消息分布</div>
      <div class="chart-body">
        <div class="bar-chart" v-if="hourlyData.length">
          <div class="bar-col" v-for="(count, idx) in hourlyData" :key="idx">
            <div class="bar-fill" :style="{ height: barH(count, hourlyMax) + '%' }"></div>
            <span class="bar-val" v-if="count">{{ count }}</span>
            <span class="bar-label">{{ idx }}时</span>
          </div>
        </div>
        <div class="chart-empty" v-else>暂无数据</div>
      </div>
    </div>

    <!-- Chart Panel: daily -->
    <div class="chart-panel">
      <div class="chart-panel-title">7天消息趋势</div>
      <div class="chart-body">
        <div class="bar-chart daily" v-if="dailyData.length">
          <div class="bar-col" v-for="d in dailyData" :key="d.date">
            <div class="bar-fill" :style="{ height: barH(d.count, dailyMax) + '%' }"></div>
            <span class="bar-val" v-if="d.count">{{ d.count }}</span>
            <span class="bar-label">{{ d.date.slice(5) }}</span>
          </div>
        </div>
        <div class="chart-empty" v-else>暂无数据</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const data = ref({})
const loading = ref(false)
const hourlyData = ref([])
const dailyData = ref([])

const overviewStats = computed(() => [
  { label: '今日消息', value: data.value.today_messages || 0 },
  { label: '总消息数', value: data.value.total_messages || 0 },
  { label: '今日活跃用户', value: data.value.active_users || 0 },
  { label: '活跃群聊', value: data.value.active_groups || 0 },
])

const hourlyMax = computed(() => Math.max(...hourlyData.value, 1))
const dailyMax = computed(() => Math.max(...dailyData.value.map(d => d.count), 1))

function barH(count, max) {
  return max > 0 ? (count / max) * 100 : 0
}

async function loadData() {
  loading.value = true
  const res = await store.fetchApi('/statistics')
  if (res && res.success) {
    data.value = res
    hourlyData.value = res.hourly || []
    dailyData.value = res.daily || []
  }
  loading.value = false
}

onMounted(() => { loadData() })
</script>

<style scoped>
.stats-page { width: 100%; }
.stats-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.stats-header h2 { color: var(--text); font-size: 18px; font-weight: 700; margin: 0; }
.refresh-btn {
  background: var(--accent); color: #fff; border: none; border-radius: 6px;
  padding: 5px 14px; font-size: 13px; cursor: pointer; transition: opacity 0.15s;
}
.refresh-btn:hover { opacity: 0.85; }
.refresh-btn:disabled { opacity: 0.45; cursor: default; }

.overview-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 14px; }
.ov-card {
  background: var(--bg2); border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 8px; text-align: center;
}
.ov-val { color: var(--text); font-size: 16px; font-weight: 700; line-height: 1.2; }
.ov-label { color: var(--text2); font-size: 11px; margin-top: 2px; }

.chart-panel {
  background: var(--bg2); border: 1px solid var(--border); border-radius: 10px;
  margin-bottom: 14px; overflow: hidden;
}
.chart-panel-title { padding: 12px 16px 0; color: var(--text); font-size: 14px; font-weight: 600; }
.chart-body { padding: 12px 16px 16px; }
.chart-empty { color: var(--text3); text-align: center; padding: 40px 0; font-size: 13px; }

.bar-chart { display: flex; align-items: flex-end; gap: 3px; height: 140px; }
.bar-chart.daily { height: 120px; }
.bar-col {
  flex: 1; display: flex; flex-direction: column; align-items: center;
  height: 100%; justify-content: flex-end;
}
.bar-fill {
  width: 100%; max-width: 24px;
  background: linear-gradient(180deg, var(--accent), var(--accent-light));
  border-radius: 3px 3px 0 0; min-height: 2px; transition: height 0.3s;
}
.bar-val { font-size: 9px; color: var(--text2); margin-bottom: 2px; }
.bar-label { font-size: 10px; color: var(--text3); margin-top: 4px; }
</style>
