<script setup>
import { h, ref, reactive, computed, defineComponent, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import axios from '../utils/axios'
import { useAppStore } from '../stores/app'
import SvgIcon from '../components/SvgIcon.vue'

const msg = useMessage()
const appStore = useAppStore()
const dirs = ref([])
const modules = ref([])
const search = ref('')
const mode = ref('all')
const loading = ref(false)
const expanded = reactive({})
const botBindOpen = reactive({})
const MAX_EDIT = 50 * 1024

// Code editor modal
const editor = reactive({ show: false, filename: '', content: '', originalContent: '', path: '', readonly: false, modified: false, saving: false })
// Config editor modal
const cfgEditor = reactive({ show: false, filename: '', path: '', format: 'raw', raw: '', parsed: null, comments: {}, viewMode: 'visual', modified: false, saving: false })

// ConfigNode recursive component
const ConfigNode = defineComponent({
  name: 'ConfigNode',
  props: { data: { required: true }, path: { type: Array, default: () => [] }, comments: { type: Object, default: () => ({}) } },
  emits: ['update'],
  setup(props, { emit }) {
    function update(p, v) { emit('update', p, v) }
    function comment(p) { return props.comments[p.join('.')] || '' }
    return () => {
      const d = props.data
      if (d == null) return h('div', { class: 'cfg-row' }, [h('span', { class: 'cfg-key' }, props.path.length ? props.path[props.path.length - 1] : 'null'), h('span', { class: 'cfg-val null' }, 'null')])
      if (typeof d === 'object' && !Array.isArray(d)) {
        const entries = Object.entries(d)
        return h('div', { class: 'cfg-section' }, entries.map(([k, v]) => {
          const np = [...props.path, k], c = comment(np)
          return v !== null && typeof v === 'object'
            ? h('details', { class: 'cfg-group', open: true }, [
                h('summary', { class: 'cfg-group-title' }, [k, c ? h('span', { class: 'cfg-comment' }, c) : null]),
                h(ConfigNode, { data: v, path: np, comments: props.comments, onUpdate: update })
              ])
            : h(ConfigNode, { data: v, path: np, comments: props.comments, onUpdate: update })
        }))
      }
      if (Array.isArray(d)) {
        const items = d.map((v, i) => {
          const np = [...props.path, i]
          return h('div', { class: 'cfg-array-item' }, [
            h('span', { class: 'cfg-idx' }, `[${i}]`),
            h(ConfigNode, { data: v, path: np, comments: props.comments, onUpdate: update }),
            h('button', { class: 'cfg-arr-btn remove', title: '删除', onClick: () => { const a = [...d]; a.splice(i, 1); update(props.path, a) } }, '×')
          ])
        })
        const defVal = () => {
          if (!d.length) return ''
          const f = d[0]
          if (f && typeof f === 'object' && !Array.isArray(f)) return Object.fromEntries(Object.entries(f).map(([k, v]) => [k, typeof v === 'boolean' ? false : typeof v === 'number' ? 0 : '']))
          return typeof f === 'boolean' ? false : typeof f === 'number' ? 0 : ''
        }
        items.push(h('button', { class: 'cfg-arr-btn add', onClick: () => update(props.path, [...d, defVal()]) }, '+ 添加'))
        return h('div', { class: 'cfg-section' }, items)
      }
      const key = props.path.length ? props.path[props.path.length - 1] : ''
      const cmt = comment(props.path), isBool = typeof d === 'boolean', isNum = typeof d === 'number'
      return h('div', { class: 'cfg-row' }, [
        h('span', { class: 'cfg-key' }, String(key)),
        isBool
          ? h('label', { class: 'cfg-toggle' }, [h('input', { type: 'checkbox', checked: d, onChange: e => update(props.path, e.target.checked) }), h('span', { class: 'cfg-toggle-slider' }), h('span', { class: 'cfg-toggle-label' }, d ? 'true' : 'false')])
          : h('input', { class: 'cfg-input' + (isNum ? ' num' : ''), type: isNum ? 'number' : 'text', value: String(d), onInput: e => { let v = e.target.value; if (isNum) v = Number(v) || 0; update(props.path, v) } }),
        cmt ? h('span', { class: 'cfg-comment' }, cmt) : null,
      ])
    }
  }
})

// Computed lists
const filteredModules = computed(() => {
  if (mode.value === 'plugin') return []
  const q = search.value.toLowerCase()
  let list = modules.value
  if (q) list = list.filter(m => m.name.toLowerCase().includes(q) || (m.display_name || '').toLowerCase().includes(q) || (m.description || '').toLowerCase().includes(q))
  return list
})
const filteredDirs = computed(() => {
  if (mode.value === 'module') return []
  const q = search.value.toLowerCase()
  if (!q) return dirs.value
  return dirs.value.filter(d => d.directory.toLowerCase().includes(q) || (d.description || '').toLowerCase().includes(q) || d.files.some(f => f.name.toLowerCase().includes(q)) || (d.commands || []).some(c => (c.name || '').toLowerCase().includes(q)))
})
const allItems = computed(() => [...filteredModules.value, ...filteredDirs.value])

function cleanPattern(s) {
  if (typeof s !== 'string' || !s) return ''
  return s
    .replace(/^\^/, '').replace(/\$$/, '')
    .replace(/\(\?:([^|)]+)(?:\|[^)]*)*\)/g, '$1')
    .replace(/\(([^|)]+)(?:\|[^)]+)+\)/g, '$1')
    .replace(/\\s\*/g, '').replace(/\\s\+/g, ' ')
    .replace(/\([^)]*\)\?/g, '').replace(/\([^)]*\)/g, '…')
    .replace(/-\?/g, '').replace(/\?/g, '')
    .replace(/\\/g, '').replace(/…+/g, '…').trim()
}
function fmtSize(s) { return s < 1024 ? s + ' B' : s < 1024 * 1024 ? (s / 1024).toFixed(1) + ' KB' : (s / (1024 * 1024)).toFixed(1) + ' MB' }
function toggle(key) { expanded[key] = !expanded[key] }
function fileBase(f) { let n = f.name; if (n.endsWith('.py')) n = n.slice(0, -3); return n }
function entryDisabled(d) { if (!d.is_large) return false; const ef = d.files.find(f => ['main.py','index.py','app.py'].includes(f.name)); return ef ? !ef.enabled : false }
function isSubFile(f) { return f.name.startsWith('app/') }
function toggleBotBind(key) { botBindOpen[key] = !botBindOpen[key] }

