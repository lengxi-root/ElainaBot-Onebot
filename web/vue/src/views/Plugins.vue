<template>
  <div class="plugins-page">
    <!-- Toolbar -->
    <div class="plugins-toolbar">
      <input class="p-search" type="text" v-model="searchText" placeholder="搜索插件..." />
      <button class="p-btn upload-btn" @click="showUpload = true">上传</button>
      <button class="p-btn" @click="showCreate = true">新建</button>
      <button class="p-btn" @click="loadPlugins">刷新</button>
    </div>

    <!-- Plugin List (directory-based) -->
    <div class="plugins-list" v-if="!loading">
      <div v-for="dir in filteredDirs" :key="dir.name" class="p-dir">
        <div class="p-dir-head" @click="dir._open = !dir._open">
          <div class="p-dir-title">
            <SvgIcon name="chevron" :size="14" :style="{ transform: dir._open ? 'rotate(0)' : 'rotate(-90deg)', transition: '0.15s' }" />
            <span>{{ dir.name }}</span>
            <span class="p-dir-count">{{ dir.plugins.length }}</span>
          </div>
          <span class="p-dir-status" :class="dir.loaded ? 'loaded' : 'unloaded'">
            {{ dir.loaded ? '已加载' : '未加载' }}
          </span>
        </div>
        <div class="p-dir-body" v-show="dir._open">
          <div v-for="file in dir.plugins" :key="file.path" class="p-file" @click="openEditor(file)">
            <span class="p-file-name">{{ file.name }}</span>
            <span class="p-file-meta">{{ file.handlers || 0 }} 处理器</span>
          </div>
          <div v-if="!dir.plugins.length" class="p-empty-inline">无插件文件</div>
        </div>
      </div>
      <div v-if="!filteredDirs.length" class="p-empty">暂无插件</div>
    </div>
    <div v-else class="p-loading">加载中...</div>

    <!-- Editor Modal -->
    <div v-if="editorFile" class="modal-mask" @click.self="closeEditor">
      <div class="editor-modal">
        <div class="editor-header">
          <span class="editor-title">{{ editorFile.path }}</span>
          <div class="editor-actions">
            <button class="p-btn save-btn" @click="saveFile" :disabled="saving">保存</button>
            <button class="p-btn" @click="closeEditor">关闭</button>
          </div>
        </div>
        <textarea
          class="code-editor"
          v-model="editorContent"
          spellcheck="false"
          @keydown.tab.prevent="insertTab"
        ></textarea>
        <div class="editor-status" v-if="editorMsg" :class="editorMsgType">{{ editorMsg }}</div>
      </div>
    </div>

    <!-- Upload Modal -->
    <div v-if="showUpload" class="modal-mask" @click.self="showUpload = false">
      <div class="small-modal">
        <h3>上传插件</h3>
        <p class="modal-desc">支持 .py 文件或 .zip 压缩包</p>
        <input type="file" accept=".py,.zip" @change="handleUpload" />
        <div class="modal-footer">
          <button class="p-btn" @click="showUpload = false">取消</button>
        </div>
      </div>
    </div>

    <!-- Create Modal -->
    <div v-if="showCreate" class="modal-mask" @click.self="showCreate = false">
      <div class="small-modal">
        <h3>新建插件</h3>
        <div class="form-group">
          <label>目录名</label>
          <input class="input" v-model="newDir" placeholder="my_plugin" />
        </div>
        <div class="form-group">
          <label>文件名</label>
          <input class="input" v-model="newFile" placeholder="main.py" />
        </div>
        <div class="modal-footer">
          <button class="p-btn" @click="showCreate = false">取消</button>
          <button class="p-btn save-btn" @click="createPlugin">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import SvgIcon from '../components/SvgIcon.vue'

const store = useAppStore()
const dirs = ref([])
const loading = ref(false)
const searchText = ref('')
const editorFile = ref(null)
const editorContent = ref('')
const editorMsg = ref('')
const editorMsgType = ref('')
const saving = ref(false)
const showUpload = ref(false)
const showCreate = ref(false)
const newDir = ref('')
const newFile = ref('main.py')

const filteredDirs = computed(() => {
  if (!searchText.value) return dirs.value
  const q = searchText.value.toLowerCase()
  return dirs.value.filter(d =>
    d.name.toLowerCase().includes(q) || d.plugins.some(p => p.name.toLowerCase().includes(q))
  )
})

async function loadPlugins() {
  loading.value = true
  const res = await store.fetchApi('/plugins/scan')
  if (res && res.success) {
    dirs.value = (res.plugins || []).map(d => ({ ...d, _open: true }))
  }
  loading.value = false
}

async function openEditor(file) {
  const res = await store.postApi('/plugins/read', { path: file.path })
  if (res && res.success) {
    editorFile.value = file
    editorContent.value = res.content || ''
    editorMsg.value = ''
  }
}

