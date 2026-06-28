<template>
  <div class="stats-page">
    <header class="page-header">
      <h1>统计分析</h1>
      <p class="subtitle">消息活跃度与趋势</p>
    </header>

    <div class="stats-grid">
      <div class="stat-card card">
        <div class="stat-icon" style="background: #eef0ff; color: var(--color-primary);">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ stats.today_messages }}</span>
          <span class="stat-label">今日消息</span>
        </div>
      </div>
      <div class="stat-card card">
        <div class="stat-icon" style="background: #dcfce7; color: #166534;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ stats.active_users }}</span>
          <span class="stat-label">活跃用户</span>
        </div>
      </div>
      <div class="stat-card card">
        <div class="stat-icon" style="background: #fef3c7; color: #92400e;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ stats.active_groups }}</span>
          <span class="stat-label">活跃群组</span>
        </div>
      </div>
      <div class="stat-card card">
        <div class="stat-icon" style="background: #ede9fe; color: #5b21b6;">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        </div>
        <div class="stat-content">
          <span class="stat-value">{{ stats.total_messages }}</span>
          <span class="stat-label">总消息数</span>
        </div>
      </div>
    </div>

    <div class="charts-row">
      <div class="card chart-card">
        <h3>今日小时分布</h3>
        <div class="bar-chart">
          <div class="bar-container">
            <div
              v-for="(val, idx) in stats.hourly"
              :key="idx"
              class="bar-wrapper"
            >
              <div class="bar" :style="{ height: barHeight(val) + '%' }" :title="`${idx}:00 - ${val} 条`">
                <span v-if="val > 0" class="bar-val">{{ val }}</span>
              </div>
              <span class="bar-label">{{ idx }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="charts-row">
      <div class="card chart-card">
        <h3>近 7 天趋势</h3>
        <div class="bar-chart">
          <div class="bar-container daily">
            <div
              v-for="day in stats.daily"
              :key="day.date"
              class="bar-wrapper"
            >
              <div class="bar bar-daily" :style="{ height: dailyBarHeight(day.count) + '%' }" :title="`${day.date} - ${day.count} 条`">
                <span v-if="day.count > 0" class="bar-val">{{ day.count }}</span>
              </div>
              <span class="bar-label">{{ day.date.slice(5) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const stats = ref({
  today_messages: 0,
  total_messages: 0,
  active_users: 0,
  active_groups: 0,
  hourly: Array(24).fill(0),
  daily: [],
})

const maxHourly = computed(() => Math.max(...stats.value.hourly, 1))
const maxDaily = computed(() => Math.max(...(stats.value.daily || []).map(d => d.count), 1))

function barHeight(val) {
  return Math.max((val / maxHourly.value) * 100, 2)
}

function dailyBarHeight(val) {
  return Math.max((val / maxDaily.value) * 100, 2)
}

async function loadStats() {
  const res = await store.fetchApi('/statistics')
  if (res && res.success) {
    stats.value = {
      today_messages: res.today_messages || 0,
      total_messages: res.total_messages || 0,
      active_users: res.active_users || 0,
      active_groups: res.active_groups || 0,
      hourly: res.hourly || Array(24).fill(0),
      daily: res.daily || [],
    }
  }
}

onMounted(loadStats)
</script>

<style scoped>
.page-header { margin-bottom: 20px; }
.page-header h1 { font-size: 22px; font-weight: 700; }
.subtitle { color: var(--color-text-muted); font-size: 13px; margin-top: 2px; }

.stats-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px; margin-bottom: 20px;
}
.stat-card { padding: 16px; display: flex; align-items: center; gap: 12px; }
.stat-icon {
  width: 40px; height: 40px; border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.stat-content { display: flex; flex-direction: column; }
.stat-value { font-size: 20px; font-weight: 700; line-height: 1.2; }
.stat-label { font-size: 12px; color: var(--color-text-muted); }

.charts-row { margin-bottom: 16px; }
.chart-card { padding: 20px; }
.chart-card h3 { font-size: 14px; font-weight: 600; margin-bottom: 16px; }

.bar-chart { overflow-x: auto; }
.bar-container { display: flex; align-items: flex-end; gap: 4px; height: 160px; padding: 0 4px; }
.bar-container.daily { gap: 12px; justify-content: center; }

.bar-wrapper { display: flex; flex-direction: column; align-items: center; flex: 1; min-width: 20px; height: 100%; justify-content: flex-end; }
.bar {
  width: 100%; max-width: 24px; background: var(--color-primary); border-radius: 3px 3px 0 0;
  transition: height 0.3s ease; position: relative; min-height: 2px;
}
.bar-daily { background: var(--color-success); max-width: 40px; }
.bar-val {
  position: absolute; top: -18px; left: 50%; transform: translateX(-50%);
  font-size: 10px; color: var(--color-text-muted); white-space: nowrap;
}
.bar-label { font-size: 10px; color: var(--color-text-muted); margin-top: 4px; }
</style>
