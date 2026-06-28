<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import yaml from 'js-yaml'
import axios from '../utils/axios'

const message = useMessage()
const loading = ref(false)
const saving = ref(false)
const dirty = ref(false)
const viewMode = ref('visual')
const raw = reactive({ settings: '' })

function parse(text) { try { return yaml.load(text) || {} } catch { return {} } }
function dump(obj) { try { return yaml.dump(obj, { lineWidth: -1, noRefs: true, sortKeys: false, quotingType: '"' }) } catch { return '' } }

const settings = computed(() => parse(raw.settings))

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

// API
async function fetchConfig() {
  loading.value = true
  try {
    const res = await axios.get('/api/config')
    raw.settings = res.data.settings || ''
    dirty.value = false
  } catch { message.error('获取配置失败') }
  finally { loading.value = false }
}

async function saveConfig() {
  saving.value = true
  try {
    const res = await axios.post('/api/config/save', { file: 'settings', content: raw.settings })
    if (res.data.success) { message.success('配置已保存，部分更改需要重启生效'); dirty.value = false }
    else message.error(res.data.error || '保存失败')
  } catch (e) { message.error('保存失败: ' + (e.message || '')) }
  finally { saving.value = false }
}

onMounted(fetchConfig)
</script>

<template>
  <div class="config-page">
    <div class="config-tabs">
      <span class="config-tab active">settings.yaml</span>
      <span class="config-tabs-spacer" />
      <button :class="['cfg-btn', { active: viewMode === 'visual' }]" @click="viewMode = 'visual'">可视化</button>
      <button :class="['cfg-btn', { active: viewMode === 'yaml' }]" @click="viewMode = 'yaml'">YAML</button>
      <button class="cfg-btn save" @click="saveConfig" :disabled="!dirty || saving">{{ saving ? '保存中...' : '保存' }}</button>
      <button class="cfg-btn" @click="fetchConfig" :disabled="loading">刷新</button>
    </div>

    <template v-if="viewMode === 'visual'">
      <div class="visual-body">
        <div class="vis-card">
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
            <div class="vis-field"><label>保留天数</label><input type="number" :value="settings.logging?.retention_days ?? 30" @input="updateSettingNum('logging', 'retention_days', $event)" /></div>
            <div class="vis-field full"><label>WAL 模式</label><label class="vis-switch"><input type="checkbox" :checked="settings.logging?.wal_mode !== false" @change="updateSettingBool('logging', 'wal_mode', $event)" /><span /></label></div>
          </div>
          <div class="vis-card-title" style="margin-top:14px">依赖管理</div>
          <div class="vis-grid">
            <div class="vis-field full"><label>自动安装依赖</label><label class="vis-switch"><input type="checkbox" :checked="settings.pip?.auto_install !== false" @change="updateSettingBool('pip', 'auto_install', $event)" /><span /></label></div>
            <div class="vis-field"><label>pip 镜像源</label><input :value="settings.pip?.mirror || ''" @input="updateSetting('pip', 'mirror', $event)" placeholder="留空用默认" /></div>
          </div>
        </div>
      </div>
    </template>

    <!-- YAML mode -->
    <div v-else class="config-body">
      <div class="editor-wrap">
        <div class="editor-hint">
          <span>编辑 settings.yaml</span>
          <span v-if="dirty" class="editor-hint-r">• 未保存</span>
        </div>
        <textarea class="yaml-editor" v-model="raw.settings" @input="dirty = true" spellcheck="false" />
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
  font-size:13px
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
.vis-grid {
  display:grid;
  grid-template-columns:1fr 1fr;
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
.vis-grid {
  grid-template-columns:1fr
}
}
</style>
