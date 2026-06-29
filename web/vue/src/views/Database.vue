<script setup>
import { h, ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useMessage, NButton, NTag, NPopover } from 'naive-ui'
import axios from '../utils/axios'
import SvgIcon from '../components/SvgIcon.vue'

const msg = useMessage()
const PAGE = 50
const loading = ref(false)
const querying = ref(false)
const databases = ref([])
const tables = ref([])
const dbPath = ref('')
const tableName = ref('')
const tableInfo = ref(null)
const rows = ref([])
const cols = ref([])
const dataColKeys = ref([])
const total = ref(0)
const page = ref(1)
const sql = ref('')
const mode = ref('table')
const selectedKeys = ref([])
const expandedKeys = ref([])
const treeSelected = ref([])
const checkedRows = ref([])
const deleting = ref(false)
const tableMaxHeight = ref(480)
const leftColRef = ref(null)
const tableWrapRef = ref(null)
let resizeObserver = null

const scrollX = computed(() => {
  const totalWidth = cols.value.reduce((sum, col) => sum + (col.type === 'selection' ? 48 : Number(col.width || col.minWidth || 180)), 0)
  return totalWidth > 900 ? totalWidth : undefined
})

const popoverStyle = {
  maxWidth: 'min(560px, 78vw)',
  maxHeight: '42vh',
  overflow: 'auto',
  whiteSpace: 'pre-wrap',
  overflowWrap: 'anywhere',
  wordBreak: 'break-word',
}

const cellPreview = (text) => {
  const normalized = String(text).replace(/\s+/g, ' ').trim()
  return normalized.length > 160 ? `${normalized.slice(0, 160)}...` : normalized
}

function recomputeHeight() {
  const left = leftColRef.value
  const wrap = tableWrapRef.value
  if (!left || !wrap) return
  const leftBottom = left.getBoundingClientRect().bottom
  const wrapTop = wrap.getBoundingClientRect().top
  const hasPager = mode.value === 'table' && total.value > PAGE
  const reserve = hasPager ? 52 : 8
  tableMaxHeight.value = Math.max(Math.floor(leftBottom - wrapTop - reserve), 280)
}

const treeData = computed(() => {
  const map = {}
  for (const db of databases.value) {
    const k = db.bot_qq
    if (!map[k]) map[k] = { label: db.label || db.bot_qq, bot_qq: db.bot_qq, children: [] }
    const name = db.date ? `${db.date}/${db.name}` : db.name
    const size = (db.size / 1024).toFixed(1)
    map[k].children.push({ key: db.path, label: name, suffix: () => h(NTag, { size: 'tiny', round: true, bordered: false }, { default: () => `${size}KB` }) })
  }
  const result = []
  for (const [k, v] of Object.entries(map)) result.push({ key: `bot_${k}`, label: v.label, children: v.children, isLeaf: false })
  return result
})

function renderDbValue(value) {
  const isNull = value == null
  const text = isNull ? 'NULL' : String(value)
  const cell = h('div', { class: 'db-cell-trigger' }, [
    h('span', { class: ['db-cell-text', { 'db-cell-null': isNull }] }, cellPreview(text)),
  ])
  return h(NPopover, { trigger: 'hover', placement: 'top', style: popoverStyle }, {
    trigger: () => cell,
    default: () => h('div', { class: 'db-popover-content' }, [
      h('div', { class: 'db-popover-actions' }, [
        h('span', { class: 'db-popover-title' }, '完整数据'),
        h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: e => { e?.stopPropagation?.(); copyCell(text) } }, { default: () => '复制' }),
      ]),
      h('pre', { class: 'db-popover-text' }, text),
    ]),
  })
}

function buildCols(rawCols, withSelect = false) {
  dataColKeys.value = rawCols.map(c => c.name)
  const mapped = rawCols.map(c => ({
    title: c.name, key: c.name, minWidth: 140, width: 220, render: row => renderDbValue(row[c.name])
  }))
  const actions = {
    title: '操作',
    key: '__actions',
    width: 80,
    render: row => h(NButton, { size: 'tiny', quaternary: true, onClick: () => copyRow(row) }, { default: () => '复制' }),
  }
  cols.value = withSelect ? [{ type: 'selection' }, ...mapped, actions] : [...mapped, actions]
}

async function fetchDatabases() {
  loading.value = true
  try { databases.value = (await axios.get('/api/database/list')).data.databases || [] }
  catch { msg.error('获取数据库列表失败') }
  finally { loading.value = false }
}

function onTreeSelect(keys) {
  const k = keys[0]; if (!k || k.startsWith('bot_')) return
  treeSelected.value = [k]; dbPath.value = k; tableName.value = ''; tableInfo.value = null
  rows.value = []; cols.value = []; dataColKeys.value = []; total.value = 0
  fetchTables(k)
}

async function fetchTables(path) {
  try { tables.value = (await axios.post('/api/database/tables', { path })).data.tables || [] }
  catch { msg.error('获取表列表失败') }
}

