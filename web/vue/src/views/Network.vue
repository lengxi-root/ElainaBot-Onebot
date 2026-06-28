<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import axios from '../utils/axios'
import SvgIcon from '../components/SvgIcon.vue'

const msg = useMessage()
const dialog = useDialog()

const loading = ref(false)
const saving = ref(false)
const connections = ref([])
const statusList = ref([])
const server = reactive({ host: '0.0.0.0', port: 5201 })

const TYPES = {
  ws_reverse: { label: '反向 WS', sub: 'WebSocket 服务器', desc: '框架监听端口，OneBot 端作为客户端连入', icon: 'server', mode: 'server' },
  ws_forward: { label: '正向 WS', sub: 'WebSocket 客户端', desc: '框架主动连接 OneBot 端的 WebSocket 服务器，自动重连', icon: 'link', mode: 'client' },
  http_server: { label: 'HTTP 上报', sub: 'HTTP 服务器', desc: '框架接收 OneBot 端 POST 上报的事件', icon: 'cloud-download', mode: 'server' },
  http_client: { label: 'HTTP 调用', sub: 'HTTP 客户端', desc: '框架通过 HTTP 调用 OneBot 端的 API 接口', icon: 'globe', mode: 'client' },
}
const TYPE_OPTIONS = Object.entries(TYPES).map(([value, t]) => ({ label: `${t.label} · ${t.sub}`, value }))

const statusMap = computed(() => {
  const m = {}
  for (const s of statusList.value) m[s.name] = s
  return m
})

function statusOf(conn) {
  const s = statusMap.value[conn.name]
  if (!conn.enable) return { type: 'default', text: '已禁用' }
  if (s?.connected) return { type: 'success', text: s.self_id && !String(s.self_id).startsWith('forward:') ? `已连接 · ${s.self_id}` : '已连接' }
  if (s?.error) return { type: 'warning', text: s.error }
  return { type: 'warning', text: '未连接' }
}

function endpointOf(conn) {
  if (TYPES[conn.type].mode === 'client') return conn.url
  const scheme = conn.type === 'ws_reverse' ? 'ws' : 'http'
  const rawHost = conn.host || server.host
  const host = rawHost === '0.0.0.0' ? '127.0.0.1' : rawHost
  const port = conn.port || server.port
  return `${scheme}://${host}:${port}${conn.path || '/'}`
}

async function fetchData() {
  loading.value = true
  try {
    const res = await axios.get('/api/onebot/connections')
    if (res.data?.success) {
      connections.value = res.data.connections || []
      statusList.value = res.data.status || []
      Object.assign(server, res.data.server || {})
    }
  } catch { msg.error('获取网络配置失败') }
  finally { loading.value = false }
}

async function persist(successText) {
  saving.value = true
  try {
    const res = await axios.post('/api/onebot/connections', { connections: connections.value })
    if (res.data?.success) {
      connections.value = res.data.connections || connections.value
      statusList.value = res.data.status || []
      if (successText) msg.success(successText)
      setTimeout(fetchData, 1200)
      return true
    }
    msg.error(res.data?.error || '保存失败')
  } catch (e) { msg.error('保存失败: ' + (e.response?.data?.error || e.message || '')) }
  finally { saving.value = false }
  return false
}

async function toggleEnable(conn, val) {
  conn.enable = val
  await persist(val ? `已启用「${conn.name}」` : `已禁用「${conn.name}」`)
}

// ── 编辑 / 新增弹窗 ──
const showEdit = ref(false)
const editIndex = ref(-1)
const form = reactive({ type: 'ws_reverse', name: '', enable: true, host: '', port: 5201, path: '/', url: '', token: '', secret: '', reconnect_interval: 5000 })

function uniqueName(base) {
  let name = base, i = 2
  const names = connections.value.map((c, idx) => idx === editIndex.value ? null : c.name)
  while (names.includes(name)) { name = `${base} ${i++}` }
  return name
}

function applyTypeDefaults() {
  const type = form.type
  form.host = server.host
  form.port = server.port
  form.path = type === 'ws_reverse' ? '/OneBotv11' : '/'
  if (type === 'ws_forward') form.url = form.url || 'ws://127.0.0.1:3001'
  else if (type === 'http_client') form.url = form.url || 'http://127.0.0.1:3000'
  if (editIndex.value < 0 && (!form.name || form.name.startsWith('新连接'))) {
    form.name = uniqueName(TYPES[type].label)
  }
}

