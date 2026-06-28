<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useMessage } from 'naive-ui'
import yaml from 'js-yaml'
import axios from '../utils/axios'
import SvgIcon from '../components/SvgIcon.vue'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const dirty = ref(false)
const activeFile = ref('settings')
const viewMode = ref('visual')
const raw = reactive({ bot: '', settings: '', templates: '' })
const botIndex = ref(0)
const buttonTexts = reactive({})

const TABS = [
  { key: 'settings', label: 'settings.yaml' },
]

const VARIABLES = ['{user_id}', '{user_count}', '{reason}', '{error_code}', '{error_message}', '{appid}', '{group_id}']

const TEMPLATE_LABELS = {
  welcome: '群欢迎 (机器人被邀请入群)',
  user_welcome: '新用户首次交互',
  friend_add: '添加好友自动回复',
  group_only: '群聊专用命令提示',
  default: '无匹配命令时的默认回复',
  owner_only: '仅主人可用命令提示',
  maintenance: '维护模式提示',
  blacklist: '用户黑名单提示',
  group_blacklist: '群黑名单提示',
  api_error: 'API 错误提示',
}

function parse(text) { try { return yaml.load(text) || {} } catch { return {} } }
function dump(obj) { try { return yaml.dump(obj, { lineWidth: -1, noRefs: true, sortKeys: false, quotingType: '"' }) } catch { return '' } }

