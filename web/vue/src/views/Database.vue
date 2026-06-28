<template>
  <div class="db-page">
    <header class="page-header">
      <h1>数据库浏览器</h1>
      <p class="subtitle">浏览 SQLite 数据库</p>
    </header>

    <div class="db-layout">
      <!-- Sidebar: DB + Table list -->
      <div class="card db-sidebar">
        <div class="panel-header">
          <span>数据库</span>
          <button class="btn btn-secondary btn-sm" @click="loadDatabases">刷新</button>
        </div>
        <div class="db-list">
          <div v-for="db in databases" :key="db.path" class="db-item">
            <div class="db-name" @click="selectDb(db)" :class="{ active: selectedDb?.path === db.path }">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
              <span>{{ db.name }}</span>
              <span class="db-size">{{ fmtSize(db.size) }}</span>
            </div>
            <div v-if="selectedDb?.path === db.path && tables.length" class="table-list">
              <div
                v-for="table in tables"
                :key="table.name"
                class="table-item"
                :class="{ active: selectedTable?.name === table.name }"
                @click="selectTable(table)"
              >
                <span>{{ table.name }}</span>
                <span class="row-count">{{ table.row_count }}</span>
              </div>
            </div>
          </div>
          <p v-if="!databases.length" class="empty-text">暂无数据库文件</p>
        </div>
      </div>

      <!-- Main: Query results -->
      <div class="card db-main">
        <template v-if="selectedTable">
          <div class="panel-header">
            <h3>{{ selectedTable.name }}</h3>
            <span class="table-info">{{ selectedTable.row_count }} 行 / {{ selectedTable.columns?.length || 0 }} 列</span>
          </div>

          <!-- SQL Editor -->
          <div class="sql-section">
            <textarea v-model="sqlQuery" class="sql-input" placeholder="输入 SQL 查询..." rows="2" spellcheck="false"></textarea>
            <div class="sql-actions">
              <button class="btn btn-primary btn-sm" @click="executeSQL">执行</button>
              <button class="btn btn-secondary btn-sm" @click="queryTable">查询表</button>
            </div>
          </div>

          <!-- Results Table -->
          <div class="results-container">
            <table class="data-table" v-if="rows.length">
              <thead>
                <tr>
                  <th v-for="col in resultColumns" :key="col" @click="toggleSort(col)" class="sortable">
                    {{ col }}
                    <span v-if="sortBy === col">{{ sortDir === 'ASC' ? ' ↑' : ' ↓' }}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, idx) in rows" :key="idx">
                  <td v-for="col in resultColumns" :key="col">{{ formatCell(row[col]) }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else class="empty-text">{{ sqlMessage || '暂无数据' }}</p>
          </div>

          <div class="results-footer">
            <span>{{ resultTotal }} 条结果</span>
            <div class="page-btns">
              <button class="btn btn-secondary btn-sm" :disabled="queryPage <= 1" @click="queryPage--; queryTable()">上一页</button>
              <span>{{ queryPage }}</span>
              <button class="btn btn-secondary btn-sm" @click="queryPage++; queryTable()">下一页</button>
            </div>
          </div>
        </template>

        <div v-else class="empty-panel">
          <p>选择一个数据库和表开始浏览</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const databases = ref([])
const tables = ref([])
const selectedDb = ref(null)
const selectedTable = ref(null)
const rows = ref([])
const resultColumns = ref([])
const resultTotal = ref(0)
const queryPage = ref(1)
const sortBy = ref('rowid')
const sortDir = ref('DESC')
const sqlQuery = ref('')
const sqlMessage = ref('')

async function loadDatabases() {
  const res = await store.fetchApi('/database/list')
  if (res && res.success) {
    databases.value = res.databases || []
  }
}

async function selectDb(db) {
  selectedDb.value = db
  selectedTable.value = null
  rows.value = []
  resultColumns.value = []
  const res = await store.fetchApi(`/database/tables?db=${encodeURIComponent(db.path)}`)
  if (res && res.success) {
    tables.value = res.tables || []
  }
}

function selectTable(table) {
  selectedTable.value = table
  queryPage.value = 1
  sortBy.value = 'rowid'
  sortDir.value = 'DESC'
  sqlQuery.value = `SELECT * FROM [${table.name}]`
  queryTable()
}

async function queryTable() {
  if (!selectedDb.value || !selectedTable.value) return
  const res = await store.postApi('/database/query', {
    db: selectedDb.value.path,
    table: selectedTable.value.name,
    page: queryPage.value,
    limit: 100,
    order_by: sortBy.value,
    order_dir: sortDir.value,
  })
  if (res && res.success) {
    rows.value = res.rows || []
    resultTotal.value = res.total || 0
    if (rows.value.length) {
      resultColumns.value = Object.keys(rows.value[0])
    }
    sqlMessage.value = ''
  }
}

async function executeSQL() {
  if (!selectedDb.value || !sqlQuery.value.trim()) return
  const res = await store.postApi('/database/execute', {
    db: selectedDb.value.path,
    sql: sqlQuery.value.trim(),
    read_only: true,
  })
  if (res && res.success) {
    if (res.rows) {
      rows.value = res.rows
      resultTotal.value = res.row_count || rows.value.length
      if (rows.value.length) {
        resultColumns.value = Object.keys(rows.value[0])
      }
      sqlMessage.value = ''
    } else {
      sqlMessage.value = `执行成功，影响 ${res.affected_rows || 0} 行`
    }
  } else {
    sqlMessage.value = res?.error || '执行失败'
    rows.value = []
  }
}

function toggleSort(col) {
  if (sortBy.value === col) {
    sortDir.value = sortDir.value === 'ASC' ? 'DESC' : 'ASC'
  } else {
    sortBy.value = col
    sortDir.value = 'DESC'
  }
  queryTable()
}

function formatCell(val) {
  if (val === null || val === undefined) return 'NULL'
  if (typeof val === 'string' && val.length > 100) return val.slice(0, 100) + '...'
  return String(val)
}

function fmtSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

onMounted(loadDatabases)
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 22px; font-weight: 700; }
.subtitle { color: var(--color-text-muted); font-size: 13px; margin-top: 2px; }