async function selectTable(t) {
  tableName.value = t.name; tableInfo.value = t; page.value = 1; mode.value = 'table'
  sql.value = `SELECT * FROM "${t.name}" ORDER BY rowid DESC LIMIT 50`
  await fetchData()
}

async function fetchData() {
  querying.value = true; checkedRows.value = []
  try {
    const res = (await axios.post('/api/database/query', { path: dbPath.value, table: tableName.value, page: page.value, page_size: PAGE })).data
    rows.value = res.data || []; total.value = res.total || 0; buildCols(res.columns || [], true)
  } catch { msg.error('查询失败') }
  finally { querying.value = false }
}

async function execSql() {
  if (!sql.value.trim() || !dbPath.value) return
  querying.value = true; mode.value = 'sql'
  try {
    const res = await axios.post('/api/database/sql', { path: dbPath.value, sql: sql.value.trim() })
    if (res.data.success) { rows.value = res.data.data || []; total.value = res.data.total || 0; buildCols(res.data.columns || [], false) }
    else msg.error(res.data.message || '查询失败')
  } catch (e) { msg.error(e.response?.data?.message || '查询失败') }
  finally { querying.value = false }
}

async function deleteSelected() {
  if (!checkedRows.value.length) return
  deleting.value = true
  try {
    const res = await axios.post('/api/database/delete', { path: dbPath.value, table: tableName.value, rowids: checkedRows.value })
    if (res.data.success) { msg.success(`已删除 ${res.data.deleted} 条数据`); checkedRows.value = []; await fetchData() }
    else msg.error(res.data.message || '删除失败')
  } catch (e) { msg.error(e.response?.data?.message || '删除失败') }
  finally { deleting.value = false }
}

function onPageChange(p) { page.value = p; fetchData() }

function getRowKeys(row) { return dataColKeys.value.length ? dataColKeys.value : Object.keys(row || {}).filter(k => !k.startsWith('_')) }
function formatRow(row) {
  const data = {}
  for (const k of getRowKeys(row)) data[k] = row[k] ?? null
  return JSON.stringify(data, null, 2)
}

function fallbackCopyText(text) {
  const el = document.createElement('textarea')
  el.value = text; el.readOnly = true; el.style.cssText = 'position:fixed;top:-1000px;left:-1000px;opacity:0'
  document.body.appendChild(el); el.select()
  const ok = document.execCommand('copy')
  document.body.removeChild(el)
  if (!ok) throw new Error('copy failed')
}

async function copyText(text) {
  if (navigator.clipboard?.writeText && window.isSecureContext) {
    try { await navigator.clipboard.writeText(text); return } catch {}
  }
  fallbackCopyText(text)
}

async function copyRow(row) {
  try { await copyText(formatRow(row)); msg.success('已复制该行数据') }
  catch { msg.error('复制失败，请检查浏览器剪贴板权限') }
}

async function copyCell(text) {
  try { await copyText(text); msg.success('已复制该数据') }
  catch { msg.error('复制失败，请检查浏览器剪贴板权限') }
}