async function fetchAll() {
  loading.value = true
  try {
    const [s, t] = await Promise.all([axios.get('/api/plugins/scan-dirs'), axios.get('/api/modules/scan')])
    dirs.value = (s.data.dirs || []).map(d => ({ ...d, files: d.files.map(f => ({ ...f, _toggling: false })) }))
    modules.value = (t.data.modules || []).map(m => ({ ...m, _toggling: false, persist_enabled: m.persist_enabled ?? false }))
    // all collapsed by default
  } catch { msg.error('获取列表失败') } finally { loading.value = false }
}

async function toggleFile(file, dir) {
  file._toggling = true
  try {
    const action = file.enabled ? 'disable' : 'enable'
    const res = await axios.post('/api/plugins/toggle', { name: dir.directory, file: fileBase(file), action })
    if (res.data.success) {
      file.enabled = !file.enabled
      const ef = dir.files.find(f => ['main.py','index.py','app.py'].includes(f.name))
      dir.enabled = ef ? ef.enabled : dir.files.some(f => f.enabled)
      msg.success(`${file.name} 已${file.enabled ? '启用' : '禁用'}`)
    } else msg.error(res.data.message || '操作失败')
  } catch { msg.error('操作失败') } finally { file._toggling = false }
}

async function toggleModule(mod) {
  mod._toggling = true
  const action = mod.persist_enabled ? 'disable' : 'enable'
  try {
    const res = await axios.post('/api/modules/toggle', { name: mod.name, action })
    if (res.data.success) { mod.persist_enabled = !mod.persist_enabled; mod.enabled = mod.persist_enabled; msg.success(`模块 ${mod.display_name} 已${mod.persist_enabled ? '开启' : '关闭'}`); setTimeout(() => fetchAll(), 500) }
    else msg.error(res.data.message || '操作失败')
  } catch { msg.error('模块切换失败') } finally { mod._toggling = false }
}

async function uploadPlugin(e) { const f = e.target.files?.[0]; e.target.value = ''; if (!f) return; if (!f.name.endsWith('.py') && !f.name.endsWith('.zip')) { msg.error('仅支持 .py 或 .zip 文件'); return }; const fd = new FormData(); fd.append('file', f); if (f.name.endsWith('.py')) fd.append('directory', 'alone'); try { const r = await axios.post('/api/plugins/upload', fd, f.name.endsWith('.zip') ? { timeout: 120000 } : {}); r.data.success ? (msg.success(r.data.message || '上传成功'), await fetchAll()) : msg.error(r.data.message || '上传失败') } catch { msg.error('上传失败') } }
async function uploadModule(e) { const f = e.target.files?.[0]; e.target.value = ''; if (!f) return; if (!f.name.endsWith('.zip')) { msg.error('模块仅支持 .zip 格式'); return }; const fd = new FormData(); fd.append('file', f); try { const r = await axios.post('/api/modules/upload', fd); r.data.success ? (msg.success(r.data.message || '模块上传成功'), await fetchAll()) : msg.error(r.data.message || '上传失败') } catch { msg.error('模块上传失败') } }

// ── 卸载 ──
const uninstallConfirm = reactive({ show: false, name: '', type: 'plugin', keepData: true, loading: false })

function showUninstall(name, type) {
  Object.assign(uninstallConfirm, { show: true, name, type, keepData: true, loading: false })
}

async function doUninstall() {
  uninstallConfirm.loading = true
  try {
    const res = await axios.post('/api/market/uninstall', { name: uninstallConfirm.name, type: uninstallConfirm.type, keep_data: uninstallConfirm.keepData })
    if (res.data.success) { msg.success(res.data.message || '已卸载'); uninstallConfirm.show = false; await fetchAll() }
    else msg.error(res.data.message || '卸载失败')
  } catch { msg.error('卸载请求失败') }
  finally { uninstallConfirm.loading = false }
}

async function readFile(file) {
  if (!file.path) { msg.error('无文件路径'); return }
  try {
    const res = await axios.post('/api/plugins/read', { path: file.path })
    if (!res.data.success) { msg.error(res.data.message || '读取失败'); return }
    const content = res.data.content || '', size = new Blob([content]).size
    Object.assign(editor, { show: true, filename: res.data.filename || file.name, content, originalContent: content, path: file.path, readonly: size > MAX_EDIT, modified: false, saving: false })
  } catch { msg.error('读取失败') }
}
async function saveFile() {
  if (editor.readonly || editor.saving) return
  editor.saving = true
  try { const r = await axios.post('/api/plugins/save', { path: editor.path, content: editor.content }); r.data.success ? (msg.success('保存成功，重载后生效'), editor.originalContent = editor.content, editor.modified = false) : msg.error(r.data.message || '保存失败') }
  catch { msg.error('保存失败') } finally { editor.saving = false }
}
function closeEditor() { if (editor.modified && !confirm('有未保存的修改，确定关闭？')) return; editor.show = false }

