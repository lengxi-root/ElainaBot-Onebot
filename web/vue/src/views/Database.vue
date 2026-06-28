<template>
  <div class="db-page">
    <div class="db-toolbar">
      <h2>数据库浏览器</h2>
      <div class="db-actions">
        <select class="db-select" v-model="selectedDb" @change="loadTables">
          <option value="">选择数据库</option>
          <option v-for="db in databases" :key="db.path" :value="db.path">{{ db.name }}</option>
        </select>
        <select class="db-select" v-model="selectedTable" @change="loadTableData" :disabled="!tables.length">
          <option value="">选择表</option>
          <option v-for="t in tables" :key="t.name" :value="t.name">{{ t.name }} ({{ t.row_count }})</option>
        </select>
        <button class="db-btn" @click="refreshAll" :disabled="!selectedDb">刷新</button>
      </div>
    </div>

    <!-- Query Area -->
    <div class="query-section" v-if="selectedDb">
      <div class="query-header">
        <span>SQL 查询</span>
        <button class="db-btn exec-btn" @click="executeQuery" :disabled="!query.trim()">执行</button>
      </div>
      <textarea class="query-input" v-model="query" placeholder="输入 SQL 查询..." spellcheck="false" rows="3"></textarea>
    </div>

    <!-- Results -->
    <div class="db-results" v-if="columns.length">
      <div class="results-info">
        <span>{{ rows.length }} 行</span>
        <span v-if="queryTime">耗时 {{ queryTime }}ms</span>
      </div>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th v-for="col in columns" :key="col">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in rows" :key="idx">
              <td v-for="col in columns" :key="col">
                <span class="db-cell-text" :title="String(row[col] ?? '')">{{ row[col] ?? '' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="db-empty" v-else-if="selectedDb && !loading">
      {{ queryError || '选择表或执行查询查看数据' }}
    </div>
    <div class="db-empty" v-else-if="!selectedDb">
      选择数据库开始浏览
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const databases = ref([])
const tables = ref([])
const selectedDb = ref('')
const selectedTable = ref('')
const columns = ref([])
const rows = ref([])
const query = ref('')
const queryError = ref('')
const queryTime = ref(0)
const loading = ref(false)

async function loadDatabases() {
  const res = await store.fetchApi('/database/list')
  if (res && res.success) {
    databases.value = res.databases || []
  }
}

async function loadTables() {
  if (!selectedDb.value) { tables.value = []; return }
  selectedTable.value = ''
  columns.value = []
  rows.value = []
  const res = await store.fetchApi('/database/tables?db=' + encodeURIComponent(selectedDb.value))
  if (res && res.success) {
    tables.value = res.tables || []
  }
}

async function loadTableData() {
  if (!selectedTable.value) return
  query.value = `SELECT * FROM ${selectedTable.value} LIMIT 100`
  await executeQuery()
}

async function executeQuery() {
  if (!query.value.trim() || !selectedDb.value) return
  loading.value = true
  queryError.value = ''
  const start = Date.now()
  const res = await store.postApi('/database/execute', { db: selectedDb.value, sql: query.value, read_only: true })
  queryTime.value = Date.now() - start
  if (res && res.success) {
    const r = res.rows || []
    if (r.length > 0) {
      columns.value = Object.keys(r[0])
    } else {
      columns.value = []
    }
    rows.value = r
  } else {
    queryError.value = res?.error || '查询失败'
    columns.value = []
    rows.value = []
  }
  loading.value = false
}

function refreshAll() {
  if (selectedTable.value) loadTableData()
  else loadTables()
}

onMounted(() => { loadDatabases() })
</script>

<style scoped>
.db-page { display: flex; flex-direction: column; height: calc(100vh - 100px); }
.db-toolbar {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;
}
.db-toolbar h2 { color: var(--text); font-size: 18px; font-weight: 700; margin: 0; }
.db-actions { display: flex; gap: 8px; align-items: center; }
.db-select {
  background: var(--bg2); color: var(--text); border: 1px solid var(--border);
  border-radius: 6px; padding: 5px 8px; font-size: 13px; outline: none; cursor: pointer;
}
.db-select:focus { border-color: var(--accent); }
.db-btn {
  padding: 5px 12px; border: 1px solid var(--border); border-radius: 6px;
  background: transparent; color: var(--text2); cursor: pointer; font-size: 12px;
}
.db-btn:hover { color: var(--text); border-color: var(--text3); }
.db-btn:disabled { opacity: 0.4; cursor: default; }
.exec-btn { background: var(--accent); color: #fff; border-color: var(--accent); }
.exec-btn:hover { opacity: 0.9; }

.query-section {
  margin-bottom: 12px; background: var(--bg2); border: 1px solid var(--border);
  border-radius: 8px; overflow: hidden;
}
.query-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; border-bottom: 1px solid var(--border); font-size: 12px; color: var(--text2);
}
.query-input {
  width: 100%; resize: vertical; padding: 10px 12px; border: none; outline: none;
  font-family: var(--font-mono); font-size: 13px; background: var(--bg2); color: var(--text);
  line-height: 1.5;
}

.db-results { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.results-info {
  display: flex; gap: 12px; font-size: 12px; color: var(--text3); margin-bottom: 6px;
}
.table-wrap { flex: 1; overflow: auto; border: 1px solid var(--border); border-radius: 6px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th {
  position: sticky; top: 0; background: var(--bg3);
  text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--border);
  color: var(--text2); font-weight: 600; font-size: 12px; white-space: nowrap;
}
.data-table td {
  padding: 6px 10px; border-bottom: 1px solid var(--border); color: var(--text);
  max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.data-table tr:hover td { background: rgba(88, 101, 242, 0.03); }

.db-cell-text { display: block; width: 100%; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.db-empty { color: var(--text3); text-align: center; padding: 40px 0; font-size: 13px; }
</style>
