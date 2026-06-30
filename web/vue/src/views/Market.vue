<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import axios from '../utils/axios'
import SvgIcon from '../components/SvgIcon.vue'

const msg = useMessage()
const items = ref([])
const search = ref('')
const category = ref('')
const type = ref('complete')
const loading = ref(false)
const error = ref('')
const preview = reactive({ show: false, name: '', type: '', content: '', files: [], loading: false, error: '' })
// 规范化清单类型: complete(完整插件) / single(独立插件) / module(模块)
function normType(i) { const t = (i.type || '').toLowerCase(); if (t === 'module') return 'module'; if (t === 'single' || t === 'standalone' || t === 'alone') return 'single'; return 'complete' }
const isModule = computed(() => type.value === 'module')

// ── 镜像选择 ──
const mirrorShow = ref(false)
const mirrorList = ref([])       // 全部镜像 URL
const fastMirrors = ref([])      // 缓存的测速结果 [{mirror, latency, success}]
const selectedMirror = ref('')   // 当前选中的镜像
const mirrorTesting = ref('')    // 正在测试的镜像 URL

function mirrorLabel(m) {
  if (!m) return '直连 GitHub'
  try { return new URL(m).hostname } catch { return m.slice(0, 30) }
}
function mirrorLatency(m) {
  const r = fastMirrors.value.find(x => (typeof x === 'string' ? x : x.mirror) === m)
  if (!r) return ''
  const ms = typeof r === 'object' ? r.latency : null
  return ms != null ? `${(ms * 1000).toFixed(0)}ms` : ''
}
async function fetchMirror() {
  try {
    const res = await axios.get('/api/market/mirror')
    if (res.data.success) {
      mirrorList.value = res.data.mirrors || []
      fastMirrors.value = res.data.fast_mirrors || []
      selectedMirror.value = res.data.mirror || ''
    }
  } catch {}
}
async function setMirror(m) {
  selectedMirror.value = m
  mirrorShow.value = false
  try {
    await axios.post('/api/market/mirror', { mirror: m })
    msg.success(`镜像已设为: ${mirrorLabel(m)}`)
  } catch { msg.error('设置镜像失败') }
}
async function testMirror(m) {
  mirrorTesting.value = m
  try {
    const res = await axios.post('/api/market/mirror/test', { mirror: m })
    if (res.data.success && res.data.data) {
      const r = res.data.data
      const idx = fastMirrors.value.findIndex(x => (typeof x === 'string' ? x : x.mirror) === m)
      if (idx >= 0) fastMirrors.value[idx] = r; else fastMirrors.value.push(r)
      msg.info(`${mirrorLabel(m)}: ${r.success ? (r.latency * 1000).toFixed(0) + 'ms' : '不可用'}`)
    }
  } catch { msg.error('测试失败') }
  finally { mirrorTesting.value = '' }
}

watch(type, () => { category.value = '' })

const filtered = computed(() => {
  let list = items.value.filter(i => normType(i) === type.value)
  if (category.value) list = list.filter(i => i.category === category.value)
  const q = search.value.toLowerCase()
  if (q) list = list.filter(i => (i.name || '').toLowerCase().includes(q) || (i.description || '').toLowerCase().includes(q) || (i.author || '').toLowerCase().includes(q) || (i.tags || []).some(t => t.toLowerCase().includes(q)))
  return list
})

const categories = computed(() => {
  const list = items.value.filter(i => normType(i) === type.value)
  return [...new Set(list.map(i => i.category).filter(Boolean))]
})

function avatarUrl(item) { const m = (item.github || '').match(/github\.com\/([^/]+)/); return m ? `https://github.com/${m[1]}.png?size=80` : '' }
function isOfficial(item) { return (item.github || '').includes('ElainaCore/') || (item.author || '').toLowerCase() === 'elainabot' }
function filteredTags(item) { const cat = (item.category || '').toLowerCase(); return (item.tags || []).filter(t => t.toLowerCase() !== cat) }
function formatSize(s) { return s ? s < 1024 ? s + ' B' : s < 1024 * 1024 ? (s / 1024).toFixed(1) + ' KB' : (s / (1024 * 1024)).toFixed(1) + ' MB' : '' }