async function readConfig(file) {
  try {
    const res = await axios.post('/api/config-file/read', { path: file.path })
    if (!res.data.success) { msg.error(res.data.message || '读取失败'); return }
    const canVisual = ['yaml', 'json'].includes(res.data.format) && res.data.parsed !== null
    Object.assign(cfgEditor, { show: true, filename: res.data.filename, path: file.path, format: res.data.format, raw: res.data.raw, parsed: res.data.parsed ? JSON.parse(JSON.stringify(res.data.parsed)) : null, comments: res.data.comments || {}, viewMode: canVisual ? 'visual' : 'raw', modified: false, saving: false })
  } catch { msg.error('读取配置失败') }
}
function openModuleConfig(mod) { expanded['m_' + mod.name] = true; if (mod.config_files?.length === 1) readConfig(mod.config_files[0]) }
async function openDirConfig(dir) {
  const key = 'cfg_' + dir.directory
  if (expanded[key]) { expanded[key] = false; return }
  try {
    const res = await axios.post('/api/plugins/config-files', { name: dir.directory })
    if (res.data.success && res.data.config_files?.length) { dir._config_files = res.data.config_files; res.data.config_files.length === 1 ? readConfig(res.data.config_files[0]) : (expanded[key] = true) }
    else msg.info('暂无配置文件')
  } catch { msg.error('获取配置失败') }
}
function onCfgUpdate(path, value) {
  if (!cfgEditor.parsed) return
  let obj = cfgEditor.parsed
  for (let i = 0; i < path.length - 1; i++) obj = obj[path[i]]
  obj[path[path.length - 1]] = value
  cfgEditor.modified = true
  if (cfgEditor.format === 'json') cfgEditor.raw = JSON.stringify(cfgEditor.parsed, null, 2)
  else if (cfgEditor.format === 'yaml') cfgEditor.raw = toYaml(cfgEditor.parsed)
}
function toYaml(obj, indent = 0) {
  const pad = '  '.repeat(indent)
  if (obj == null) return pad + 'null\n'
  if (typeof obj !== 'object') return typeof obj === 'string' ? (obj === '' ? "''" : /[:#\[\]{}|>&*!?,]/.test(obj) || /^\s|\s$/.test(obj) ? (obj.includes("'") ? `"${obj.replace(/"/g, '\\"')}"` : `'${obj}'`) : obj) : String(obj)
  let out = ''
  if (Array.isArray(obj)) { if (!obj.length) return pad + '[]\n'; for (const v of obj) out += typeof v === 'object' && v !== null ? pad + '-\n' + toYaml(v, indent + 1) : pad + '- ' + toYaml(v) + '\n' }
  else { for (const [k, v] of Object.entries(obj)) out += typeof v === 'object' && v !== null ? pad + k + ':\n' + toYaml(v, indent + 1) : pad + k + ': ' + toYaml(v) + '\n' }
  return out
}
async function saveCfg() {
  if (cfgEditor.saving) return
  cfgEditor.saving = true
  try {
    const content = cfgEditor.viewMode === 'visual' && cfgEditor.parsed && cfgEditor.format === 'json' ? JSON.stringify(cfgEditor.parsed, null, 2) : cfgEditor.raw
    const r = await axios.post('/api/config-file/save', { path: cfgEditor.path, content, format: cfgEditor.format })
    r.data.success ? (msg.success(r.data.message || '保存成功'), cfgEditor.modified = false) : msg.error(r.data.message || '保存失败')
  } catch { msg.error('保存失败') } finally { cfgEditor.saving = false }
}
function closeCfg() { if (cfgEditor.modified && !confirm('有未保存的修改，确定关闭？')) return; cfgEditor.show = false }

async function saveBotBindings() {
  const map = {}
  for (const d of dirs.value) { if (d.allowed_bots?.length) map[d.directory] = [...d.allowed_bots]; for (const f of d.files) if (f.allowed_bots?.length) map[`${d.directory}/${fileBase(f)}`] = [...f.allowed_bots] }
  try { await axios.post('/api/plugins/bots', { plugin_bots: map }) } catch { msg.error('保存机器人绑定失败') }
}
function bindDirBot(dir, appid, checked) { if (!dir.allowed_bots) dir.allowed_bots = []; checked ? (!dir.allowed_bots.includes(appid) && dir.allowed_bots.push(appid)) : (dir.allowed_bots = dir.allowed_bots.filter(b => b !== appid)); saveBotBindings() }
function bindFileBot(dir, file, appid, checked) { if (!file.allowed_bots) file.allowed_bots = []; checked ? (!file.allowed_bots.includes(appid) && file.allowed_bots.push(appid)) : (file.allowed_bots = file.allowed_bots.filter(b => b !== appid)); saveBotBindings() }

onMounted(() => { appStore.fetchBots(); fetchAll() })
</script>

<template>
  <div class="plugins-page">
    <div class="plugins-toolbar">
      <select v-model="mode" class="p-select"><option value="all">全部</option><option value="plugin">插件</option><option value="module">模块</option></select>
      <input v-model="search" class="p-search" placeholder="搜索插件或模块..." />
      <label v-if="mode !== 'module'" class="p-btn upload-btn"><SvgIcon name="upload" :size="14" /><span>上传插件</span><input type="file" accept=".py,.zip" hidden @change="uploadPlugin" /></label>
      <label v-if="mode !== 'plugin'" class="p-btn upload-btn"><SvgIcon name="upload" :size="14" /><span>上传模块</span><input type="file" accept=".zip" hidden @change="uploadModule" /></label>
      <button class="p-btn" @click="fetchAll" :disabled="loading">刷新</button>
    </div>

    <div v-if="loading" class="p-loading">加载中...</div>
    <div v-else-if="!allItems.length" class="p-empty">暂无{{ mode === 'module' ? '模块' : mode === 'plugin' ? '插件' : '内容' }}</div>
    <div v-else class="plugins-list">
      <!-- Modules -->
      <div v-for="m in filteredModules" :key="'m_' + m.name" class="p-dir mod-card">
        <div class="p-dir-head" @click="toggle('m_' + m.name)">
          <div class="p-dir-left">
            <SvgIcon :name="expanded['m_'+m.name] ? 'chevron-forward' : 'chevron-back'" :size="14" :style="{ transform: expanded['m_'+m.name] ? 'rotate(90deg)' : 'rotate(0)', transition: '.15s' }" />
            <SvgIcon name="cube" :size="14" style="color:var(--accent)" />
            <span class="p-dir-name">{{ m.display_name }}</span>
            <span class="p-tag module-tag">模块</span>
            <span :class="['p-tag', m.enabled ? 'ok' : 'off']">{{ m.enabled ? '运行中' : '未启用' }}</span>
            <span v-if="m.error" class="p-tag off" :title="m.error">异常</span>
            <span class="p-tag">v{{ m.version }}</span>
          </div>
          <div class="p-dir-right" @click.stop>
            <span v-if="m.description" class="p-dir-desc">{{ m.description }}</span>
            <label class="p-switch-sm module-switch" :title="m.persist_enabled ? '关闭模块' : '开启模块'">
              <input type="checkbox" :checked="m.persist_enabled" :disabled="m._toggling" @change="toggleModule(m)" /><span />
            </label>
            <span v-if="m.config_files?.length" class="p-tag config-tag" @click="openModuleConfig(m)"><SvgIcon name="settings" :size="10" /> 配置 </span>
            <span class="p-tag uninstall-tag" @click="showUninstall(m.name, 'module')"><SvgIcon name="trash" :size="10" /> 卸载</span>
          </div>
        </div>
        <div v-if="expanded['m_' + m.name]" class="p-dir-files">
          <div v-if="!m.config_files?.length" class="p-empty-inline">暂无配置文件</div>
          <div v-for="cf in m.config_files" :key="cf.path" class="p-file">
            <div class="p-file-left">
              <SvgIcon name="file" :size="13" />
              <span class="p-file-name">{{ cf.name }}</span>
              <span :class="['p-tag', 'fmt-' + cf.format]">{{ cf.format.toUpperCase() }}</span>
              <span class="p-file-size">{{ fmtSize(cf.size) }}</span>
            </div>
            <div class="p-file-actions">
              <button class="p-act-btn sm" @click="readConfig(cf)" title="编辑配置"><SvgIcon name="settings" :size="13" /></button>
            </div>
          </div>
        </div>
      </div>

      <!-- Plugin dirs -->
      <div v-for="d in filteredDirs" :key="d.directory" class="p-dir">
        <div class="p-dir-head" @click="toggle(d.directory)">
          <div class="p-dir-left">
            <SvgIcon :name="expanded[d.directory] ? 'chevron-forward' : 'chevron-back'" :size="14" :style="{ transform: expanded[d.directory] ? 'rotate(90deg)' : 'rotate(0)', transition: '.15s' }" />
            <SvgIcon name="extension-puzzle" :size="14" style="color:var(--text2)" />
            <span class="p-dir-name">{{ d.is_large ? (d.meta?.name || d.directory) : d.directory }}</span>
            <span class="p-tag plugin-tag">插件</span>
            <span v-if="d.is_system" class="p-tag">系统</span>
            <span :class="['p-tag', d.enabled ? 'ok' : 'off']">{{ d.enabled ? '已加载' : '未加载' }}</span>
            <span v-if="d.is_large && d.meta?.version" class="p-tag">v{{ d.meta.version }}</span>
            <span v-else-if="!d.is_large" class="p-tag">{{ d.files.length }} 个文件</span>
            <span v-else class="p-tag">{{ d.files.length }} 个文件</span>
          </div>
          <div class="p-dir-right" @click.stop>
            <span v-if="d.is_large && d.meta?.author" class="p-meta-author">{{ d.meta.author }}</span>
            <span v-if="d.is_large && (d.meta?.description || d.description)" class="p-dir-desc">{{ d.meta?.description || d.description }}</span>
            <a v-if="d.is_large && d.meta?.github" class="p-meta-link" :href="d.meta.github" target="_blank" @click.stop title="GitHub"><SvgIcon name="globe" :size="12" /></a>
            <span class="p-tag config-tag" @click="openDirConfig(d)"><SvgIcon name="settings" :size="10" /> 配置 </span>
            <span :class="['p-tag bot-bind-tag', { active: d.allowed_bots?.length }]" @click="toggleBotBind(d.directory)">
              <SvgIcon name="people" :size="10" /> {{ d.allowed_bots?.length ? d.allowed_bots.length + '个机器人' : '全部机器人' }}
            </span>
            <span v-if="d.is_large && !d.is_system" class="p-tag uninstall-tag" @click="showUninstall(d.directory, 'plugin')"><SvgIcon name="trash" :size="10" /> 卸载</span>
          </div>
        </div>
        <!-- Dir bot bind -->
        <div v-if="botBindOpen[d.directory]" class="bot-bind-panel" @click.stop>
          <div class="bot-bind-title">选择允许触发的机器人 (不选 = 全部)</div>
          <label v-for="bot in appStore.bots" :key="bot.bot_qq" class="bot-bind-item">
            <input type="checkbox" :checked="(d.allowed_bots || []).includes(bot.bot_qq)" @change="e => bindDirBot(d, bot.bot_qq, e.target.checked)" />
            <img v-if="bot.avatar" :src="bot.avatar" class="bot-bind-avatar" />
            <span>{{ bot.name || bot.bot_qq }}</span><span class="bot-bind-id">{{ bot.bot_qq }}</span>
          </label>
        </div>
        <!-- Commands -->
        <div v-if="d.commands?.length && expanded[d.directory]" class="p-dir-cmds">
          <span v-for="cmd in d.commands" :key="cmd.pattern" :class="['p-cmd-tag', { owner: cmd.owner_only, group: cmd.group_only && !cmd.owner_only }]" :title="(cmd.owner_only ? '[主人专用] ' : cmd.group_only ? '[群聊专用] ' : '[所有人] ') + (cmd.name ? cmd.name + ' | ' : '') + (cmd.desc ? cmd.pattern + ' — ' + cmd.desc : cmd.pattern)">
            <SvgIcon :name="cmd.owner_only ? 'shield' : cmd.group_only ? 'group' : 'globe'" :size="11" /> {{ cmd.name || cleanPattern(cmd.pattern) }}
          </span>
        </div>
        <!-- Config files -->
        <div v-if="expanded['cfg_' + d.directory] && d._config_files?.length" class="p-dir-files">
          <div v-for="cf in d._config_files" :key="cf.path" class="p-file">
            <div class="p-file-left">
              <SvgIcon name="settings" :size="13" />
              <span class="p-file-name">{{ cf.name }}</span>
              <span :class="['p-tag', 'fmt-' + cf.format]">{{ cf.format.toUpperCase() }}</span>
              <span class="p-file-size">{{ fmtSize(cf.size) }}</span>
            </div>
            <div class="p-file-actions">
              <button class="p-act-btn sm" @click="readConfig(cf)" title="编辑配置"><SvgIcon name="settings" :size="13" /></button>
            </div>
          </div>
        </div>
        <!-- Files -->
        <div v-if="expanded[d.directory]" class="p-dir-files">
          <template v-for="f in d.files" :key="f.path">
            <div :class="['p-file', { 'p-file-greyed': entryDisabled(d) && isSubFile(f) }]">
              <div class="p-file-left"><SvgIcon name="file" :size="13" /><span class="p-file-name">{{ f.name }}</span><span v-if="!d.is_large && f.meta?.name" class="p-file-meta">({{ f.meta.name }}<template v-if="f.meta?.version"> v{{ f.meta.version }}</template>)</span><span class="p-file-size">{{ fmtSize(f.size) }}</span><span class="p-file-time">{{ f.last_modified }}</span></div>
              <div class="p-file-actions">
                <span v-if="!d.is_large" :class="['p-tag bot-bind-tag sm', { active: f.allowed_bots?.length }]" @click.stop="toggleBotBind(d.directory + '/' + fileBase(f))" :title="f.allowed_bots?.length ? '已绑定 ' + f.allowed_bots.length + ' 个机器人' : '全部机器人'">
                  <SvgIcon name="people" :size="9" /> {{ f.allowed_bots?.length || '全部' }}
                </span>
                <label v-if="!(entryDisabled(d) && isSubFile(f))" class="p-switch-sm" :title="f.enabled ? '禁用' : '启用'"><input type="checkbox" :checked="f.enabled" :disabled="f._toggling" @change="toggleFile(f, d)" /><span /></label>
                <button class="p-act-btn sm" @click="readFile(f)" title="查看代码"><SvgIcon name="code" :size="13" /></button>
                <button v-if="!d.is_large && !d.is_system" class="p-act-btn sm danger-btn" @click.stop="showUninstall(d.directory === 'alone' ? fileBase(f) : d.directory, 'plugin')" title="卸载"><SvgIcon name="trash" :size="13" /></button>
              </div>
            </div>
            <!-- File-level bot bind -->
            <div v-if="!d.is_large && botBindOpen[d.directory + '/' + fileBase(f)]" class="bot-bind-panel file-level" @click.stop>
              <div class="bot-bind-title">{{ f.name }} — 选择允许触发的机器人</div>
              <label v-for="bot in appStore.bots" :key="bot.bot_qq" class="bot-bind-item">
                <input type="checkbox" :checked="(f.allowed_bots || []).includes(bot.bot_qq)" @change="e => bindFileBot(d, f, bot.bot_qq, e.target.checked)" />
                <img v-if="bot.avatar" :src="bot.avatar" class="bot-bind-avatar" />
                <span>{{ bot.name || bot.bot_qq }}</span><span class="bot-bind-id">{{ bot.bot_qq }}</span>
              </label>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- Uninstall confirm modal -->
    <div v-if="uninstallConfirm.show" class="p-modal-overlay" @click.self="uninstallConfirm.show = false">
      <div class="p-uninstall-confirm">
        <div class="p-uninstall-title">确认卸载</div>
        <div class="p-uninstall-msg">确定卸载 <b>{{ uninstallConfirm.name }}</b> 吗？</div>
        <label class="p-uninstall-check">
          <input type="checkbox" v-model="uninstallConfirm.keepData" />
          <span>保留插件数据</span>
        </label>
        <div class="p-uninstall-btns">
          <button class="p-btn" @click="uninstallConfirm.show = false">取消</button>
          <button class="p-btn danger" @click="doUninstall" :disabled="uninstallConfirm.loading">{{ uninstallConfirm.loading ? '卸载中...' : '卸载' }}</button>
        </div>
      </div>
    </div>

    <!-- Code editor modal -->
    <div v-if="editor.show" class="p-modal-overlay" @click.self="closeEditor">
      <div class="p-modal">
        <div class="p-modal-head">
          <div class="p-modal-title"><SvgIcon name="file" :size="16" /><span>{{ editor.filename }}</span><span v-if="editor.readonly" class="p-tag warn">只读 (文件过大)</span><span v-if="editor.modified" class="p-tag accent">已修改</span></div>
          <div class="p-modal-actions">
            <button v-if="!editor.readonly && editor.modified" class="p-btn save-btn" @click="saveFile"><SvgIcon name="save" :size="14" /> 保存 </button>
            <button class="p-btn close-btn" @click="closeEditor"><SvgIcon name="x" :size="14" /> 关闭 </button>
          </div>
        </div>
        <div class="p-modal-body"><textarea v-model="editor.content" class="p-code-editor" spellcheck="false" :readonly="editor.readonly" @input="editor.modified = true" /></div>
      </div>
    </div>

    <!-- Config editor modal -->
    <div v-if="cfgEditor.show" class="p-modal-overlay" @click.self="closeCfg">
      <div class="p-modal cfg-modal">
        <div class="p-modal-head">
          <div class="p-modal-title">
            <SvgIcon name="settings" :size="16" />
            <span>{{ cfgEditor.filename }}</span>
            <span :class="['p-tag', 'fmt-' + cfgEditor.format]">{{ cfgEditor.format.toUpperCase() }}</span>
            <span v-if="cfgEditor.modified" class="p-tag accent">已修改</span>
          </div>
          <div class="p-modal-actions">
            <div v-if="cfgEditor.format === 'yaml' || cfgEditor.format === 'json'" class="cv-mode-tabs">
              <button :class="['cv-mode-tab', { active: cfgEditor.viewMode === 'visual' }]" @click="cfgEditor.viewMode = 'visual'"><SvgIcon name="grid" :size="12" /> 可视化</button>
              <button :class="['cv-mode-tab', { active: cfgEditor.viewMode === 'raw' }]" @click="cfgEditor.viewMode = 'raw'"><SvgIcon name="code" :size="12" /> 源码</button>
            </div>
            <button v-if="cfgEditor.modified" class="p-btn save-btn" @click="saveCfg"><SvgIcon name="save" :size="14" /> 保存</button>
            <button class="p-btn close-btn" @click="closeCfg"><SvgIcon name="x" :size="14" /> 关闭</button>
          </div>
        </div>
        <div class="p-modal-body cfg-body">
          <div v-if="cfgEditor.viewMode === 'visual' && cfgEditor.parsed" class="cfg-visual">
            <ConfigNode :data="cfgEditor.parsed" :path="[]" :comments="cfgEditor.comments" @update="onCfgUpdate" />
          </div>
          <textarea v-else v-model="cfgEditor.raw" class="p-code-editor cfg-editor" spellcheck="false" @input="cfgEditor.modified = true" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.plugins-page {
  display:flex;
  flex-direction:column
}
.plugins-toolbar {
  display:flex;
  align-items:center;
  gap:8px;
  margin-bottom:12px
}
.p-select {
  background:var(--bg2);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:6px;
  padding:6px 8px;
  font-size:13px;
  outline:none;
  cursor:pointer;
  min-width:80px
}
.p-select:focus {
  border-color:var(--accent)
}
.p-search {
  flex:1;
  max-width:260px;
  background:var(--bg2);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:6px;
  padding:6px 10px;
  font-size:13px;
  outline:none
}
.p-search:focus {
  border-color:var(--accent)
}
.p-btn {
  display:flex;
  align-items:center;
  gap:4px;
  padding:6px 12px;
  border:1px solid var(--border);
  border-radius:6px;
  background:transparent;
  color:var(--text2);
  cursor:pointer;
  font-size:12px
}
.p-btn:hover {
  color:var(--text);
  border-color:var(--text3)
}
.p-btn:disabled {
  opacity:.4;
  cursor:default
}
.p-btn.active-mode {
  background:var(--accent);
  color:#fff;
  border-color:var(--accent)
}
.upload-btn {
  background:var(--accent);
  color:#fff;
  border-color:var(--accent);
  cursor:pointer
}
.upload-btn:hover {
  opacity:.9
}
.save-btn {
  background:var(--accent);
  color:#fff;
  border-color:var(--accent)
}
.save-btn:hover {
  opacity:.9
}
.plugins-list {
  display:flex;
  flex-direction:column;
  gap:6px;
  padding-bottom:40px
}
.p-loading,.p-empty {
  text-align:center;
  color:var(--text3);
  padding:40px 0;
  font-size:13px
}
.p-empty-inline {
  text-align:center;
  color:var(--text3);
  padding:12px 0;
  font-size:12px
}
.p-dir {
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:10px;
  overflow:clip
}
.p-dir-head {
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:10px 14px;
  cursor:pointer;
  -webkit-user-select:none;
  -moz-user-select:none;
  user-select:none;
  gap:8px
}
.p-dir-head:hover {
  background:var(--bg3)
}
.p-dir-left {
  display:flex;
  align-items:center;
  gap:6px;
  min-width:0
}
.p-dir-name {
  font-size:13px;
  font-weight:600;
  color:var(--text)
}
.p-dir-right {
  display:flex;
  align-items:center;
  gap:6px;
  flex-shrink:0
}
.p-dir-desc {
  font-size:11px;
  color:var(--text3);
  max-width:300px;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap
}
.p-meta-author {
  font-size:11px;
  color:var(--accent);
  opacity:.8;
  white-space:nowrap
}
.p-meta-link {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  width:22px;
  height:22px;
  border-radius:4px;
  color:var(--text3);
  text-decoration:none;
  transition:.15s
}
.p-meta-link:hover {
  color:var(--accent);
  background:rgba(var(--accent-rgb,99,102,241),.1)
}
.p-tag {
  font-size:10px;
  padding:1px 6px;
  border-radius:4px;
  background:var(--bg3);
  color:var(--text3);
  white-space:nowrap
}
.p-tag.ok {
  background:#34c7591f;
  color:#34c759
}
.p-tag.off {
  background:#ff453a1a;
  color:#ff453a
}
.p-tag.warn {
  background:#ffaa0026;
  color:#e8a000
}
.p-tag.accent {
  background:rgba(var(--accent-rgb,99,102,241),.15);
  color:var(--accent)
}
.p-tag.module-tag {
  background:rgba(var(--accent-rgb,99,102,241),.15);
  color:var(--accent);
  font-weight:600
}
.p-tag.plugin-tag {
  background:#34c7591f;
  color:#34c759;
  font-weight:600
}
.p-tag.config-tag {
  cursor:pointer;
  background:rgba(var(--accent-rgb,99,102,241),.1);
  color:var(--accent);
  display:inline-flex;
  align-items:center;
  gap:2px
}
.p-tag.config-tag:hover {
  background:rgba(var(--accent-rgb,99,102,241),.25)
}
.p-tag.fmt-yaml {
  background:#ffaa001f;
  color:#e8a000
}
.p-tag.fmt-json {
  background:#34c7591a;
  color:#34c759
}
.p-tag.fmt-toml {
  background:#6496ff1f;
  color:#6496ff
}
.p-tag.fmt-ini {
  background:#c864c81f;
  color:#c864c8
}
.p-tag.fmt-text,.p-tag.fmt-raw {
  background:var(--bg3);
  color:var(--text3)
}
.p-dir-cmds {
  display:flex;
  flex-wrap:wrap;
  gap:4px;
  padding:0 14px 8px
}
.p-cmd-tag {
  font-size:11px;
  padding:1px 7px;
  border-radius:4px;
  background:rgba(var(--accent-rgb,99,102,241),.1);
  color:var(--accent);
  white-space:nowrap;
  display:inline-flex;
  align-items:center;
  gap:3px
}
.p-cmd-tag.owner {
  background:#ffaa001f;
  color:#e8a000
}
.p-cmd-tag.group {
  background:#34c7591a;
  color:#34c759
}
.p-dir-files {
  border-top:1px solid var(--border)
}
.p-file {
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:6px 14px 6px 28px;
  border-bottom:1px solid var(--border);
  gap:8px
}
.p-file:last-child {
  border-bottom:none
}
.p-file-greyed {
  opacity:.4;
  pointer-events:none
}
.p-file-greyed .p-act-btn {
  pointer-events:auto;
  opacity:1
}
.p-file-left {
  display:flex;
  align-items:center;
  gap:6px;
  min-width:0
}
.p-file-name {
  font-size:12px;
  color:var(--text);
  font-family:Cascadia Code,Fira Code,monospace
}
.p-file-size,.p-file-time {
  font-size:10px;
  color:var(--text3)
}
.p-file-actions {
  display:flex;
  align-items:center;
  gap:6px;
  flex-shrink:0;
  position:relative
}
.p-switch-sm {
  position:relative;
  display:inline-block;
  width:30px;
  height:16px;
  cursor:pointer;
  flex-shrink:0
}
.p-switch-sm input {
  display:none
}
.p-switch-sm span {
  position:absolute;
  top:0;
  right:0;
  bottom:0;
  left:0;
  background:var(--border);
  border-radius:8px;
  transition:.2s
}
.p-switch-sm span:after {
  content:"";
  position:absolute;
  left:2px;
  top:2px;
  width:12px;
  height:12px;
  background:#fff;
  border-radius:50%;
  transition:.2s
}
.p-switch-sm input:checked+span {
  background:var(--accent)
}
.p-switch-sm input:checked+span:after {
  left:16px
}
.bot-bind-tag {
  cursor:pointer;
  display:inline-flex;
  align-items:center;
  gap:3px;
  background:var(--bg3);
  color:var(--text3);
  transition:.15s
}
.bot-bind-tag:hover {
  color:var(--accent);
  background:rgba(var(--accent-rgb,99,102,241),.1)
}
.bot-bind-tag.active {
  background:rgba(var(--accent-rgb,99,102,241),.15);
  color:var(--accent)
}
.bot-bind-tag.sm {
  font-size:10px;
  padding:1px 5px
}
.bot-bind-panel {
  padding:8px 14px;
  background:var(--bg);
  border-top:1px solid var(--border)
}
.bot-bind-panel.file-level {
  padding:8px 14px 8px 28px;
  border-bottom:1px solid var(--border)
}
.bot-bind-title {
  font-size:11px;
  color:var(--text3);
  margin-bottom:6px
}
.bot-bind-item {
  display:flex;
  align-items:center;
  gap:6px;
  padding:4px 0;
  cursor:pointer;
  font-size:12px;
  color:var(--text)
}
.bot-bind-item input[type=checkbox] {
  width:14px;
  height:14px;
  accent-color:var(--accent);
  cursor:pointer
}
.bot-bind-avatar {
  width:18px;
  height:18px;
  border-radius:50%
}
.bot-bind-id {
  font-size:10px;
  color:var(--text3);
  margin-left:auto;
  font-family:monospace
}
.p-act-btn {
  display:flex;
  align-items:center;
  justify-content:center;
  width:28px;
  height:28px;
  border-radius:6px;
  border:1px solid var(--border);
  background:transparent;
  color:var(--text2);
  cursor:pointer
}
.p-act-btn.sm {
  width:24px;
  height:24px
}
.p-act-btn:hover {
  color:var(--accent);
  border-color:var(--accent)
}
.p-modal-overlay {
  position:fixed;
  top:0;
  right:0;
  bottom:0;
  left:0;
  z-index:1000;
  background:#00000073;
  display:flex;
  align-items:center;
  justify-content:center
}
.p-modal {
  width:92vw;
  max-width:1100px;
  height:82vh;
  background:var(--bg);
  border:1px solid var(--border);
  border-radius:12px;
  display:flex;
  flex-direction:column;
  overflow:hidden
}
.cfg-modal {
  max-width:900px;
  height:78vh
}
.p-modal-head {
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:10px 14px;
  background:var(--bg2);
  border-bottom:1px solid var(--border);
  gap:8px;
  flex-wrap:wrap
}
.p-modal-title {
  display:flex;
  align-items:center;
  gap:6px;
  font-size:13px;
  font-weight:600;
  color:var(--text);
  min-width:0
}
.p-modal-actions {
  display:flex;
  align-items:center;
  gap:6px;
  flex-shrink:0;
  flex-wrap:wrap
}
.p-modal-body {
  flex:1;
  display:flex;
  min-height:0
}
.p-code-editor {
  flex:1;
  resize:none;
  padding:14px 16px;
  margin:0 8px 8px;
  background:#1a1a2e;
  color:#e0e0e0;
  border:1px solid rgba(255,255,255,.08);
  border-radius:8px;
  outline:none;
  font-family:Cascadia Code,Fira Code,Consolas,monospace;
  font-size:13px;
  line-height:1.7;
  -moz-tab-size:4;
  -o-tab-size:4;
  tab-size:4
}
.p-code-editor[readonly] {
  opacity:.8;
  cursor:default
}
.close-btn {
  color:var(--text);
  background:var(--bg3);
  border-color:var(--border)
}
.close-btn:hover {
  color:#ff453a;
  border-color:#ff453a;
  background:#ff453a1a
}
.cfg-body {
  flex-direction:column;
  background:var(--bg)
}
.cfg-visual {
  flex:1;
  overflow-y:auto;
  padding:12px 16px;
  background:var(--bg)
}
.cfg-editor {
  margin-top:0
}
.cv-mode-tabs {
  display:flex;
  background:var(--bg3);
  border-radius:8px;
  padding:2px;
  gap:2px
}
.cv-mode-tab {
  display:flex;
  align-items:center;
  gap:4px;
  padding:5px 12px;
  border:none;
  border-radius:6px;
  background:transparent;
  color:var(--text3);
  font-size:12px;
  cursor:pointer;
  transition:all .2s;
  white-space:nowrap
}
.cv-mode-tab:hover { color:var(--text) }
.cv-mode-tab.active {
  background:var(--accent);
  color:#fff;
  box-shadow:0 1px 4px rgba(0,0,0,.2)
}
@media(max-width:767px) {
  .plugins-toolbar {
  flex-wrap:wrap
}
.p-search {
  max-width:none;
  width:100%;
  order:10
}
.p-dir-head {
  flex-direction:column;
  align-items:flex-start;
  padding:10px 12px;
  gap:8px
}
.p-dir-left {
  flex-wrap:wrap;
  gap:4px
}
.p-dir-right {
  width:100%;
  flex-wrap:wrap;
  gap:6px
}
.p-dir-desc {
  max-width:none;
  width:100%;
  white-space:normal;
  line-height:1.4
}
.p-file {
  flex-wrap:wrap;
  padding:8px 12px;
  gap:6px
}
.p-file-left {
  flex:1;
  min-width:0;
  flex-wrap:wrap
}
.p-file-time {
  display:none
}
.p-file-actions {
  width:auto
}
.p-modal {
  width:100vw;
  height:100vh;
  max-width:none;
  border-radius:0
}
.cfg-modal {
  max-width:none;
  height:100vh
}
.p-modal-head {
  padding:10px 12px;
  flex-direction:column;
  align-items:flex-start;
  gap:8px
}
.p-modal-title {
  flex-wrap:wrap;
  font-size:12px
}
.p-modal-actions {
  width:100%;
  justify-content:flex-end
}
.p-code-editor {
  font-size:12px;
  padding:10px 12px;
  margin:0 4px 4px;
  line-height:1.5
}
.cfg-visual {
  padding:10px 12px
}
.p-dir-cmds {
  padding:6px 12px
}
.bot-bind-panel {
  padding:8px 12px
}
.bot-bind-panel.file-level {
  padding:8px 12px
}
}

</style>

<style>
/* ===== Config Tree (unscoped for ConfigNode child component) ===== */
.cfg-section {
  display:flex;
  flex-direction:column;
  gap:2px
}
.cfg-group {
  margin-bottom:4px
}
.cfg-group-title {
  font-size:13px;
  font-weight:600;
  color:var(--accent);
  cursor:pointer;
  padding:6px 0 4px;
  -webkit-user-select:none;
  -moz-user-select:none;
  user-select:none;
  list-style:none;
  display:flex;
  align-items:center;
  gap:4px
}
.cfg-group-title:before {
  content:"▶";
  font-size:9px;
  transition:.15s
}
details[open]>.cfg-group-title:before {
  transform:rotate(90deg)
}
.cfg-group>.cfg-section {
  padding-left:16px;
  margin-left:4px
}
.cfg-row {
  display:flex;
  align-items:center;
  gap:10px;
  padding:4px 0;
  min-height:32px
}
.cfg-key {
  font-size:12px;
  color:var(--text2);
  font-family:Cascadia Code,Fira Code,monospace;
  min-width:140px;
  flex-shrink:0
}
.cfg-comment {
  font-size:10px;
  color:var(--text3);
  opacity:.5;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
  flex-shrink:1;
  min-width:0
}
.cfg-group-title .cfg-comment {
  font-size:10px;
  font-weight:400;
  margin-left:6px
}
.cfg-val.null {
  font-size:12px;
  color:var(--text3);
  font-style:italic
}
.cfg-input {
  flex:1;
  max-width:400px;
  padding:4px 8px;
  font-size:12px;
  background:var(--bg2);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:4px;
  outline:none;
  font-family:Cascadia Code,Fira Code,monospace
}
.cfg-input:focus {
  border-color:var(--accent)
}
.cfg-input.num {
  max-width:160px
}
.cfg-toggle {
  display:flex;
  align-items:center;
  gap:6px;
  cursor:pointer
}
.cfg-toggle input {
  display:none
}
.cfg-toggle-slider {
  position:relative;
  width:32px;
  height:18px;
  background:var(--border);
  border-radius:9px;
  transition:.2s
}
.cfg-toggle-slider:after {
  content:"";
  position:absolute;
  left:2px;
  top:2px;
  width:14px;
  height:14px;
  background:#fff;
  border-radius:50%;
  transition:.2s
}
.cfg-toggle input:checked+.cfg-toggle-slider {
  background:var(--accent)
}
.cfg-toggle input:checked+.cfg-toggle-slider:after {
  left:16px
}
.cfg-toggle-label {
  font-size:11px;
  color:var(--text3);
  font-family:monospace
}
.cfg-array-item {
  display:flex;
  align-items:center;
  gap:6px
}
.cfg-idx {
  font-size:10px;
  color:var(--text3);
  min-width:28px;
  font-family:monospace
}
.cfg-arr-btn {
  border:1px solid var(--border);
  border-radius:4px;
  background:transparent;
  cursor:pointer;
  font-size:11px;
  padding:2px 8px;
  color:var(--text2);
  transition:.15s
}
.cfg-arr-btn:hover {
  border-color:var(--accent);
  color:var(--accent)
}
.cfg-arr-btn.remove {
  padding:2px 6px;
  color:var(--text3);
  flex-shrink:0
}
.cfg-arr-btn.remove:hover {
  color:#e74c3c;
  border-color:#e74c3c
}
.cfg-arr-btn.add {
  margin-top:4px;
  align-self:flex-start
}
@media(max-width:767px) {
  .cfg-row {
  flex-wrap:wrap;
  gap:4px
}
.cfg-key {
  min-width:80px;
  max-width:none;
  width:100%;
  font-size:11px
}
.cfg-input {
  max-width:none;
  width:100%
}
.cfg-input.num {
  max-width:none
}
.cfg-comment {
  width:100%;
  white-space:normal
}
.cfg-group>.cfg-section {
  padding-left:10px
}
.cfg-array-item {
  flex-wrap:wrap
}
}
.uninstall-tag {
  color:#ff453a !important;
  border-color:#ff453a4d !important;
  cursor:pointer
}
.uninstall-tag:hover {
  border-color:#ff453a !important;
  background:#ff453a1a
}
.p-uninstall-confirm {
  background:var(--bg);
  border:1px solid var(--border);
  border-radius:12px;
  padding:20px 24px;
  width:340px;
  max-width:90vw
}
.p-uninstall-title {
  font-size:15px;
  font-weight:600;
  color:var(--text);
  margin-bottom:8px
}
.p-uninstall-msg {
  font-size:13px;
  color:var(--text2);
  margin-bottom:14px;
  line-height:1.5
}
.p-uninstall-check {
  display:flex;
  align-items:center;
  gap:6px;
  font-size:13px;
  color:var(--text2);
  margin-bottom:16px;
  cursor:pointer
}
.p-uninstall-check input[type="checkbox"] {
  width:15px;
  height:15px;
  accent-color:var(--accent)
}
.p-uninstall-btns {
  display:flex;
  justify-content:flex-end;
  gap:8px
}
.p-btn.danger {
  color:#fff;
  background:#ff453a;
  border-color:#ff453a
}
.p-btn.danger:hover {
  background:#e03e34
}
.p-btn.danger:disabled {
  opacity:.5;
  cursor:default
}
.p-file-meta {
  font-size:11px;
  color:var(--text3);
  margin-left:4px
}
.p-act-btn.danger-btn {
  color:#ff453a
}
.p-act-btn.danger-btn:hover {
  background:#ff453a1a
}
</style>
