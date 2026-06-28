<template>
  <div class="modules-page">
    <header class="page-header">
      <div class="page-header-row">
        <div>
          <h1>模块管理</h1>
          <p class="subtitle">可选拓展模块</p>
        </div>
        <div class="header-actions">
          <button class="btn btn-secondary" @click="showUpload = true">上传模块</button>
          <button class="btn btn-secondary" @click="loadModules">刷新</button>
        </div>
      </div>
    </header>

    <!-- Upload Dialog -->
    <div v-if="showUpload" class="modal-overlay" @click.self="showUpload = false">
      <div class="modal card">
        <h3>上传模块</h3>
        <p class="modal-desc">上传 .zip 压缩包（包含 main.py 入口文件）</p>
        <input type="file" ref="uploadInput" accept=".zip" @change="onUploadFile" />
        <div class="modal-actions">
          <button class="btn btn-secondary" @click="showUpload = false">取消</button>
        </div>
      </div>
    </div>

    <div class="modules-grid">
      <div v-for="mod in modules" :key="mod.name" class="card module-card">
        <div class="module-header">
          <div>
            <h3>{{ mod.display_name }}</h3>
            <p class="module-desc">{{ mod.description || '无描述' }}</p>
          </div>
          <label class="toggle">
            <input
              type="checkbox"
              :checked="mod.enabled"
              @change="toggleModule(mod.name, !mod.enabled)"
            />
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="module-meta">
          <span v-if="mod.version">v{{ mod.version }}</span>
          <span v-if="mod.author">{{ mod.author }}</span>
          <span v-if="mod.last_modified">{{ mod.last_modified }}</span>
        </div>
        <p v-if="mod.error" class="module-error">{{ mod.error }}</p>
      </div>
      <p v-if="!modules.length" class="empty-text">暂无模块。将模块目录放入 <code>modules/</code> 即可被发现。</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const modules = ref([])
const showUpload = ref(false)
const uploadInput = ref(null)

async function loadModules() {
  const res = await store.fetchApi('/modules/scan')
  if (res && res.success) {
    modules.value = res.modules || []
  }
}

async function toggleModule(name, enabled) {
  await store.postApi('/modules/toggle', { name, enabled })
  await loadModules()
}

async function onUploadFile() {
  const file = uploadInput.value?.files?.[0]
  if (!file) return
  const form = new FormData()
  form.append('file', file)
  const token = localStorage.getItem('elaina_token')
  try {
    const res = await fetch('/api/modules/upload', {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    })
    const data = await res.json()
    if (data.success) {
      showUpload.value = false
      await loadModules()
    }
  } catch (e) {}
}

onMounted(loadModules)
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 22px; font-weight: 700; }
.subtitle { color: var(--color-text-muted); font-size: 13px; margin-top: 2px; }
.page-header-row { display: flex; align-items: flex-start; justify-content: space-between; }
.header-actions { display: flex; gap: 8px; }

.modules-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px;
}

.module-card { padding: 16px; }
.module-header {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 8px;
}
.module-header h3 { font-size: 14px; font-weight: 600; }
.module-desc { font-size: 12px; color: var(--color-text-muted); margin-top: 2px; }
.module-meta { display: flex; gap: 12px; font-size: 11px; color: var(--color-text-muted); }
.module-error {
  margin-top: 8px; font-size: 12px; color: var(--color-danger);
  background: #fee2e2; padding: 6px 10px; border-radius: var(--radius-sm);
}

.toggle { position: relative; width: 40px; height: 22px; flex-shrink: 0; }
.toggle input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
  position: absolute; inset: 0; background: var(--color-border); border-radius: 11px;
  cursor: pointer; transition: background var(--transition);
}
.toggle-slider::before {
  content: ''; position: absolute; width: 16px; height: 16px; border-radius: 50%;
  background: white; top: 3px; left: 3px; transition: transform var(--transition);
}
.toggle input:checked + .toggle-slider { background: var(--color-primary); }
.toggle input:checked + .toggle-slider::before { transform: translateX(18px); }

.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 200;
  display: flex; align-items: center; justify-content: center;
}
.modal { padding: 24px; width: 400px; max-width: 90vw; }
.modal h3 { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.modal-desc { font-size: 13px; color: var(--color-text-muted); margin-bottom: 12px; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 16px; }

.empty-text {
  color: var(--color-text-muted); font-size: 13px; grid-column: 1 / -1;
  text-align: center; padding: 40px;
}
.empty-text code {
  background: var(--color-bg-tertiary); padding: 2px 6px; border-radius: 4px;
  font-family: var(--font-mono); font-size: 12px;
}
</style>
