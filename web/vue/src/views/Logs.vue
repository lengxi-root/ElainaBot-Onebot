<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useAppStore } from '../stores/app'
import { on, off } from '../utils/ws'
import axios from '../utils/axios'

const app = useAppStore()
const MAX = 500
const TABS = [
  { key: 'message', label: '消息' }, { key: 'lifecycle', label: '事件' },
  { key: 'framework', label: '框架' }, { key: 'error', label: '错误' },
  { key: 'login', label: '登录日志' },
]
const tab = ref('message')
const autoScroll = ref(true)
const messages = ref([]), framework = ref([]), errors = ref([]), lifecycle = ref([]), logins = ref([])
const logContainer = ref(null)
const expandedRaw = ref({})
const expandedErr = ref({})
const expandedMsg = ref({})

function escapeHtml(s) {
  return s ? s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<span class="t-nl">↵</span>') : ''
}
function fmtMsgContent(s) {
  if (!s) return ''
  const ki = s.indexOf('\n[keyboard] ')
  if (ki === -1) return escapeHtml(s)
  const body = s.slice(ki + 12)
  let short = body
  if (body.startsWith('{')) {
    try { const kb = JSON.parse(body); const rows = kb?.content?.rows || []; short = rows.flatMap(r => (r.buttons||[]).map(b => b?.render_data?.label || '?')).join(' | ') } catch {}
  }
  return escapeHtml(s.slice(0, ki)) + '<span class="t-nl">↵</span>[keyboard] ' + escapeHtml(short)
}
function toggleMsg(i) { expandedMsg.value[i] = !expandedMsg.value[i] }
function toggleErr(i, type) { expandedErr.value[i] = expandedErr.value[i] === type ? null : type }
function fmtJson(s) { if (!s) return ''; try { return JSON.stringify(JSON.parse(s), null, 2) } catch { return s } }
function fmtCtx(v) { if (!v) return '无'; if (typeof v === 'string') try { return JSON.stringify(JSON.parse(v), null, 2) } catch { return v } return JSON.stringify(v, null, 2) }

const filteredMessages = computed(() => app.currentBotId ? messages.value.filter(m => m.appid === app.currentBotId) : messages.value)
const filteredLifecycle = computed(() => app.currentBotId ? lifecycle.value.filter(m => m.appid === app.currentBotId) : lifecycle.value)
const currentLogs = computed(() =>
  tab.value === 'message' ? filteredMessages.value
  : tab.value === 'framework' ? framework.value
  : tab.value === 'lifecycle' ? filteredLifecycle.value
  : tab.value === 'login' ? logins.value
  : errors.value
)

function pushLog(type, entry) {
  const arr = type === 'message' ? messages : type === 'framework' ? framework : (type === 'lifecycle' || type === 'event') ? lifecycle : errors
  arr.value.push(entry)
  if (arr.value.length > MAX) arr.value.splice(0, arr.value.length - MAX)
}
function onNewLog(data) { if (!data) return; const t = data.log_type || 'message'; const e = { ...data }; delete e.log_type; pushLog(t, e) }
function onInit() { if (!messages.value.length) fetchLogs() }
function clearAll() { messages.value = []; framework.value = []; errors.value = []; lifecycle.value = []; logins.value = []; expandedRaw.value = {}; expandedErr.value = {}; expandedMsg.value = {} }

async function fetchLogs() {
  try {
    const res = await axios.get('/api/logs/recent')
    if (res.data.message) messages.value = res.data.message
    if (res.data.framework) framework.value = res.data.framework
    if (res.data.error) errors.value = res.data.error
    if (res.data.lifecycle) lifecycle.value = res.data.lifecycle
  } catch {}
  fetchLoginLogs()
}
async function fetchLoginLogs() {
  try {
    const res = await axios.get('/api/logs/login')
    if (res.data.data) logins.value = res.data.data.map(r => ({ ...r, timestamp: r.last_access ? r.last_access.replace('T', ' ').slice(0, 19) : '' }))
  } catch {}
}

watch(currentLogs, async () => {
  if (autoScroll.value) { await nextTick(); const el = logContainer.value; if (el) el.scrollTop = el.scrollHeight }
}, { deep: true })