function _ys(v) { if (v == null) return 'null'; if (typeof v === 'boolean') return v ? 'true' : 'false'; if (typeof v === 'number') return String(v); if (typeof v !== 'string') return String(v); if (!v) return "''"; if (v === '|') return "'|'"; if (v.includes('\n')) return '"' + v.replace(/\\/g,'\\\\').replace(/"/g,'\\"').replace(/\n/g,'\\n') + '"'; if (/[:#[\]{}|>&*!?,'"\\ ]/.test(v) || v[0] === ' ' || v[0] === '-' || v.endsWith(' ')) return '"' + v.replace(/\\/g,'\\\\').replace(/"/g,'\\"') + '"'; return v }
function _serBtns(btns) { return '[' + btns.map(r => Array.isArray(r) ? '[' + r.filter(b => b && typeof b === 'object').map(b => '{' + Object.entries(b).map(([k,v]) => k+': '+_ys(v)).join(', ') + '}').join(',') + ']' : '').join(',') + ']' }
function _multiline(v, indent) { const pad = '  '.repeat(indent); const ls = []; v.replace(/\n$/, '').split('\n').forEach(ln => ls.push(ln.trim() ? pad + ln : '')); return ls }
function _serVal(k, v, indent) { if (k === 'buttons' && Array.isArray(v)) return ['  '.repeat(indent) + k + ': ' + _serBtns(v)]; if (typeof v === 'string' && v.includes('\n')) return ['  '.repeat(indent) + k + ': |', ..._multiline(v, indent + 1)]; return ['  '.repeat(indent) + k + ': ' + _ys(v)] }
function dumpTemplates(obj) {
  const lines = []
  for (const [key, val] of Object.entries(obj)) {
    if (val == null) continue
    if (typeof val === 'string') { if (val.includes('\n')) { lines.push(key + ': |', ..._multiline(val, 1)) } else { lines.push(key + ': ' + _ys(val)) }; lines.push(''); continue }
    if (Array.isArray(val)) { lines.push(key + ':'); val.forEach(item => { if (typeof item !== 'object') return; let first = true; for (const [k,v] of Object.entries(item)) { const pfx = first ? '  - ' : '    '; first = false; if (k === 'buttons' && Array.isArray(v)) { lines.push(pfx + k + ': ' + _serBtns(v)) } else if (typeof v === 'string' && v.includes('\n')) { lines.push(pfx + k + ': |'); _multiline(v, 3).forEach(ln => lines.push(ln)) } else { lines.push(pfx + k + ': ' + _ys(v)) } } }); lines.push(''); continue }
    if (typeof val === 'object') { lines.push(key + ':'); for (const [k,v] of Object.entries(val)) _serVal(k, v, 1).forEach(ln => lines.push(ln)); lines.push(''); continue }
    lines.push(key + ': ' + _ys(val), '')
  }
  return lines.join('\n')
}

function dumpBot(obj) {
  let r = dump(obj)
  r = r.replace(/^(bots:)/m, '# ===== 机器人配置 =====\n# 支持多机器人，每个机器人独立配置\n# 修改后自动热加载，无需重启\n\n$1')
    .replace(/^(\s+)(websocket:)/gm, '$1# WebSocket 连接配置\n$1$2')
    .replace(/^(\s+)(message:)/gm, '$1# 消息处理\n$1$2')
    .replace(/^(\s+)(identity:)/gm, '$1# 用户ID模式\n$1$2')
    .replace(/^(\s+)(welcome:)/gm, '$1# 欢迎消息\n$1$2')
    .replace(/^(\s+)(maintenance:)/gm, '$1# 维护模式\n$1$2')
    .replace(/^(\s+)(dedup:)/gm, '$1# 事件去重\n$1$2')
    .replace(/^(\s+)(blacklist:)/gm, '$1# 黑名单\n$1$2')
  return r
}

// Computed
const bots = computed(() => {
  const d = parse(raw.bot)
  const list = Array.isArray(d?.bots) ? d.bots : []
  if (botIndex.value >= list.length) botIndex.value = 0
  return list
})
const currentBot = computed(() => bots.value[botIndex.value] || null)
const settings = computed(() => parse(raw.settings))
const templates = computed(() => parse(raw.templates))
const templateKeys = computed(() => Object.keys(templates.value).filter(k => !k.startsWith('#')))

// Bot config helpers
function updateBotField(idx, field, event) {
  const d = parse(raw.bot)
  if (!d.bots?.[idx]) return
  d.bots[idx][field] = field === 'owner_ids'
    ? event.target.value.split(',').map(s => s.trim()).filter(Boolean)
    : event.target.value
  raw.bot = dumpBot(d); dirty.value = true
}

function updateBotNested(idx, section, key, value) {
  const d = parse(raw.bot)
  if (!d.bots?.[idx]) return
  if (!d.bots[idx][section]) d.bots[idx][section] = {}
  d.bots[idx][section][key] = value
  raw.bot = dumpBot(d); dirty.value = true
}

function updateBotNestedStr(idx, section, key, event) { updateBotNested(idx, section, key, event.target.value) }
function updateBotNestedNum(idx, section, key, event) { updateBotNested(idx, section, key, parseInt(event.target.value) || 0) }
function updateBotNestedList(idx, section, key, event) { updateBotNested(idx, section, key, event.target.value.split(',').map(s => s.trim()).filter(Boolean)) }

function addBot() {
  const d = parse(raw.bot)
  if (!Array.isArray(d.bots)) d.bots = []
  d.bots.push({
    appid: '', secret: '', robot_qq: '', owner_ids: [],
    websocket: { enabled: true, custom_url: '', reconnect_interval: 5, max_reconnects: -1, log_level: 'INFO' },
    message: { use_markdown: true, markdown_suffix: '', button_enter_to_send: false, send_default_response: false, default_response_excluded_regex: [] },
    identity: { use_union_id_for_group: false, use_union_id_for_channel: false },
    welcome: { group_welcome: false, new_user_welcome: false, friend_add_message: false },
    maintenance: { enabled: false, reply: true },
    dedup: { enabled: false },
    blacklist: { user_enabled: false, group_enabled: false, user_list: [], group_list: [] },
    non_at_message: { enabled: false, group_whitelist: [], ignore_at_other_bot: true, ignore_at_other_user: true, ignore_bot_sender: false, quiet_at_self: false, strip_bot_name_at: false },
  })
  raw.bot = dumpBot(d); botIndex.value = d.bots.length - 1; dirty.value = true
}

function removeBot() {
  if (!confirm(`确定删除机器人 #${botIndex.value + 1}？`)) return
  const d = parse(raw.bot)
  if (!d.bots?.[botIndex.value]) return
  d.bots.splice(botIndex.value, 1)
  raw.bot = dumpBot(d)
  if (botIndex.value >= d.bots.length) botIndex.value = Math.max(0, d.bots.length - 1)
  dirty.value = true
}

// Settings helpers
function updateSetting(section, key, event) {
  const d = parse(raw.settings)
  if (!d[section]) d[section] = {}
  d[section][key] = event.target.value
  raw.settings = dump(d); dirty.value = true
}

function updateSettingNum(section, key, event) {
  const d = parse(raw.settings)
  if (!d[section]) d[section] = {}
  d[section][key] = parseInt(event.target.value) || 0
  raw.settings = dump(d); dirty.value = true
}

function updateSettingBool(section, key, event) {
  const d = parse(raw.settings)
  if (!d[section]) d[section] = {}
  d[section][key] = event.target.checked
  raw.settings = dump(d); dirty.value = true
}

function updateSettingList(section, key, event) {
  const d = parse(raw.settings)
  if (!d[section]) d[section] = {}
  d[section][key] = event.target.value.split(',').map(s => s.trim()).filter(Boolean)
  raw.settings = dump(d); dirty.value = true
}

// Template helpers
function getTemplateField(key, field) {
  const t = templates.value[key]
  if (!t) return ''
  return typeof t === 'string' ? (field === 'markdown' ? t : '') : (t[field] || '')
}

function updateTemplateField(key, field, event) {
  const d = parse(raw.templates)
  let t = d[key]
  if (typeof t === 'string') { d[key] = { markdown: t }; t = d[key] }
  else if (!t || typeof t !== 'object') { d[key] = {}; t = d[key] }
  t[field] = event.target.value
  raw.templates = dumpTemplates(d); dirty.value = true
}

function getButtons(key) {
  const t = templates.value[key]
  if (!t || typeof t === 'string' || !t.buttons) return ''
  try {
    const d = yaml.dump(t.buttons, { lineWidth: -1, noRefs: true, flowLevel: 0 }).trim()
    return d.startsWith('[') ? d.slice(1, -1) : d
  } catch { return '' }
}

function syncButtonTexts() {
  for (const key of templateKeys.value) {
    if (!(key in buttonTexts)) buttonTexts[key] = getButtons(key)
  }
}

function updateButtonText(key, event) {
  buttonTexts[key] = event.target.value
  dirty.value = true
}

function commitButtons(key) {
  const d = parse(raw.templates)
  let t = d[key]
  if (typeof t === 'string') { d[key] = { markdown: t }; t = d[key] }
  else if (!t || typeof t !== 'object') { d[key] = {}; t = d[key] }
  const val = (buttonTexts[key] || '').trim()
  if (!val) { delete t.buttons }
  else { try { t.buttons = yaml.load('[' + val + ']') } catch {} }
  raw.templates = dumpTemplates(d)
}

// API
async function fetchConfig() {
  loading.value = true
  try {
    const res = await axios.get('/api/config')
    raw.bot = res.data.bot || ''
    raw.settings = res.data.settings || ''
    raw.templates = res.data.templates || ''
    dirty.value = false
    // 重置 buttonTexts 缓存
    Object.keys(buttonTexts).forEach(k => delete buttonTexts[k])
    syncButtonTexts()
  } catch { message.error('获取配置失败') }
  finally { loading.value = false }
}

async function saveConfig() {
  saving.value = true
  // Commit all button texts before saving templates
  if (activeFile.value === 'templates') {
    for (const key of templateKeys.value) commitButtons(key)
  }
  try {
    const res = await axios.post('/api/config/save', { file: activeFile.value, content: raw[activeFile.value] })
    if (res.data.success) { message.success('配置已保存，部分更改需要重启生效'); dirty.value = false }
    else message.error(res.data.error || '保存失败')
  } catch (e) { message.error('保存失败: ' + (e.message || '')) }
  finally { saving.value = false }
}

function switchToYaml() {
  if (activeFile.value === 'templates') { for (const key of templateKeys.value) commitButtons(key) }
  viewMode.value = 'yaml'
}

watch(templateKeys, syncButtonTexts)
onMounted(fetchConfig)
</script>

<template>
  <div class="config-page">
    <div class="config-tabs">
      <button v-for="tab in TABS" :key="tab.key" :class="['config-tab', { active: activeFile === tab.key }]" @click="activeFile = tab.key">{{ tab.label }}</button>
      <span class="config-tabs-spacer" />
      <button :class="['cfg-btn', { active: viewMode === 'visual' }]" @click="viewMode = 'visual'">可视化</button>
      <button :class="['cfg-btn', { active: viewMode === 'yaml' }]" @click="switchToYaml">YAML</button>
      <button class="cfg-btn save" @click="saveConfig" :disabled="!dirty || saving">{{ saving ? '保存中...' : '保存' }}</button>
      <button class="cfg-btn" @click="fetchConfig" :disabled="loading">刷新</button>
    </div>

    <template v-if="viewMode === 'visual'">
      <div class="visual-body">
        <!-- Bot -->
        <template v-if="activeFile === 'bot'">
          <div class="bot-picker">
            <label>选择机器人</label>
            <select v-if="bots.length" v-model="botIndex">
              <option v-for="(bot, i) in bots" :key="i" :value="i">机器人 #{{ i + 1 }} — {{ bot.appid || '新机器人' }}</option>
            </select>
            <button class="cfg-btn" style="font-size:12px;padding:4px 10px;display:flex;align-items:center;gap:3px" @click="addBot"><SvgIcon name="plus" :size="13" /> 添加</button>
            <button v-if="bots.length" class="cfg-btn" style="font-size:12px;padding:4px 10px;color:var(--danger);display:flex;align-items:center;gap:3px" @click="removeBot"><SvgIcon name="minus" :size="13" /> 删除当前</button>
          </div>
          <div v-if="currentBot" class="vis-card">
            <div class="vis-card-title">机器人 #{{ botIndex + 1 }} — {{ currentBot.appid || '新机器人' }}</div>
            <div class="vis-grid">
              <div class="vis-field"><label>AppID</label><input :value="currentBot.appid" @input="updateBotField(botIndex, 'appid', $event)" /></div>
              <div class="vis-field"><label>Secret</label><input :value="currentBot.secret" @input="updateBotField(botIndex, 'secret', $event)" type="password" /></div>
              <div class="vis-field"><label>机器人QQ</label><input :value="currentBot.robot_qq" @input="updateBotField(botIndex, 'robot_qq', $event)" /></div>
              <div class="vis-field"><label>主人 OpenID</label><input :value="(currentBot.owner_ids||[]).join(',')" @input="updateBotField(botIndex, 'owner_ids', $event)" placeholder="逗号分隔" /></div>
              <div class="vis-field"><label>第三方发信接口</label><input :value="currentBot.api_base || ''" @input="updateBotField(botIndex, 'api_base', $event)" placeholder="留空使用官方" /></div>
            </div>
            <div class="vis-section">WebSocket</div>
            <div class="vis-grid">
              <div class="vis-field"><label>启用 WS</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.websocket||{}).enabled" @change="updateBotNested(botIndex, 'websocket', 'enabled', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>自定义 WS 地址</label><input :value="(currentBot.websocket||{}).custom_url || ''" @input="updateBotNestedStr(botIndex, 'websocket', 'custom_url', $event)" /></div>
              <div class="vis-field"><label>重连间隔(秒)</label><input type="number" :value="(currentBot.websocket||{}).reconnect_interval || 5" @input="updateBotNestedNum(botIndex, 'websocket', 'reconnect_interval', $event)" /></div>
              <div class="vis-field"><label>最大重连次数</label><input type="number" :value="(currentBot.websocket||{}).max_reconnects || -1" @input="updateBotNestedNum(botIndex, 'websocket', 'max_reconnects', $event)" /></div>
              <div class="vis-field"><label>日志等级</label><select :value="(currentBot.websocket||{}).log_level || 'INFO'" @change="updateBotNested(botIndex, 'websocket', 'log_level', $event.target.value)"><option>DEBUG</option><option>INFO</option><option>WARNING</option><option>ERROR</option></select></div>
            </div>
            <div class="vis-section">消息处理</div>
            <div class="vis-grid">
              <div class="vis-field"><label>使用 Markdown</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.message||{}).use_markdown !== false" @change="updateBotNested(botIndex, 'message', 'use_markdown', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>按钮自动发送转回调</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.message||{}).button_enter_to_send" @change="updateBotNested(botIndex, 'message', 'button_enter_to_send', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>Markdown 后缀</label><input :value="(currentBot.message||{}).markdown_suffix || ''" @input="updateBotNestedStr(botIndex, 'message', 'markdown_suffix', $event)" /></div>
              <div class="vis-field"><label>排除默认回复正则</label><input :value="((currentBot.message||{}).default_response_excluded_regex||[]).join(',')" @input="updateBotNestedList(botIndex, 'message', 'default_response_excluded_regex', $event)" placeholder="逗号分隔" /></div>
              <div class="vis-field"><label>抑制其他机器人导致的默认回复</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.message||{}).suppress_bot_system_reply" @change="updateBotNested(botIndex, 'message', 'suppress_bot_system_reply', $event.target.checked)" /><span /></label></div>
            </div>
            <div class="vis-section">功能开关</div>
            <div class="vis-grid">
              <div class="vis-field"><label>默认回复</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.message||{}).send_default_response" @change="updateBotNested(botIndex, 'message', 'send_default_response', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>入群欢迎</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.welcome||{}).group_welcome" @change="updateBotNested(botIndex, 'welcome', 'group_welcome', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>新用户首次交互</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.welcome||{}).new_user_welcome" @change="updateBotNested(botIndex, 'welcome', 'new_user_welcome', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>添加好友消息</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.welcome||{}).friend_add_message" @change="updateBotNested(botIndex, 'welcome', 'friend_add_message', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>维护模式</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.maintenance||{}).enabled" @change="updateBotNested(botIndex, 'maintenance', 'enabled', $event.target.checked)" /><span /></label></div>
              <div v-if="(currentBot.maintenance||{}).enabled" class="vis-field"><label>维护时回复提示</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.maintenance||{}).reply !== false" @change="updateBotNested(botIndex, 'maintenance', 'reply', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>事件去重</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.dedup||{}).enabled" @change="updateBotNested(botIndex, 'dedup', 'enabled', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>用户黑名单</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.blacklist||{}).user_enabled" @change="updateBotNested(botIndex, 'blacklist', 'user_enabled', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>群黑名单</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.blacklist||{}).group_enabled" @change="updateBotNested(botIndex, 'blacklist', 'group_enabled', $event.target.checked)" /><span /></label></div>
            </div>
            <div v-if="(currentBot.blacklist||{}).user_enabled || (currentBot.blacklist||{}).group_enabled" class="vis-grid" style="margin-top:8px">
              <div v-if="(currentBot.blacklist||{}).user_enabled" class="vis-field"><label>用户黑名单列表</label><input :value="((currentBot.blacklist||{}).user_list||[]).join(',')" @input="updateBotNestedList(botIndex, 'blacklist', 'user_list', $event)" placeholder="OpenID, 逗号分隔" /></div>
              <div v-if="(currentBot.blacklist||{}).group_enabled" class="vis-field"><label>群黑名单列表</label><input :value="((currentBot.blacklist||{}).group_list||[]).join(',')" @input="updateBotNestedList(botIndex, 'blacklist', 'group_list', $event)" placeholder="群 OpenID, 逗号分隔" /></div>
            </div>
            <div class="vis-section">全量环境 <span style="font-weight:normal;color:var(--text-secondary);font-size:12px">开启后全量消息匹配正则插件, 不判断是否@机器人</span></div>
            <div class="vis-grid">
              <div class="vis-field"><label>未@机器人时正常响应指令</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.non_at_message||{}).enabled" @change="updateBotNested(botIndex, 'non_at_message', 'enabled', $event.target.checked)" /><span /></label></div>
              <div v-if="(currentBot.non_at_message||{}).enabled" class="vis-field"><label>是否忽略用户仅@其他机器人的消息</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.non_at_message||{}).ignore_at_other_bot" @change="updateBotNested(botIndex, 'non_at_message', 'ignore_at_other_bot', $event.target.checked)" /><span /></label></div>
              <div v-if="(currentBot.non_at_message||{}).enabled" class="vis-field"><label>是否忽略用户仅@其他用户的消息</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.non_at_message||{}).ignore_at_other_user" @change="updateBotNested(botIndex, 'non_at_message', 'ignore_at_other_user', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>屏蔽其他机器人发送的消息</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.non_at_message||{}).ignore_bot_sender" @change="updateBotNested(botIndex, 'non_at_message', 'ignore_bot_sender', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>用户@机器人时抑制默认回复</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.non_at_message||{}).quiet_at_self" @change="updateBotNested(botIndex, 'non_at_message', 'quiet_at_self', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>匹配前剥离开头@机器人名称</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.non_at_message||{}).strip_bot_name_at" @change="updateBotNested(botIndex, 'non_at_message', 'strip_bot_name_at', $event.target.checked)" /><span /></label></div>
            </div>
            <div v-if="!(currentBot.non_at_message||{}).enabled" class="vis-grid" style="margin-top:8px">
              <div class="vis-field"><label>群白名单</label><input :value="((currentBot.non_at_message||{}).group_whitelist||[]).join(',')" @input="updateBotNestedList(botIndex, 'non_at_message', 'group_whitelist', $event)" placeholder="群 OpenID, 逗号分隔 (仅白名单群触发插件)" /></div>
            </div>
            <div class="vis-section">用户 ID 模式</div>
            <div class="vis-grid">
              <div class="vis-field"><label>群聊使用 union_openid</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.identity||{}).use_union_id_for_group" @change="updateBotNested(botIndex, 'identity', 'use_union_id_for_group', $event.target.checked)" /><span /></label></div>
              <div class="vis-field"><label>频道使用 union_openid</label><label class="vis-switch"><input type="checkbox" :checked="(currentBot.identity||{}).use_union_id_for_channel" @change="updateBotNested(botIndex, 'identity', 'use_union_id_for_channel', $event.target.checked)" /><span /></label></div>
            </div>
          </div>
        </template>

        <!-- Settings -->
        <div v-if="activeFile === 'settings'" class="vis-card">
          <div class="vis-card-title">HTTP 服务器</div>
          <div class="vis-grid">
            <div class="vis-field"><label>监听地址</label><input :value="settings.server?.host || '0.0.0.0'" @input="updateSetting('server', 'host', $event)" /></div>
            <div class="vis-field"><label>端口</label><input type="number" :value="settings.server?.port || 5201" @input="updateSettingNum('server', 'port', $event)" /></div>
          </div>
          <div class="vis-card-title" style="margin-top:14px">主人配置</div>
          <div class="vis-grid">
            <div class="vis-field full"><label>主人 QQ 号</label><input :value="(settings.owner?.ids || []).join(',')" @input="updateSettingList('owner', 'ids', $event)" placeholder="多个用逗号分隔" /></div>
          </div>
          <div class="vis-card-title" style="margin-top:14px">OneBot 协议</div>
          <div class="vis-grid">
            <div class="vis-field"><label>默认鉴权 Token</label><input :value="settings.onebot?.access_token || ''" @input="updateSetting('onebot', 'access_token', $event)" placeholder="连接未单独配置时使用" /></div>
            <div class="vis-field"><label>HTTP 上报签名密钥</label><input :value="settings.onebot?.secret || ''" @input="updateSetting('onebot', 'secret', $event)" placeholder="可选" /></div>
            <div class="vis-field full" style="font-size:12px;color:var(--text-secondary)">网络连接（正向/反向 WS、HTTP）请在「网络配置」页面管理</div>
          </div>
          <div class="vis-card-title" style="margin-top:14px">Web 面板</div>
          <div class="vis-grid">
            <div class="vis-field"><label>管理密码</label><input :value="settings.web?.admin_password || ''" @input="updateSetting('web', 'admin_password', $event)" type="password" /></div>
            <div class="vis-field"><label>框架名称</label><input :value="settings.web?.framework_name || 'Elaina'" @input="updateSetting('web', 'framework_name', $event)" /></div>
            <div class="vis-field"><label>图标 URL</label><input :value="settings.web?.favicon_url || ''" @input="updateSetting('web', 'favicon_url', $event)" /></div>
            <div class="vis-field"><label>PC 标题后缀</label><input :value="settings.web?.pc_title_suffix || ''" @input="updateSetting('web', 'pc_title_suffix', $event)" /></div>
            <div class="vis-field"><label>登录标题后缀</label><input :value="settings.web?.login_title_suffix || ''" @input="updateSetting('web', 'login_title_suffix', $event)" /></div>
          </div>
          <div class="vis-card-title" style="margin-top:14px">日志</div>
          <div class="vis-grid">
            <div class="vis-field"><label>日志等级</label><select :value="settings.logging?.level || 'INFO'" @change="updateSetting('logging', 'level', $event)"><option>DEBUG</option><option>INFO</option><option>WARNING</option><option>ERROR</option></select></div>
            <div class="vis-field"><label>日志目录</label><input :value="settings.logging?.dir || 'log'" @input="updateSetting('logging', 'dir', $event)" /></div>
            <div class="vis-field"><label>写入间隔(秒)</label><input type="number" :value="settings.logging?.insert_interval ?? 2" @input="updateSettingNum('logging', 'insert_interval', $event)" /></div>
            <div class="vis-field"><label>批量写入条数</label><input type="number" :value="settings.logging?.batch_size ?? 0" @input="updateSettingNum('logging', 'batch_size', $event)" /></div>
            <div class="vis-field"><label>保留天数</label><input type="number" :value="settings.logging?.retention_days ?? 5" @input="updateSettingNum('logging', 'retention_days', $event)" /></div>
            <div class="vis-field full"><label>WAL 模式</label><label class="vis-switch"><input type="checkbox" :checked="settings.logging?.wal_mode !== false" @change="updateSettingBool('logging', 'wal_mode', $event)" /><span /></label></div>
          </div>
          <div class="vis-card-title" style="margin-top:14px">依赖管理</div>
          <div class="vis-grid">
            <div class="vis-field full"><label>自动安装依赖</label><label class="vis-switch"><input type="checkbox" :checked="settings.pip?.auto_install !== false" @change="updateSettingBool('pip', 'auto_install', $event)" /><span /></label></div>
            <div class="vis-field"><label>pip 镜像源</label><input :value="settings.pip?.mirror || ''" @input="updateSetting('pip', 'mirror', $event)" placeholder="留空用默认" /></div>
          </div>
          <div class="vis-card-title" style="margin-top:14px">定时重启</div>
          <div class="vis-grid">
            <div class="vis-field full"><label>启用</label><label class="vis-switch"><input type="checkbox" :checked="settings.restart?.enabled" @change="updateSettingBool('restart', 'enabled', $event)" /><span /></label></div>
            <div class="vis-field"><label>模式</label><select :value="settings.restart?.mode || 'daily'" @change="updateSetting('restart', 'mode', $event)"><option value="daily">每天固定时间</option><option value="interval">每隔 N 小时</option></select></div>
            <div v-if="(settings.restart?.mode || 'daily') === 'daily'" class="vis-field"><label>重启时间</label><input :value="settings.restart?.daily_time || '04:00'" @input="updateSetting('restart', 'daily_time', $event)" placeholder="HH:MM" /></div>
            <div v-if="settings.restart?.mode === 'interval'" class="vis-field"><label>间隔小时</label><input type="number" :value="settings.restart?.interval_hours || 24" @input="updateSettingNum('restart', 'interval_hours', $event)" min="1" /></div>
          </div>
          <div class="vis-card-title" style="margin-top:14px">统计</div>
          <div class="vis-grid">
            <div class="vis-field full"><label>开启统计</label><label class="vis-switch"><input type="checkbox" :checked="settings.statistics?.enabled !== false" @change="updateSettingBool('statistics', 'enabled', $event)" /><span /></label></div>
            <div class="vis-field"><label>每日统计-时</label><input type="number" :value="settings.statistics?.schedule_hour ?? 4" @input="updateSettingNum('statistics', 'schedule_hour', $event)" min="0" max="23" /></div>
            <div class="vis-field"><label>每日统计-分</label><input type="number" :value="settings.statistics?.schedule_minute ?? 0" @input="updateSettingNum('statistics', 'schedule_minute', $event)" min="0" max="59" /></div>
          </div>
        </div>

        <!-- Templates -->
        <div v-if="activeFile === 'templates'" class="vis-card">
          <div class="vis-card-title">消息模板</div>
          <div class="help-vars" style="margin-bottom:12px">
            <span v-for="v in VARIABLES" :key="v" class="help-var">{{ v }}</span>
          </div>
          <div v-for="key in templateKeys" :key="key" class="tpl-edit-item">
            <div class="tpl-edit-header">
              <label class="tpl-edit-label">{{ key }}</label>
              <span v-if="TEMPLATE_LABELS[key]" class="tpl-desc">{{ TEMPLATE_LABELS[key] }}</span>
            </div>
            <div class="tpl-fields">
              <div class="tpl-field">
                <span class="tpl-field-label">Markdown</span>
                <textarea class="tpl-edit-input" :value="getTemplateField(key, 'markdown')" @input="updateTemplateField(key, 'markdown', $event)" rows="2" />
              </div>
              <div class="tpl-field">
                <span class="tpl-field-label">按钮 (YAML)</span>
                <textarea class="tpl-edit-input" :value="buttonTexts[key] ?? ''" @input="updateButtonText(key, $event)" rows="2"
                  placeholder='[{text: "菜单", data: "/菜单", enter: true, style: 1}],[{text: "帮助", data: "/帮助"}]' />
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- YAML mode -->
    <div v-else class="config-body">
      <div class="editor-wrap">
        <div class="editor-hint">
          <span>编辑 {{ activeFile }}.yaml</span>
          <span v-if="dirty" class="editor-hint-r">• 未保存</span>
        </div>
        <textarea class="yaml-editor" v-model="raw[activeFile]" @input="dirty = true" spellcheck="false" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.config-page {
  display:flex;
  flex-direction:column;
  height:calc(100vh - 100px)
}
.config-header {
  display:flex;
  align-items:center;
  justify-content:flex-end;
  margin-bottom:12px
}
.config-actions {
  display:flex;
  gap:6px
}
.cfg-btn {
  padding:5px 14px;
  border:1px solid var(--border);
  border-radius:6px;
  background:transparent;
  color:var(--text2);
  cursor:pointer;
  font-size:13px
}
.cfg-btn:hover {
  color:var(--text);
  border-color:var(--text3)
}
.cfg-btn:disabled {
  opacity:.4;
  cursor:default
}
.cfg-btn.active {
  background:var(--bg3);
  color:var(--text);
  border-color:var(--text3)
}
.cfg-btn.save {
  background:var(--accent);
  color:#fff;
  border-color:var(--accent)
}
.cfg-btn.save:hover {
  background:var(--accent-hover)
}
.config-tabs {
  display:flex;
  align-items:center;
  gap:6px;
  margin-bottom:12px
}
.config-tabs-spacer {
  flex:1
}
.config-tab {
  padding:6px 16px;
  border:1px solid var(--border);
  border-radius:6px;
  background:transparent;
  color:var(--text2);
  cursor:pointer;
  font-size:13px
}
.config-tab:hover {
  color:var(--text)
}
.config-tab.active {
  background:var(--accent);
  color:#fff;
  border-color:var(--accent)
}
.config-body {
  flex:1;
  display:flex;
  gap:12px;
  min-height:0
}
.editor-wrap {
  flex:1;
  display:flex;
  flex-direction:column;
  min-width:0
}
.editor-hint {
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:8px 12px;
  background:var(--bg3);
  border:1px solid var(--border);
  border-bottom:none;
  border-radius:8px 8px 0 0;
  color:var(--text2);
  font-size:12px
}
.editor-hint-r {
  color:var(--warning)
}
.yaml-editor {
  flex:1;
  resize:none;
  padding:12px;
  background:var(--bg2);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:0 0 8px 8px;
  font-family:Cascadia Code,Fira Code,monospace;
  font-size:13px;
  line-height:1.6;
  -moz-tab-size:2;
  -o-tab-size:2;
  tab-size:2;
  outline:none
}
.yaml-editor:focus {
  border-color:var(--accent)
}
.visual-body {
  flex:1;
  overflow-y:auto;
  display:flex;
  flex-direction:column;
  gap:12px
}
.vis-card {
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:10px;
  padding:16px
}
.vis-card-title {
  color:var(--text);
  font-size:14px;
  font-weight:700;
  margin-bottom:12px
}
.vis-section {
  color:var(--accent);
  font-size:12px;
  font-weight:600;
  margin:14px 0 8px;
  padding-top:10px;
  border-top:1px solid var(--border)
}
.vis-grid {
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:8px 16px
}
.vis-grid-3 {
  display:grid;
  grid-template-columns:1fr 1fr 1fr;
  gap:8px 16px
}
.vis-field {
  display:flex;
  align-items:center;
  gap:8px
}
.vis-field.full {
  grid-column:1 / -1
}
.vis-field label:first-child {
  font-size:12px;
  color:var(--text2);
  min-width:140px;
  flex-shrink:0;
  text-align:right
}
.vis-field input[type=text],.vis-field input[type=password],.vis-field input[type=number],.vis-field input:not([type]),.vis-field select {
  flex:1;
  min-width:0;
  background:var(--bg3);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:6px;
  padding:5px 8px;
  font-size:12px;
  outline:none
}
.vis-field input:focus,.vis-field select:focus {
  border-color:var(--accent)
}
.vis-switch {
  position:relative;
  display:inline-block;
  width:36px;
  height:20px;
  cursor:pointer
}
.vis-switch input {
  display:none
}
.vis-switch span {
  position:absolute;
  top:0;
  right:0;
  bottom:0;
  left:0;
  background:var(--border);
  border-radius:10px;
  transition:.2s
}
.vis-switch span:after {
  content:"";
  position:absolute;
  left:2px;
  top:2px;
  width:16px;
  height:16px;
  background:#fff;
  border-radius:50%;
  transition:.2s
}
.vis-switch input:checked+span {
  background:var(--accent)
}
.vis-switch input:checked+span:after {
  left:18px
}
.tpl-edit-item {
  margin-bottom:14px;
  padding-bottom:14px;
  border-bottom:1px solid var(--border)
}
.tpl-edit-item:last-child {
  border-bottom:none;
  margin-bottom:0;
  padding-bottom:0
}
.tpl-edit-header {
  display:flex;
  align-items:center;
  gap:8px;
  margin-bottom:6px
}
.tpl-edit-label {
  font-size:12px;
  color:var(--accent);
  font-weight:600
}
.tpl-desc {
  font-size:11px;
  color:var(--text3)
}
.tpl-fields {
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:12px
}
.tpl-field {
  display:flex;
  flex-direction:column;
  gap:2px;
  min-width:0
}
.tpl-field-label {
  font-size:11px;
  color:var(--text3)
}
.tpl-edit-input {
  width:100%;
  box-sizing:border-box;
  resize:vertical;
  background:var(--bg3);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:6px;
  padding:6px 8px;
  font-size:12px;
  font-family:Cascadia Code,Fira Code,monospace;
  line-height:1.5;
  outline:none
}
.tpl-edit-input:focus {
  border-color:var(--accent)
}
.help-vars {
  display:flex;
  flex-wrap:wrap;
  gap:4px
}
.help-var {
  background:var(--bg3);
  color:var(--accent);
  padding:2px 8px;
  border-radius:4px;
  font-size:11px;
  font-family:monospace
}
.bot-picker {
  display:flex;
  align-items:center;
  gap:10px;
  margin-bottom:4px
}
.bot-picker label {
  font-size:13px;
  color:var(--text2);
  font-weight:600;
  flex-shrink:0
}
.bot-picker select {
  flex:1;
  max-width:320px;
  background:var(--bg3);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:6px;
  padding:5px 8px;
  font-size:13px;
  outline:none
}
.bot-picker select:focus {
  border-color:var(--accent)
}
@media(max-width:767px) {
  .config-tabs {
  flex-wrap:wrap
}
.config-tab {
  padding:5px 10px;
  font-size:12px
}
.config-body {
  flex-direction:column
}
.vis-grid,.vis-grid-3 {
  grid-template-columns:1fr
}
.bot-picker {
  flex-direction:column;
  align-items:stretch
}
.bot-picker select {
  max-width:none
}
}
</style>