function onTypeChange(val) {
  form.type = val
  form.url = ''
  applyTypeDefaults()
}

function openAdd() {
  editIndex.value = -1
  Object.assign(form, {
    type: 'ws_reverse', name: '', enable: true, token: '', secret: '',
    host: server.host, port: server.port, path: '/OneBotv11', url: '', reconnect_interval: 5000,
  })
  form.name = uniqueName(TYPES['ws_reverse'].label)
  showEdit.value = true
}

function openEdit(conn) {
  editIndex.value = connections.value.indexOf(conn)
  Object.assign(form, { host: server.host, port: server.port, path: '/', url: '', token: '', secret: '', reconnect_interval: 5000 }, JSON.parse(JSON.stringify(conn)))
  showEdit.value = true
}

async function confirmEdit() {
  if (!form.name.trim()) { msg.warning('请填写名称'); return }
  if (TYPES[form.type].mode === 'client' && !form.url.trim()) { msg.warning('请填写连接 URL'); return }
  const item = JSON.parse(JSON.stringify(form))
  if (editIndex.value >= 0) connections.value.splice(editIndex.value, 1, item)
  else connections.value.push(item)
  showEdit.value = false
  await persist('已保存')
}

function removeConn(conn) {
  dialog.warning({
    title: '删除连接',
    content: `确定删除连接「${conn.name}」？`,
    positiveText: '删除', negativeText: '取消',
    onPositiveClick: async () => {
      const i = connections.value.indexOf(conn)
      if (i >= 0) connections.value.splice(i, 1)
      await persist('已删除')
    },
  })
}

function copyText(text) {
  navigator.clipboard?.writeText(text).then(() => msg.success('已复制')).catch(() => {})
}

onMounted(fetchData)
</script>

<template>
  <div class="net-page">
    <div class="net-head">
      <div>
        <h2 class="net-title">网络配置</h2>
        <p class="net-sub">配置框架与 OneBot 实现端的连接方式，支持正向/反向 WebSocket 与 HTTP，保存后即时生效。</p>
      </div>
      <div class="net-head-actions">
        <n-button size="small" tertiary :loading="loading" @click="fetchData">
          <template #icon><SvgIcon name="refresh" :size="15" /></template>刷新
        </n-button>
        <n-button size="small" type="primary" @click="openAdd">
          <template #icon><SvgIcon name="plus" :size="15" /></template>新建
        </n-button>
      </div>
    </div>

    <div v-if="connections.length" class="net-grid">
      <div v-for="conn in connections" :key="conn.name" class="net-card" :class="{ disabled: !conn.enable }">
        <div class="net-card-top">
          <SvgIcon :name="TYPES[conn.type].icon" :size="16" class="net-card-icon" />
          <span class="net-card-name">{{ conn.name }}</span>
          <n-tag size="tiny" :bordered="false" round class="net-type-tag">{{ TYPES[conn.type].label }}</n-tag>
          <span class="net-card-spacer" />
          <n-switch size="small" :value="conn.enable" @update:value="v => toggleEnable(conn, v)" />
        </div>
        <div class="net-card-endpoint" @click="copyText(endpointOf(conn))" :title="'点击复制: ' + endpointOf(conn)">
          <SvgIcon name="link" :size="13" />
          <span class="net-ep-text">{{ endpointOf(conn) }}</span>
          <SvgIcon name="copy" :size="13" class="net-ep-copy" />
        </div>
        <div class="net-card-bottom">
          <n-tag size="small" :type="statusOf(conn).type" round>{{ statusOf(conn).text }}</n-tag>
          <span class="net-card-spacer" />
          <span v-if="conn.token" class="net-meta-item"><SvgIcon name="key" :size="12" /> Token</span>
          <span v-if="conn.type === 'ws_forward'" class="net-meta-item">重连 {{ (conn.reconnect_interval || 5000) / 1000 }}s</span>
          <n-button size="tiny" quaternary @click="openEdit(conn)"><template #icon><SvgIcon name="settings" :size="13" /></template></n-button>
          <n-button size="tiny" quaternary type="error" @click="removeConn(conn)"><template #icon><SvgIcon name="trash" :size="13" /></template></n-button>
        </div>
      </div>
    </div>
    <div v-else-if="!loading" class="net-empty">
      暂无连接，点击右上角「新建」添加一个连接
    </div>

    <n-modal v-model:show="showEdit" preset="card" :title="editIndex >= 0 ? '编辑连接' : '新建连接'" style="max-width:480px" :bordered="false">
      <n-form label-placement="top" size="small">
        <n-form-item label="连接类型">
          <n-select :value="form.type" :options="TYPE_OPTIONS" :disabled="editIndex >= 0" @update:value="onTypeChange" />
        </n-form-item>
        <p class="net-form-desc">{{ TYPES[form.type].desc }}</p>
        <n-form-item label="名称（唯一）">
          <n-input v-model:value="form.name" placeholder="连接名称" />
        </n-form-item>

        <template v-if="TYPES[form.type].mode === 'client'">
          <n-form-item :label="form.type === 'ws_forward' ? 'WebSocket 地址' : 'HTTP API 地址'">
            <n-input v-model:value="form.url" :placeholder="form.type === 'ws_forward' ? 'ws://127.0.0.1:3001' : 'http://127.0.0.1:3000'" />
          </n-form-item>
          <n-form-item v-if="form.type === 'ws_forward'" label="重连间隔 (毫秒)">
            <n-input-number v-model:value="form.reconnect_interval" :min="1000" :step="1000" style="width:100%" />
          </n-form-item>
        </template>

        <template v-else>
          <n-form-item label="监听地址 (host)">
            <n-input v-model:value="form.host" placeholder="0.0.0.0" />
          </n-form-item>
          <n-form-item label="监听端口 (port)">
            <n-input-number v-model:value="form.port" :min="1" :max="65535" style="width:100%" />
          </n-form-item>
          <p class="net-form-desc">与面板端口 ({{ server.port }}) 相同时复用主服务；填写不同端口则独立监听 (适用于容器部署)。</p>
          <n-form-item label="路径">
            <n-input v-model:value="form.path" placeholder="/OneBotv11" />
          </n-form-item>
        </template>

        <n-form-item label="Access Token（可选）">
          <n-input v-model:value="form.token" type="password" show-password-on="click" placeholder="鉴权 token，留空则不校验" />
        </n-form-item>
        <n-form-item v-if="form.type === 'http_server'" label="Secret（HTTP 上报签名，可选）">
          <n-input v-model:value="form.secret" type="password" show-password-on="click" placeholder="HMAC-SHA1 签名密钥" />
        </n-form-item>
      </n-form>
      <template #footer>
        <div style="display:flex;justify-content:flex-end;gap:8px">
          <n-button size="small" @click="showEdit = false">取消</n-button>
          <n-button size="small" type="primary" :loading="saving" @click="confirmEdit">保存</n-button>
        </div>
      </template>
    </n-modal>
  </div>