.db-layout { display: grid; grid-template-columns: 260px 1fr; gap: 16px; height: calc(100vh - 140px); }

.db-sidebar { display: flex; flex-direction: column; overflow: hidden; }
.db-main { display: flex; flex-direction: column; overflow: hidden; }

.panel-header {
  padding: 10px 16px; border-bottom: 1px solid var(--color-border-light);
  display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
  font-size: 13px; font-weight: 600;
}
.panel-header h3 { font-size: 14px; font-weight: 600; }
.table-info { font-size: 12px; color: var(--color-text-muted); font-weight: normal; }

.btn-sm { font-size: 12px; padding: 4px 10px; }

.db-list { flex: 1; overflow-y: auto; }

.db-item { border-bottom: 1px solid var(--color-border-light); }
.db-name {
  display: flex; align-items: center; gap: 6px; padding: 8px 12px; cursor: pointer;
  font-size: 13px; transition: background var(--transition);
}
.db-name:hover { background: var(--color-bg-secondary); }
.db-name.active { background: var(--color-primary-light); color: var(--color-primary); }
.db-name svg { flex-shrink: 0; color: var(--color-text-muted); }
.db-size { margin-left: auto; font-size: 11px; color: var(--color-text-muted); }

.table-list { padding: 0 0 4px 20px; }
.table-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 4px 12px; font-size: 12px; cursor: pointer; border-radius: 4px;
  transition: background var(--transition);
}
.table-item:hover { background: var(--color-bg-secondary); }
.table-item.active { background: var(--color-primary-light); color: var(--color-primary); font-weight: 500; }
.row-count { font-size: 11px; color: var(--color-text-muted); }

.sql-section {
  padding: 8px 16px; border-bottom: 1px solid var(--color-border-light);
  display: flex; gap: 8px; align-items: flex-start; flex-shrink: 0;
}
.sql-input {
  flex: 1; padding: 8px; border: 1px solid var(--color-border); border-radius: var(--radius-sm);
  font-family: var(--font-mono); font-size: 12px; outline: none; resize: none;
  background: var(--color-bg-secondary);
}
.sql-input:focus { border-color: var(--color-primary); }
.sql-actions { display: flex; flex-direction: column; gap: 4px; }

.results-container { flex: 1; overflow: auto; }

.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th {
  text-align: left; padding: 6px 12px; background: var(--color-bg-secondary);
  font-weight: 600; font-size: 11px; color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border); white-space: nowrap;
  position: sticky; top: 0; z-index: 1;
}
.data-table th.sortable { cursor: pointer; }
.data-table th.sortable:hover { color: var(--color-primary); }
.data-table td {
  padding: 4px 12px; border-bottom: 1px solid var(--color-border-light);
  font-family: var(--font-mono); max-width: 300px; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap;
}
.data-table tr:hover td { background: var(--color-bg-secondary); }

.results-footer {
  padding: 8px 16px; border-top: 1px solid var(--color-border-light);
  display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
  font-size: 12px; color: var(--color-text-muted);
}
.page-btns { display: flex; align-items: center; gap: 8px; }

.empty-panel {
  flex: 1; display: flex; align-items: center; justify-content: center;
  color: var(--color-text-muted); font-size: 14px;
}
.empty-text { color: var(--color-text-muted); font-size: 13px; text-align: center; padding: 40px; }

@media (max-width: 768px) {
  .db-layout { grid-template-columns: 1fr; height: auto; }
  .db-sidebar { max-height: 250px; }
}
</style>