onMounted(() => { fetchLogs(); on('new_log', onNewLog); on('init', onInit) })
onUnmounted(() => { off('new_log', onNewLog); off('init', onInit) })
</script>

<template>
  <div class="log-page">
    <div class="log-toolbar">
      <div class="log-tabs">
        <button v-for="t in TABS" :key="t.key" :class="['tab-btn', { active: tab === t.key }]" @click="tab = t.key">{{ t.label }}</button>
      </div>
      <div class="log-actions">
        <label class="auto-label"><input type="checkbox" v-model="autoScroll" /> 自动滚动 </label>
        <button class="tool-btn" @click="clearAll">清空</button>
      </div>
    </div>
    <div class="terminal" ref="logContainer">
      <div v-if="!currentLogs.length" class="term-empty">等待日志...</div>
      <div v-for="(e, i) in currentLogs" :key="i" class="term-line">
        <!-- message -->
        <template v-if="tab === 'message'">
          <span class="t-time">{{ e.timestamp }}</span>
          <span v-if="e.bot_name" class="t-bot">[{{ e.bot_name }}]</span>
          <span v-if="e.direction === 'send'" class="t-dir t-dir-send">发送</span>
          <span v-else-if="e.direction === 'receive'" class="t-dir t-dir-recv">接收</span>
          <span v-if="e.user_id" class="t-uid">U:{{ e.user_id }}</span>
          <span v-if="e.group_id" class="t-gid">G:{{ e.group_id }}</span>
          <span class="t-content" v-html="fmtMsgContent(e.content)" />
          <span v-if="e.raw_message" :class="['t-expand-btn', { active: expandedMsg[i] }]" @click="toggleMsg(i)">原始事件</span>
          <div v-if="expandedMsg[i] && e.raw_message" class="t-detail"><pre class="t-traceback">{{ fmtJson(e.raw_message) }}</pre></div>
        </template>
        <!-- framework -->
        <template v-else-if="tab === 'framework'">
          <span class="t-time">{{ e.timestamp }}</span>
          <span :class="['t-level', (e.level || 'INFO').toLowerCase()]">{{ e.level || 'INFO' }}</span>
          <span v-if="e.source" class="t-source">[{{ e.source }}]</span>
          <span class="t-content">{{ e.content || e.message || '' }}</span>
        </template>
        <!-- lifecycle -->
        <template v-else-if="tab === 'lifecycle'">
          <span class="t-time">{{ e.timestamp }}</span>
          <span v-if="e.bot_name" class="t-bot">[{{ e.bot_name }}({{ e.appid || '?' }})]</span>
          <span :class="['t-lc-type', 't-lc-' + (e.event_type || e.type || '')]">{{ { group_add:'入群', group_del:'退群', group_member_add:'用户入群', group_member_del:'用户退群', friend_add:'加好友', friend_del:'删好友', group_msg_reject:'关闭主动消息', group_msg_receive:'开启主动消息', MESSAGE_REACTION_ADD:'表态', MESSAGE_REACTION_REMOVE:'取消表态', GUILD_UPDATE:'频道更新' }[e.event_type || e.type] || e.event_type || e.type }}</span>
          <span v-if="e.user_id" class="t-uid">U:{{ e.user_id }}</span>
          <span v-if="e.group_id" class="t-gid">G:{{ e.group_id }}</span>
          <span v-if="e.raw_message || e.content" :class="['t-expand-btn', { active: expandedRaw[i] }]" @click="expandedRaw[i] = !expandedRaw[i]">原始响应</span>
          <div v-if="expandedRaw[i] && (e.raw_message || e.content)" class="t-detail"><pre class="t-traceback">{{ fmtJson(e.raw_message || e.content) }}</pre></div>
        </template>
        <!-- login -->
        <template v-else-if="tab === 'login'">
          <span class="t-time">{{ e.timestamp }}</span>
          <span class="t-login-ip">{{ e.ip }}</span>
          <span :class="['t-login-status', e.is_banned ? 'banned' : 'ok']">{{ e.is_banned ? '已封禁' : '正常' }}</span>
          <span v-if="e.fail_count" class="t-login-fail">失败 {{ e.fail_count }} 次</span>
          <span v-if="e.first_access" class="t-login-first">首次: {{ e.first_access.replace('T',' ').slice(0,19) }}</span>
        </template>
        <!-- error -->
        <template v-else>
          <span class="t-time">{{ e.timestamp }}</span>
          <span class="t-level error">ERROR</span>
          <span v-if="e.appid && e.appid !== '0000'" class="t-appid">({{ e.appid }})</span>
          <span v-if="e.module_type || e.module_name" class="t-source"> [{{ [e.module_type, e.module_name].filter(Boolean).join(':') }}] </span>
          <div class="t-err-actions">
            <span :class="['t-expand-btn', { active: expandedErr[i] === 'raw' }]" @click="toggleErr(i, 'raw')">原始消息</span>
            <span :class="['t-expand-btn', { active: expandedErr[i] === 'payload' }]" @click="toggleErr(i, 'payload')">发送内容</span>
            <span :class="['t-expand-btn', { active: expandedErr[i] === 'resp' }]" @click="toggleErr(i, 'resp')">响应对象</span>
          </div>
          <div v-if="expandedErr[i]" class="t-detail">
            <pre v-if="expandedErr[i] === 'raw'" class="t-traceback">{{ e.content || '无' }}</pre>
            <pre v-else-if="expandedErr[i] === 'payload'" class="t-traceback">{{ fmtCtx(e.context) }}</pre>
            <pre v-else-if="expandedErr[i] === 'resp'" class="t-traceback">{{ e.traceback || '无' }}</pre>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.log-page {
  display:flex;
  flex-direction:column;
  height:calc(100vh - 100px)
}
.log-toolbar {
  display:flex;
  align-items:center;
  justify-content:space-between;
  margin-bottom:8px;
  flex-wrap:wrap;
  gap:8px
}
.log-tabs {
  display:flex;
  gap:2px
}
.tab-btn {
  padding:5px 14px;
  border:1px solid var(--border);
  border-radius:4px;
  background:transparent;
  color:var(--text2);
  cursor:pointer;
  font-size:13px
}
.tab-btn:hover {
  color:var(--text);
  border-color:var(--text3)
}
.tab-btn.active {
  background:var(--accent);
  color:#fff;
  border-color:var(--accent)
}
.log-actions {
  display:flex;
  align-items:center;
  gap:10px
}
.auto-label {
  color:var(--text2);
  font-size:12px;
  cursor:pointer;
  display:flex;
  align-items:center;
  gap:4px
}
.auto-label input {
  accent-color:var(--accent)
}
.tool-btn {
  padding:4px 10px;
  border:1px solid var(--border);
  border-radius:4px;
  background:transparent;
  color:var(--text2);
  cursor:pointer;
  font-size:12px
}
.tool-btn:hover {
  color:var(--text);
  border-color:var(--text3)
}
.terminal {
  flex:1;
  min-height:0;
  overflow-y:auto;
  background:var(--bg3);
  border:1px solid var(--border);
  border-radius:6px;
  font-family:Cascadia Code,Fira Code,Consolas,Monaco,monospace;
  font-size:13px;
  line-height:1.7;
  padding:6px 0
}
.term-empty {
  color:var(--text3);
  text-align:center;
  padding:40px 0
}
.term-line {
  padding:1px 12px;
  white-space:pre-wrap;
  word-break:break-all
}
.term-line:hover {
  background:#5865f20f
}
.t-time {
  color:var(--text3);
  margin-right:6px
}
.t-bot {
  color:var(--info);
  margin-right:4px
}
.t-appid {
  color:var(--text3);
  margin-right:6px;
  font-size:12px
}
.t-uid {
  color:var(--success);
  margin-right:6px
}
.t-gid {
  color:var(--warning);
  margin-right:6px
}
.t-content {
  color:var(--text)
}
.t-nl {
  color:var(--text3);
  font-size:10px;
  margin:0 1px;
  opacity:.6
}
.t-dir {
  font-size:10px;
  padding:0 4px;
  border-radius:3px;
  margin-right:4px;
  font-weight:600;
  line-height:16px;
  display:inline-block
}
.t-dir-send {
  color:#2e7d32;
  background:#e8f5e9
}
.t-dir-recv {
  color:#1565c0;
  background:#e3f2fd
}
.t-level {
  padding:0 4px;
  border-radius:3px;
  margin-right:6px;
  font-size:11px;
  font-weight:600
}
.t-level.info {
  color:var(--info)
}
.t-level.debug {
  color:var(--text3)
}
.t-level.warning {
  color:var(--warning)
}
.t-level.error {
  color:var(--danger)
}
.t-level.critical {
  color:#fff;
  background:var(--danger)
}
.t-source {
  color:var(--text2);
  margin-right:6px
}
.t-err {
  color:var(--danger)
}
.t-expand-btn {
  color:var(--accent);
  font-size:11px;
  margin-left:8px;
  cursor:pointer;
  border:1px solid var(--accent);
  border-radius:3px;
  padding:0 4px;
  -webkit-user-select:none;
  -moz-user-select:none;
  user-select:none;
  white-space:nowrap
}
.t-expand-btn:hover,.t-expand-btn.active {
  background:var(--accent);
  color:#fff
}
.t-detail {
  margin:4px 0 2px 20px;
  padding:0;
  border-radius:6px;
  overflow:hidden
}
.t-ctx {
  margin-bottom:6px
}
.t-ctx-item {
  display:flex;
  gap:6px;
  font-size:12px;
  line-height:1.6
}
.t-ctx-key {
  color:var(--warning);
  font-weight:600;
  flex-shrink:0
}
.t-ctx-val {
  color:var(--text);
  word-break:break-all
}
.t-traceback {
  margin:0;
  padding:10px 12px;
  font-size:12px;
  line-height:1.6;
  background:#1e1e1e;
  border-radius:6px;
  color:#d4d4d4;
  font-family:Cascadia Code,Fira Code,Consolas,monospace;
  white-space:pre-wrap;
  word-break:break-all;
  max-height:300px;
  overflow-y:auto
}
.t-err-actions {
  display:inline-flex;
  gap:4px;
  margin-left:6px
}
.t-lc-type {
  font-size:11px;
  padding:0 5px;
  border-radius:3px;
  margin-right:6px;
  font-weight:600;
  display:inline-block
}
.t-lc-group_add {
  color:#1b5e20;
  background:#e8f5e9
}
.t-lc-group_del {
  color:#b71c1c;
  background:#ffebee
}
.t-lc-group_member_add {
  color:#00695c;
  background:#e0f2f1
}
.t-lc-group_member_del {
  color:#880e4f;
  background:#fce4ec
}
.t-lc-friend_add {
  color:#1565c0;
  background:#e3f2fd
}
.t-lc-friend_del {
  color:#e65100;
  background:#fff3e0
}
.t-lc-group_msg_reject {
  color:#bf360c;
  background:#fbe9e7
}
.t-lc-group_msg_receive {
  color:#6a1b9a;
  background:#f3e5f5
}
.t-lc-MESSAGE_REACTION_ADD {
  color:#283593;
  background:#e8eaf6
}
.t-lc-MESSAGE_REACTION_REMOVE {
  color:#455a64;
  background:#eceff1
}
.t-lc-GUILD_UPDATE {
  color:#00838f;
  background:#e0f7fa
}
.t-login-ip {
  color:var(--accent);
  font-weight:600;
  margin-right:8px
}
.t-login-status {
  font-size:11px;
  padding:0 5px;
  border-radius:3px;
  font-weight:600;
  margin-right:6px
}
.t-login-status.ok {
  color:#2e7d32;
  background:#e8f5e9
}
.t-login-status.banned {
  color:#c62828;
  background:#ffebee
}
.t-login-fail {
  color:var(--warning);
  font-size:12px;
  margin-right:6px
}
.t-login-first {
  color:var(--text2);
  font-size:11px
}
@media(max-width:767px) {
  .terminal {
  font-size:11px;
  -webkit-overflow-scrolling:touch
}
.log-toolbar {
  flex-direction:column;
  align-items:stretch;
  gap:8px
}
.log-toolbar > * {
  width:100%
}
}
</style>