function closeEditor() { editorFile.value = null }

async function saveFile() {
  saving.value = true
  editorMsg.value = ''
  const res = await store.postApi('/plugins/save', { path: editorFile.value.path, content: editorContent.value })
  if (res && res.success) {
    editorMsg.value = '保存成功'
    editorMsgType.value = 'success'
  } else {
    editorMsg.value = res?.error || '保存失败'
    editorMsgType.value = 'error'
  }
  saving.value = false
}

function insertTab(e) {
  const ta = e.target
  const start = ta.selectionStart
  const end = ta.selectionEnd
  editorContent.value = editorContent.value.substring(0, start) + '  ' + editorContent.value.substring(end)
  setTimeout(() => { ta.selectionStart = ta.selectionEnd = start + 2 }, 0)
}

async function handleUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  const form = new FormData()
  form.append('file', file)
  const token = localStorage.getItem('elaina_token')
  const res = await fetch('/api/plugins/upload', { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form })
  const data = await res.json()
  if (data.success) { showUpload.value = false; loadPlugins() }
}

async function createPlugin() {
  if (!newDir.value) return
  const res = await store.postApi('/plugins/create', { dir: newDir.value, filename: newFile.value || 'main.py' })
  if (res && res.success) { showCreate.value = false; loadPlugins() }
}

onMounted(() => { loadPlugins() })
</script>

<style scoped>
.plugins-page { display: flex; flex-direction: column; }
.plugins-toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.p-search {
  flex: 1; max-width: 260px; background: var(--bg2); color: var(--text);
  border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; font-size: 13px; outline: none;
}
.p-search:focus { border-color: var(--accent); }
.p-btn {
  display: flex; align-items: center; gap: 4px; padding: 6px 12px;
  border: 1px solid var(--border); border-radius: 6px; background: transparent;
  color: var(--text2); cursor: pointer; font-size: 12px;
}
.p-btn:hover { color: var(--text); border-color: var(--text3); }
.p-btn:disabled { opacity: 0.4; cursor: default; }
.upload-btn { background: var(--accent); color: #fff; border-color: var(--accent); }
.upload-btn:hover { opacity: 0.9; }
.save-btn { background: var(--accent); color: #fff; border-color: var(--accent); }
.save-btn:hover { opacity: 0.9; }

.plugins-list { display: flex; flex-direction: column; gap: 6px; padding-bottom: 40px; }
.p-loading, .p-empty { text-align: center; color: var(--text3); padding: 40px 0; font-size: 13px; }
.p-empty-inline { text-align: center; color: var(--text3); padding: 12px 0; font-size: 12px; }

.p-dir { background: var(--bg2); border: 1px solid var(--border); border-radius: 10px; overflow: clip; }
.p-dir-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; cursor: pointer; user-select: none; gap: 8px;
}
.p-dir-title { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: var(--text); }
.p-dir-count { font-size: 11px; color: var(--text3); font-weight: 400; }
.p-dir-status { font-size: 11px; padding: 2px 8px; border-radius: 4px; }
.p-dir-status.loaded { background: #dcfce7; color: #166534; }
.p-dir-status.unloaded { background: var(--bg3); color: var(--text3); }

.p-dir-body { border-top: 1px solid var(--border); }
.p-file {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px 8px 28px; cursor: pointer; transition: background 0.12s;
  font-size: 13px;
}
.p-file:hover { background: var(--bg3); }
.p-file-name { color: var(--text); }
.p-file-meta { color: var(--text3); font-size: 11px; }

/* Modal */
.modal-mask {
  position: fixed; inset: 0; background: rgba(0,0,0,0.3);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.editor-modal {
  width: 90vw; max-width: 900px; height: 80vh;
  background: var(--bg); border-radius: 10px; display: flex; flex-direction: column; overflow: hidden;
  border: 1px solid var(--border);
}
.editor-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; border-bottom: 1px solid var(--border);
}
.editor-title { font-size: 13px; color: var(--text); font-weight: 500; }
.editor-actions { display: flex; gap: 6px; }
.code-editor {
  flex: 1; resize: none; padding: 12px; background: var(--bg2); color: var(--text);
  border: none; font-family: var(--font-mono); font-size: 13px; line-height: 1.6;
  tab-size: 2; outline: none;
}
.editor-status { padding: 6px 16px; font-size: 12px; border-top: 1px solid var(--border); }
.editor-status.success { color: var(--success); }
.editor-status.error { color: var(--danger); }

.small-modal {
  width: 380px; background: var(--bg); border-radius: 10px; padding: 20px;
  border: 1px solid var(--border);
}
.small-modal h3 { font-size: 16px; margin-bottom: 8px; color: var(--text); }
.modal-desc { font-size: 12px; color: var(--text2); margin-bottom: 12px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 12px; color: var(--text2); margin-bottom: 4px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
</style>