async function fetchList() {
  loading.value = true; error.value = ''
  try { const res = await axios.get('/api/market/list'); if (res.data.success) items.value = (res.data.data || []).map(i => ({ ...i, _installing: false, _previewing: false, _uninstalling: false })); else error.value = res.data.message || '获取插件列表失败' }
  catch { error.value = '无法连接插件库, 请检查网络' }
  finally { loading.value = false }
}

async function refresh() {
  loading.value = true; error.value = ''
  try { const res = await axios.post('/api/market/refresh'); if (res.data.success) { msg.success(res.data.message || '已刷新'); await fetchList() } else { error.value = res.data.message || '刷新失败'; loading.value = false } }
  catch { error.value = '刷新失败'; loading.value = false }
}

async function previewItem(item) {
  let url = item.path ? '' : item.github || item.download_url || ''
  if (item.path && item.github) { const m = item.github.match(/github\.com\/([^/]+)\/([^/]+)/); if (m) url = `https://raw.githubusercontent.com/${m[1]}/${m[2]}/${item.branch || 'main'}/${item.path}` }
  if (!url) { msg.warning('无可预览地址'); return }
  Object.assign(preview, { show: true, name: item.name, type: '', content: '', files: [], loading: true, error: '' })
  try { const res = await axios.post('/api/market/preview', { url }); if (res.data.success) { preview.type = res.data.type || 'py'; res.data.files ? preview.files = res.data.files : preview.content = res.data.content || '' } else preview.error = res.data.message || '预览失败' }
  catch { preview.error = '预览请求失败' }
  finally { preview.loading = false }
}

// 插件市场尚未适配 OneBot 协议, 当前插件并不通用, 暂时标记为"等待开发"并禁用安装
const MARKET_WIP = true

async function install(item) {
  if (MARKET_WIP) { msg.warning('插件市场正在开发中，当前插件尚未适配 OneBot，暂不可安装'); return }
  if (item._installing) return; item._installing = true
  try { const res = await axios.post('/api/market/install', { name: item.name, type: normType(item), github: item.github || '', url: item.download_url || '', path: item.path || '', alone: item.alone !== false, branch: item.branch || 'main', mirror: selectedMirror.value }); if (res.data.success) { msg.success(res.data.message || `${item.name} 安装成功`); await fetchList() } else msg.error(res.data.message || '安装失败') }
  catch { msg.error('安装请求失败') }
  finally { item._installing = false }
}

async function uninstall(item) {
  if (item._uninstalling) return; item._uninstalling = true
  try { const res = await axios.post('/api/market/uninstall', { name: item.name, type: normType(item) }); if (res.data.success) { msg.success(res.data.message || `${item.name} 已卸载`); await fetchList() } else msg.error(res.data.message || '卸载失败') }
  catch { msg.error('卸载请求失败') }
  finally { item._uninstalling = false }
}

onMounted(() => { fetchList(); fetchMirror() })
</script>