</template>

<style scoped>
.net-page { padding: 4px 2px 24px }
.net-head { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; margin-bottom:18px }
.net-head-actions { display:flex; gap:8px; flex-shrink:0 }
.net-title { font-size:18px; font-weight:600; margin:0 }
.net-sub { margin:4px 0 0; font-size:12.5px; color:var(--text-secondary); line-height:1.5; max-width:680px }
.net-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:12px }
.net-card { border:1px solid var(--border,rgba(128,128,128,.2)); border-radius:10px; padding:12px 14px; background:var(--card-bg,rgba(128,128,128,.04)); transition:border-color .15s }
.net-card:hover { border-color:var(--accent,#5865f2) }
.net-card.disabled { opacity:.62 }
.net-card-top { display:flex; align-items:center; gap:8px }
.net-card-icon { color:var(--accent,#5865f2); flex-shrink:0 }
.net-card-name { font-weight:600; font-size:13.5px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
.net-type-tag { background:rgba(88,101,242,.12); color:var(--accent,#5865f2) }
.net-card-spacer { flex:1 }
.net-card-endpoint { display:flex; align-items:center; gap:6px; margin-top:9px; padding:5px 8px; border-radius:7px; background:rgba(128,128,128,.1); font-size:12px; font-family:monospace; cursor:pointer; color:var(--text-secondary) }
.net-card-endpoint:hover { color:var(--text) }
.net-ep-text { flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis }
.net-ep-copy { opacity:.5 }
.net-card-bottom { display:flex; align-items:center; gap:8px; margin-top:10px }
.net-meta-item { display:flex; align-items:center; gap:3px; font-size:11px; color:var(--text-secondary) }
.net-form-desc { margin:-6px 0 10px; font-size:11.5px; color:var(--text-secondary) }
.net-empty { font-size:12.5px; color:var(--text-secondary); padding:32px; text-align:center; border:1px dashed var(--border,rgba(128,128,128,.25)); border-radius:10px }
</style>
