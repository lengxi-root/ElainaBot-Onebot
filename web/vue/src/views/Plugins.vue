<template>
  <div class="plugins-page">
    <header class="page-header">
      <div class="page-header-row">
        <div>
          <h1>插件管理</h1>
          <p class="subtitle">管理 OneBot 插件</p>
        </div>
        <div class="header-actions">
          <button class="btn btn-secondary" @click="showUpload = true">上传</button>
          <button class="btn btn-secondary" @click="showCreate = true">新建</button>
          <button class="btn btn-secondary" @click="loadPlugins">刷新</button>
        </div>
      </div>
    </header>

    <!-- Upload Dialog -->
    <div v-if="showUpload" class="modal-overlay" @click.self="showUpload = false">
      <div class="modal card">
        <h3>上传插件</h3>
        <p class="modal-desc">支持 .py 文件或 .zip 压缩包</p>
        <input type="file" ref="uploadInput" accept=".py,.zip" @change="onUploadFile" />
        <div class="modal-actions">
          <button class="btn btn-secondary" @click="showUpload = false">取消</button>
        </div>
      </div>
    </div>

    <!-- Create Dialog -->
    <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
      <div class="modal card">
        <h3>新建插件</h3>
        <label>目录名</label>
        <input v-model="newDir" class="input" placeholder="my_plugin" />
        <label>文件名</label>
        <input v-model="newFile" class="input" placeholder="main.py" />
        <div class="modal-actions">
          <button class="btn btn-secondary" @click="showCreate = false">取消</button>
          <button class="btn btn-primary" @click="createPlugin">创建</button>
        </div>
      </div>
    </div>

    <!-- Plugin List -->
    <div class="plugins-grid">
      <div v-for="plugin in plugins" :key="plugin.name" class="card plugin-card">
        <div class="plugin-header">
          <h3>{{ plugin.meta?.name || plugin.name }}</h3>
          <span class="badge" :class="plugin.enabled ? 'badge-success' : 'badge-danger'">
            {{ plugin.enabled ? '已加载' : '未加载' }}
          </span>
        </div>
        <p v-if="plugin.description" class="plugin-desc">{{ plugin.description }}</p>
        <div class="plugin-meta">
          <span v-if="plugin.meta?.version">v{{ plugin.meta.version }}</span>
          <span v-if="plugin.meta?.author">{{ plugin.meta.author }}</span>
          <span>{{ plugin.handlers }} 个处理器</span>
        </div>

        <!-- Files -->
        <div v-if="plugin.files && plugin.files.length" class="plugin-files">
          <div v-for="file in plugin.files" :key="file.name" class="file-item" @click="openFile(file)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            <span>{{ file.name }}</span>
            <span class="file-size">{{ fmtSize(file.size) }}</span>
          </div>
        </div>

        <div class="plugin-actions">
          <button @click="reloadPlugin(plugin.name)" class="btn btn-secondary btn-sm">重载</button>
        </div>
      </div>
      <p v-if="!plugins.length" class="empty-text">暂无插件。将插件目录放入 <code>plugins/</code> 即可自动加载。</p>
    </div>

    <!-- Code Editor Modal -->
    <div v-if="editingFile" class="modal-overlay editor-overlay" @click.self="closeEditor">
      <div class="modal card editor-modal">
        <div class="editor-header">
          <h3>{{ editingFile.filename }}</h3>
          <div class="editor-actions">
            <button class="btn btn-primary btn-sm" @click="saveFile" :disabled="!editorChanged">保存</button>
            <button class="btn btn-secondary btn-sm" @click="closeEditor">关闭</button>
          </div>
        </div>
        <textarea
          v-model="editorContent"
          @input="editorChanged = true"
          class="code-editor"
          spellcheck="false"
        ></textarea>
        <p v-if="editorMsg" class="editor-msg" :class="{ error: editorError }">{{ editorMsg }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const plugins = ref([])
const showUpload = ref(false)
const showCreate = ref(false)
const newDir = ref('')
const newFile = ref('main.py')
const uploadInput = ref(null)

const editingFile = ref(null)
const editorContent = ref('')
const editorChanged = ref(false)
const editorMsg = ref('')
const editorError = ref(false)

async function loadPlugins() {
  const res = await store.fetchApi('/plugins/scan')
  if (res && res.success) {
    plugins.value = res.plugins || []
  }
}

async function reloadPlugin(name) {
  await store.postApi('/plugins/reload', { name })
  await loadPlugins()
}

async function openFile(file) {
  const res = await store.postApi('/plugins/read', { path: file.path })
  if (res && res.success) {
    editingFile.value = { path: file.path, filename: res.filename }
    editorContent.value = res.content
    editorChanged.value = false
    editorMsg.value = ''
  }
}

async function saveFile() {
  const res = await store.postApi('/plugins/save', {
    path: editingFile.value.path,
    content: editorContent.value,
  })
  if (res && res.success) {
    editorMsg.value = '保存成功'
    editorError.value = false
    editorChanged.value = false
  } else {
    editorMsg.value = res?.message || '保存失败'
    editorError.value = true
  }
}

function closeEditor() {
  editingFile.value = null
}

async function createPlugin() {
  if (!newDir.value) return
  const res = await store.postApi('/plugins/create', {
    directory: newDir.value,
    filename: newFile.value || 'main.py',
  })
  if (res && res.success) {
    showCreate.value = false
    newDir.value = ''
    newFile.value = 'main.py'
    await loadPlugins()
  }
}

async function onUploadFile() {
  const file = uploadInput.value?.files?.[0]
  if (!file) return
  const form = new FormData()
  form.append('file', file)
  const token = localStorage.getItem('elaina_token')
  try {
    const res = await fetch('/api/plugins/upload', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    })
    const data = await res.json()
    if (data.success) {
      showUpload.value = false
      await loadPlugins()
    }
  } catch (e) {}
}

function fmtSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  return (bytes / 1024).toFixed(1) + ' KB'
}

onMounted(loadPlugins)
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 22px; font-weight: 700; }
.subtitle { color: var(--color-text-muted); font-size: 13px; margin-top: 2px; }
.page-header-row { display: flex; align-items: flex-start; justify-content: space-between; }
.header-actions { display: flex; gap: 8px; }

.plugins-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px;
}

.plugin-card { padding: 16px; }
.plugin-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
.plugin-header h3 { font-size: 14px; font-weight: 600; }
.plugin-desc { font-size: 12px; color: var(--color-text-muted); margin-bottom: 8px; }
.plugin-meta { display: flex; gap: 12px; font-size: 12px; color: var(--color-text-muted); margin-bottom: 8px; }

.plugin-files { margin-bottom: 8px; }
.file-item {
  display: flex; align-items: center; gap: 6px; padding: 4px 8px;
  font-size: 12px; cursor: pointer; border-radius: 4px; transition: background var(--transition);
}
.file-item:hover { background: var(--color-bg-secondary); }
.file-item svg { color: var(--color-text-muted); flex-shrink: 0; }
.file-size { margin-left: auto; color: var(--color-text-muted); }

.plugin-actions { display: flex; gap: 8px; }
.btn-sm { font-size: 12px; padding: 4px 10px; }

/* Modal */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 200;
  display: flex; align-items: center; justify-content: center;
}
.modal { padding: 24px; width: 400px; max-width: 90vw; }
.modal h3 { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.modal-desc { font-size: 13px; color: var(--color-text-muted); margin-bottom: 12px; }
.modal label { display: block; font-size: 13px; font-weight: 500; margin-bottom: 4px; margin-top: 8px; }
.input {
  width: 100%; padding: 8px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm);
  font-size: 13px; outline: none; font-family: inherit; background: var(--color-bg);
}
.input:focus { border-color: var(--color-primary); }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

/* Editor Modal */
.editor-overlay { align-items: stretch; padding: 40px; }
.editor-modal { width: 100%; max-width: 900px; display: flex; flex-direction: column; margin: auto; }
.editor-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.editor-header h3 { font-size: 14px; font-weight: 600; }
.editor-actions { display: flex; gap: 8px; }
.code-editor {
  flex: 1; min-height: 400px; padding: 16px; border: 1px solid var(--color-border);
  border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: 13px;
  line-height: 1.6; resize: vertical; outline: none; background: var(--color-bg-secondary);
  color: var(--color-text);
}
.editor-msg { font-size: 12px; margin-top: 8px; color: var(--color-success); }
.editor-msg.error { color: var(--color-danger); }

.empty-text {
  color: var(--color-text-muted); font-size: 13px; grid-column: 1 / -1;
  text-align: center; padding: 40px;
}
.empty-text code {
  background: var(--color-bg-tertiary); padding: 2px 6px; border-radius: 4px;
  font-family: var(--font-mono); font-size: 12px;
}
</style>