<template>
  <div class="market-page">
    <div class="market-toolbar">
      <div class="market-title">
        <SvgIcon name="storefront" :size="18" /><span>插件市场</span>
        <span v-if="items.length" class="market-count">{{ filtered.length }}</span>
      </div>
      <div class="market-actions">
        <select v-model="type" class="m-select"><option value="complete">完整插件</option><option value="single">独立插件</option><option value="module">模块</option></select>
        <select v-model="category" class="m-select"><option value="">全部分类</option><option v-for="c in categories" :key="c" :value="c">{{ c }}</option></select>
        <input v-model="search" class="m-search" placeholder="搜索..." />
        <div class="m-mirror-wrap">
          <button class="m-btn" @click="mirrorShow = !mirrorShow" :title="'当前镜像: ' + mirrorLabel(selectedMirror)">
            <SvgIcon name="globe" :size="14" /><span>{{ mirrorLabel(selectedMirror) }}</span>
          </button>
          <div v-if="mirrorShow" class="m-mirror-backdrop" @click="mirrorShow = false"></div>
          <div v-if="mirrorShow" class="m-mirror-dropdown">
            <div class="m-mirror-title">选择下载镜像</div>
            <div :class="['m-mirror-item', { active: selectedMirror === '' }]" @click="setMirror('')">
              <span class="m-mirror-name">自动选择</span>
              <span class="m-mirror-ms">{{ mirrorLatency('') }}</span>
            </div>
            <div v-for="m in mirrorList" :key="m" :class="['m-mirror-item', { active: selectedMirror === m }]">
              <span class="m-mirror-name" @click="setMirror(m)">{{ mirrorLabel(m) }}</span>
              <span class="m-mirror-ms" @click="setMirror(m)">{{ mirrorLatency(m) }}</span>
              <button class="m-mirror-test" @click.stop="testMirror(m)" :disabled="mirrorTesting === m">{{ mirrorTesting === m ? '...' : '测试' }}</button>
            </div>
          </div>
        </div>
        <button class="m-btn" @click="refresh" :disabled="loading"><SvgIcon name="refresh" :size="14" /><span>刷新</span></button>
        <a href="https://github.com/ElainaCore/ElainaOnebot-plugins" target="_blank" class="m-btn submit"><SvgIcon name="upload" :size="14" /><span>投稿</span></a>
      </div>
    </div>
    <div v-if="MARKET_WIP" class="m-wip"><SvgIcon name="alert-circle" :size="15" /><span><b>等待开发：</b>插件市场尚未适配 OneBot 协议，当前插件并不通用，安装功能暂时关闭，敬请期待。</span></div>
    <div class="m-disclaimer"><SvgIcon name="alert-circle" :size="13" /><span>第三方插件由社区开发者提供，请自行辨别插件可用性与安全风险，框架不对第三方插件内容负责。</span></div>

    <div v-if="loading" class="m-state"><div class="m-spinner" /><span>正在加载插件库...</span></div>
    <div v-else-if="error" class="m-state m-error"><SvgIcon name="alert-circle" :size="20" /><span>{{ error }}</span><button class="m-btn" @click="fetchList">重试</button></div>
    <template v-else>
      <div v-if="filtered.length" class="market-grid">
        <div v-for="item in filtered" :key="item.name" class="m-card">
          <div class="m-card-head">
            <div class="m-card-icon">
              <img v-if="avatarUrl(item)" :src="avatarUrl(item)" class="m-avatar" @error="e => e.target.style.display='none'" />
              <SvgIcon v-else :name="isModule ? 'cube' : 'extension-puzzle'" :size="20" />
            </div>
            <div class="m-card-info">
              <div class="m-card-name">{{ item.name }}</div>
              <div class="m-card-author">{{ item.author || '未知作者' }}<span v-if="isOfficial(item)" class="m-official">官方</span></div>
            </div>
            <span v-if="item.has_update" class="m-update-badge">有更新</span>
            <span v-else-if="item.installed" class="m-installed-badge">已安装</span>
            <div v-if="item.version" class="m-card-version"><span v-if="item.local_version && item.local_version !== item.version">v{{ item.local_version }} → </span>v{{ item.version }}</div>
          </div>
          <div class="m-card-desc">{{ item.description || '暂无描述' }}</div>
          <div v-if="item.tags?.length || item.category" class="m-card-tags">
            <span v-if="item.category" class="m-tag cat">{{ item.category }}</span>
            <span v-for="t in filteredTags(item)" :key="t" class="m-tag">{{ t }}</span>
          </div>
          <div class="m-card-foot">
            <a v-if="item.github" :href="item.github" target="_blank" class="m-link" title="GitHub"><SvgIcon name="globe" :size="14" /><span>仓库</span></a>
            <template v-if="!isModule"><span v-if="normType(item) === 'single'" class="m-type-badge" :title="item.alone === false ? '独立文件夹 plugins/' + item.name + '/' : '共享 plugins/alone/'">独立</span><span v-else class="m-type-badge repo">完整</span></template>
            <div class="m-card-btns">
              <button v-if="!isModule && (item.path || item.github)" class="m-btn sm preview" @click="previewItem(item)" :disabled="item._previewing"><SvgIcon name="code" :size="13" /> 预览</button>
              <button v-if="item.installed" class="m-btn sm uninstall" @click="uninstall(item)" :disabled="item._uninstalling || (!isModule && item.name === 'system')"><SvgIcon name="trash" :size="13" /> {{ item._uninstalling ? '卸载中...' : '卸载' }}</button>
              <button :class="['m-btn sm install', { update: item.has_update }]" @click="install(item)" :disabled="item._installing || MARKET_WIP"><SvgIcon name="cloud-download" :size="13" /> {{ MARKET_WIP ? '等待开发' : item._installing ? '安装中...' : item.has_update ? '更新' : item.installed ? '重装' : '安装' }}</button>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="m-state"><SvgIcon name="search" :size="20" /><span>{{ search || category ? '没有匹配的结果' : '暂无内容' }}</span></div>
    </template>

    <!-- Preview modal -->
    <div v-if="preview.show" class="m-modal-overlay" @click.self="preview.show = false">
      <div class="m-modal">
        <div class="m-modal-head">
          <div class="m-modal-title"><SvgIcon name="code" :size="16" /><span>{{ preview.name }}</span><span v-if="preview.type" class="m-tag">{{ preview.type }}</span></div>
          <button class="m-btn sm close" @click="preview.show = false"><SvgIcon name="x" :size="14" /></button>
        </div>
        <div class="m-modal-body">
          <div v-if="preview.loading" class="m-state" style="padding:40px 0"><div class="m-spinner" /><span>加载中...</span></div>
          <template v-else-if="preview.files?.length">
            <div v-for="f in preview.files" :key="f.name" class="m-preview-file">
              <div class="m-preview-fname">{{ f.name }} <span class="m-preview-size">{{ formatSize(f.size) }}</span></div>
              <pre class="m-preview-code">{{ f.content }}</pre>
            </div>
          </template>
          <pre v-else-if="preview.content" class="m-preview-code">{{ preview.content }}</pre>
          <div v-else class="m-state" style="padding:40px 0"><span>{{ preview.error || '无法预览' }}</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.market-page {
  display:flex;
  flex-direction:column;
  height:calc(100vh - 100px);
  overflow-y:auto
}
.market-toolbar {
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  margin-bottom:16px;
  flex-wrap:wrap
}
.market-title {
  display:flex;
  align-items:center;
  gap:8px;
  font-size:16px;
  font-weight:700;
  color:var(--text)
}
.market-count {
  font-size:12px;
  font-weight:400;
  color:var(--text3)
}
.market-actions {
  display:flex;
  align-items:center;
  gap:8px;
  flex-wrap:wrap
}
.m-disclaimer {
  display:flex;
  align-items:center;
  gap:6px;
  padding:6px 12px;
  margin-bottom:12px;
  background:#ffb30014;
  border:1px solid rgba(255,179,0,.18);
  border-radius:6px;
  font-size:11px;
  color:#ffb300;
  line-height:1.4
}
.m-wip {
  display:flex;
  align-items:center;
  gap:8px;
  padding:10px 14px;
  margin-bottom:10px;
  background:rgba(88,101,242,.1);
  border:1px solid rgba(88,101,242,.35);
  border-radius:8px;
  font-size:13px;
  color:var(--accent, #5865f2);
  line-height:1.5
}
.m-select {
  background:var(--bg2);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:6px;
  padding:6px 8px;
  font-size:13px;
  outline:none;
  cursor:pointer;
  min-width:100px
}
.m-select:focus {
  border-color:var(--accent)
}
.m-search {
  max-width:220px;
  background:var(--bg2);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:6px;
  padding:6px 10px;
  font-size:13px;
  outline:none
}
.m-search:focus {
  border-color:var(--accent)
}
.m-btn {
  display:flex;
  align-items:center;
  gap:4px;
  padding:6px 12px;
  border:1px solid var(--border);
  border-radius:6px;
  background:transparent;
  color:var(--text2);
  cursor:pointer;
  font-size:12px;
  transition:all .15s;
  white-space:nowrap
}
.m-btn:hover {
  color:var(--text);
  border-color:var(--text3)
}
.m-btn:disabled {
  opacity:.4;
  cursor:default
}
.m-btn.sm {
  padding:4px 10px;
  font-size:11px
}
.m-btn.install {
  background:var(--accent);
  color:#fff;
  border-color:var(--accent)
}
.m-btn.install:hover {
  opacity:.9
}
.m-btn.submit {
  text-decoration:none;
  color:var(--accent);
  border-color:var(--accent)
}
.m-btn.close {
  border:none;
  color:var(--text3)
}
.m-btn.close:hover {
  color:#ff453a
}
.m-state {
  display:flex;
  flex-direction:column;
  align-items:center;
  gap:8px;
  color:var(--text3);
  padding:60px 0;
  font-size:13px
}
.m-error {
  color:#ff453a
}
.m-spinner {
  width:24px;
  height:24px;
  border:2px solid var(--border);
  border-top-color:var(--accent);
  border-radius:50%;
  animation:spin-a7d38b85 .6s linear infinite
}
@keyframes spin-a7d38b85 {
  to {
  transform:rotate(360deg)
}
}
.market-grid {
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
  gap:12px;
  align-content:start
}
.m-card {
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:var(--radius);
  box-shadow:var(--shadow-sm);
  padding:18px;
  display:flex;
  flex-direction:column;
  gap:10px;
  transition:transform .15s,box-shadow .15s
}
.m-card:hover {
  transform:translateY(-2px);
  box-shadow:var(--shadow-hover)
}
.m-card-head {
  display:flex;
  align-items:center;
  gap:10px
}
.m-card-icon {
  width:40px;
  height:40px;
  border-radius:10px;
  flex-shrink:0;
  background:linear-gradient(135deg,rgba(var(--accent-rgb,99,102,241),.15),rgba(var(--accent-rgb,99,102,241),.05));
  display:flex;
  align-items:center;
  justify-content:center;
  color:var(--accent);
  overflow:hidden
}
.m-avatar {
  width:100%;
  height:100%;
  -o-object-fit:cover;
  object-fit:cover;
  border-radius:10px
}
.m-card-info {
  flex:1;
  min-width:0
}
.m-card-name {
  font-size:14px;
  font-weight:600;
  color:var(--text);
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap
}
.m-card-author {
  font-size:11px;
  color:var(--text3);
  display:flex;
  align-items:center;
  gap:4px
}
.m-official {
  font-size:9px;
  padding:0 5px;
  border-radius:3px;
  font-weight:600;
  background:linear-gradient(135deg,#5865f233,#7289da26);
  color:#7289da;
  border:1px solid rgba(114,137,218,.25)
}
.m-card-version {
  font-size:10px;
  color:var(--text3);
  background:var(--bg3);
  padding:2px 6px;
  border-radius:4px;
  flex-shrink:0;
  font-family:monospace
}
.m-card-desc {
  font-size:12px;
  color:var(--text2);
  line-height:1.5;
  display:-webkit-box;
  -webkit-line-clamp:2;
  -webkit-box-orient:vertical;
  overflow:hidden
}
.m-card-tags {
  display:flex;
  flex-wrap:wrap;
  gap:4px
}
.m-tag {
  font-size:10px;
  padding:1px 6px;
  border-radius:4px;
  background:var(--bg3);
  color:var(--text3)
}
.m-tag.cat {
  background:rgba(var(--accent-rgb,99,102,241),.12);
  color:var(--accent);
  font-weight:500
}
.m-card-foot {
  display:flex;
  align-items:center;
  gap:8px;
  margin-top:auto;
  padding-top:4px
}
.m-link {
  display:flex;
  align-items:center;
  gap:3px;
  font-size:11px;
  color:var(--text3);
  text-decoration:none;
  transition:.15s
}
.m-link:hover {
  color:var(--accent)
}
.m-type-badge {
  font-size:10px;
  padding:1px 6px;
  border-radius:4px;
  background:#34c7591a;
  color:#34c759
}
.m-type-badge.repo {
  background:rgba(var(--accent-rgb,99,102,241),.1);
  color:var(--accent)
}
.m-type-badge.module {
  background:#ff9f0a1a;
  color:#ff9f0a
}
.m-installed-badge {
  font-size:10px;
  padding:2px 6px;
  border-radius:4px;
  flex-shrink:0;
  background:#34c7591f;
  color:#34c759;
  font-weight:600
}
.m-update-badge {
  font-size:10px;
  padding:2px 6px;
  border-radius:4px;
  flex-shrink:0;
  background:#ff9f0a1f;
  color:#ff9f0a;
  font-weight:600
}
.m-btn.install.update {
  background:#ff9f0a;
  border-color:#ff9f0a
}
.m-btn.uninstall {
  color:#ff453a;
  border-color:#ff453a4d
}
.m-btn.uninstall:hover {
  border-color:#ff453a
}
.m-card-btns {
  display:flex;
  gap:6px;
  margin-left:auto
}
.m-mirror-wrap {
  position:relative
}
.m-mirror-backdrop {
  position:fixed;
  inset:0;
  z-index:199
}
.m-mirror-dropdown {
  position:absolute;
  top:calc(100% + 6px);
  right:0;
  z-index:200;
  width:320px;
  max-height:360px;
  overflow-y:auto;
  background:var(--bg);
  border:1px solid var(--border);
  border-radius:10px;
  box-shadow:0 8px 24px rgba(0,0,0,.25);
  padding:6px 0
}
.m-mirror-title {
  font-size:11px;
  font-weight:600;
  color:var(--text3);
  padding:6px 12px 4px;
  text-transform:uppercase;
  letter-spacing:.5px
}
.m-mirror-item {
  display:flex;
  align-items:center;
  gap:6px;
  padding:6px 12px;
  cursor:pointer;
  font-size:12px;
  color:var(--text2);
  transition:background .1s
}
.m-mirror-item:hover {
  background:var(--bg2)
}
.m-mirror-item.active {
  color:var(--accent);
  font-weight:600
}
.m-mirror-item.active::before {
  content:'✓';
  font-size:11px;
  margin-right:2px
}
.m-mirror-name {
  flex:1;
  min-width:0;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap
}
.m-mirror-ms {
  font-size:10px;
  color:var(--text3);
  font-family:monospace;
  flex-shrink:0
}
.m-mirror-test {
  font-size:10px;
  padding:1px 6px;
  border:1px solid var(--border);
  border-radius:4px;
  background:transparent;
  color:var(--text3);
  cursor:pointer;
  flex-shrink:0;
  transition:all .15s
}
.m-mirror-test:hover {
  color:var(--accent);
  border-color:var(--accent)
}
.m-mirror-test:disabled {
  opacity:.4;
  cursor:default
}
.m-modal-overlay {
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
.m-modal {
  width:90vw;
  max-width:900px;
  height:80vh;
  background:var(--bg);
  border:1px solid var(--border);
  border-radius:12px;
  display:flex;
  flex-direction:column;
  overflow:hidden
}
.m-modal-head {
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:10px 14px;
  background:var(--bg2);
  border-bottom:1px solid var(--border)
}
.m-modal-title {
  display:flex;
  align-items:center;
  gap:6px;
  font-size:13px;
  font-weight:600;
  color:var(--text)
}
.m-modal-body {
  flex:1;
  overflow-y:auto;
  padding:12px
}
.m-preview-file {
  margin-bottom:12px
}
.m-preview-fname {
  font-size:12px;
  font-weight:600;
  color:var(--accent);
  padding:4px 0;
  font-family:Cascadia Code,Fira Code,monospace
}
.m-preview-size {
  font-size:10px;
  color:var(--text3);
  font-weight:400;
  margin-left:8px
}
.m-preview-code {
  background:#1a1a2e;
  color:#e0e0e0;
  border:1px solid rgba(255,255,255,.06);
  border-radius:8px;
  padding:12px 14px;
  font-size:12px;
  line-height:1.6;
  font-family:Cascadia Code,Fira Code,Consolas,monospace;
  overflow-x:auto;
  white-space:pre;
  -moz-tab-size:4;
  -o-tab-size:4;
  tab-size:4;
  margin:0
}
@media(max-width:767px) {
  .market-toolbar {
  flex-direction:column;
  align-items:stretch
}
.market-grid {
  grid-template-columns:1fr
}
.m-modal {
  width:96vw;
  height:85vh
}
}
</style>