function exportCsv() {
  if (!rows.value.length) return
  const keys = getRowKeys(rows.value[0]), header = keys.join(',')
  const body = rows.value.map(r => keys.map(k => { const v = r[k]; if (v == null) return ''; const s = String(v).replace(/"/g, '""'); return s.includes(',') || s.includes('\n') || s.includes('"') ? `"${s}"` : s }).join(',')).join('\n')
  const blob = new Blob(['\uFEFF' + header + '\n' + body], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob), a = document.createElement('a')
  a.href = url; a.download = `${tableName.value || 'query'}_${new Date().toISOString().slice(0, 10)}.csv`; a.click(); URL.revokeObjectURL(url)
}

onMounted(() => {
  fetchDatabases()
  resizeObserver = new ResizeObserver(() => recomputeHeight())
  nextTick(() => {
    if (leftColRef.value) resizeObserver.observe(leftColRef.value)
    recomputeHeight()
  })
  window.addEventListener('resize', recomputeHeight)
})

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect()
  window.removeEventListener('resize', recomputeHeight)
})

watch([rows, tables, () => tableInfo.value, () => total.value], () => nextTick(recomputeHeight))
</script>

<template>
  <div>
    <div class="ui-page-head">
      <div class="ui-page-head-main">
        <div class="ui-page-icon"><SvgIcon name="cube" :size="24" /></div>
        <div>
          <h1 class="ui-page-title">数据库</h1>
          <div class="ui-page-sub">浏览和查询数据库表</div>
        </div>
      </div>
    </div>
    <n-spin :show="loading">
      <div class="grid grid-cols-1 lg:grid-cols-4 gap-4 items-start">
        <div ref="leftColRef" class="lg:col-span-1 space-y-3">
          <n-card size="small" title="数据库" :style="{ background: 'var(--bg2)', border: '1px solid var(--border)' }">
            <n-tree :data="treeData" :selected-keys="treeSelected" @update:selected-keys="onTreeSelect" block-line selectable :expanded-keys="expandedKeys" @update:expanded-keys="v => expandedKeys = v" />
            <n-empty v-if="!treeData.length && !loading" description="暂无数据库" size="small" class="mt-2" />
          </n-card>
          <n-card v-if="tables.length" size="small" title="表" :style="{ background: 'var(--bg2)', border: '1px solid var(--border)' }">
            <div class="space-y-1">
              <div v-for="t in tables" :key="t.name" class="flex items-center justify-between px-2 py-1.5 rounded cursor-pointer text-sm transition-colors"
                :style="{ background: tableName === t.name ? 'var(--primary-alpha)' : 'transparent', color: 'var(--text1)' }" @click="selectTable(t)">
                <span class="truncate">{{ t.name }}</span>
                <n-tag size="tiny" round>{{ t.count }}</n-tag>
              </div>
            </div>
          </n-card>
          <n-card v-if="tableInfo" size="small" title="表结构" :style="{ background: 'var(--bg2)', border: '1px solid var(--border)' }">
            <div class="text-xs space-y-0.5">
              <div v-for="c in tableInfo.columns" :key="c.name" class="flex gap-2">
                <span class="font-mono" style="color:var(--primary)">{{ c.name }}</span>
                <span style="color:var(--text3)">{{ c.type }}{{ c.pk ? ' PK' : '' }}{{ c.notnull ? ' NOT NULL' : '' }}</span>
              </div>
            </div>
          </n-card>
        </div>
        <div class="lg:col-span-3 space-y-3">
          <n-card size="small" :style="{ background: 'var(--bg2)', border: '1px solid var(--border)' }">
            <div class="flex gap-2">
              <n-input v-model:value="sql" type="textarea" placeholder="输入 SQL 查询 (仅 SELECT)..." :autosize="{ minRows: 1, maxRows: 4 }" class="flex-1 font-mono text-sm" @keydown.ctrl.enter="execSql" />
              <n-button type="primary" @click="execSql" :loading="querying" :disabled="!dbPath"> 执行 </n-button>
            </div>
            <div class="text-xs mt-1" style="color:var(--text3)"> Ctrl+Enter 执行 · 仅允许 SELECT 查询 · 自动限制 500 行 </div>
          </n-card>
          <n-card v-if="rows.length || querying" size="small" :style="{ background: 'var(--bg2)', border: '1px solid var(--border)' }">
            <template #header>
              <div class="flex items-center justify-between">
                <span class="text-sm">{{ mode === 'sql' ? 'SQL 查询结果' : tableName || '数据' }} <span v-if="total > 0" style="color:var(--text3)"> ({{ total }} 行)</span></span>
                <div class="flex gap-2">
                  <n-button v-if="checkedRows.length" size="tiny" type="error" @click="deleteSelected" :loading="deleting"> 删除选中 ({{ checkedRows.length }}) </n-button>
                  <n-button v-if="rows.length" size="tiny" quaternary @click="exportCsv">导出 CSV</n-button>
                </div>
              </div>
            </template>
            <n-spin :show="querying">
              <div ref="tableWrapRef" class="overflow-x-auto">
                <n-data-table class="db-data-table" :columns="cols" :data="rows" :bordered="false" :single-line="false" size="small" :max-height="tableMaxHeight" :scroll-x="scrollX" :row-key="r => r._rowid" :checked-row-keys="checkedRows" @update:checked-row-keys="k => checkedRows = k" striped />
              </div>
              <div v-if="mode === 'table' && total > PAGE" class="flex justify-center mt-3">
                <n-pagination v-model:page="page" :page-count="Math.ceil(total / PAGE)" :page-size="PAGE" size="small" @update:page="onPageChange" />
              </div>
            </n-spin>
          </n-card>
          <n-empty v-if="!rows.length && !querying && dbPath" description="选择左侧的表查看数据，或输入 SQL 查询" class="mt-8" />
          <n-empty v-if="!dbPath && !loading" description="选择左侧的数据库开始浏览" class="mt-8" />
        </div>
      </div>
    </n-spin>
  </div>
</template>

<style scoped>
:deep(.n-card) {
  border-radius: var(--radius) !important;
  box-shadow: var(--shadow-sm);
}
.db-cell-text {
  display: block;
  width: 100%;
  max-width: 100%;
  overflow: hidden;
  line-height: 20px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.db-cell-trigger {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  height: 22px;
  cursor: default;
}

.db-cell-null {
  color: var(--text3);
  font-style: italic;
}

:deep(.db-data-table .n-data-table-td) {
  height: 34px;
  max-height: 34px;
  overflow: hidden;
  white-space: nowrap;
  vertical-align: middle;
}

:deep(.db-data-table .n-data-table-tr) {
  height: 34px;
}

:deep(.db-data-table .n-data-table-td__ellipsis) {
  max-width: 100%;
  line-height: 20px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

:global(.db-popover-content) {
  min-width: 220px;
}

:global(.db-popover-actions) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

:global(.db-popover-title) {
  color: var(--text2);
  font-size: 12px;
  font-weight: 600;
}

:global(.db-popover-text) {
  margin: 0;
  font-family: inherit;
  line-height: 1.55;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
}
</style>
