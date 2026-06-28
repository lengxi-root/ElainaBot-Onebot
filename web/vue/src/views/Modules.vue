<template>
  <div class="modules-page">
    <div class="modules-toolbar">
      <h2>模块管理</h2>
      <div class="modules-actions">
        <button class="p-btn upload-btn" @click="showUpload = true">上传模块</button>
        <button class="p-btn" @click="loadModules">刷新</button>
      </div>
    </div>

    <div class="modules-list" v-if="!loading">
      <div v-for="mod in modules" :key="mod.name" class="mod-card">
        <div class="mod-header">
          <div class="mod-info">
            <span class="mod-name">{{ mod.display_name || mod.name }}</span>
            <span class="mod-desc">{{ mod.description || '无描述' }}</span>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" :checked="mod.enabled" @change="toggleModule(mod)" />
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="mod-meta">
          <span v-if="mod.version">v{{ mod.version }}</span>
          <span v-if="mod.author">{{ mod.author }}</span>
          <span v-if="mod.last_modified">{{ mod.last_modified }}</span>
        </div>
        <div class="mod-error" v-if="mod.error">{{ mod.error }}</div>
      </div>
      <div v-if="!modules.length" class="mod-empty">暂无模块</div>
    </div>
    <div v-else class="mod-empty">加载中...</div>

    <!-- Upload Modal -->
    <div v-if="showUpload" class="modal-mask" @click.self="showUpload = false">
      <div class="small-modal">
        <h3>上传模块</h3>
        <p class="modal-desc">支持 .zip 压缩包</p>
        <input type="file" accept=".zip" @change="handleUpload" />
        <div class="modal-footer">
          <button class="p-btn" @click="showUpload = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const modules = ref([])
const loading = ref(false)
const showUpload = ref(false)

async function loadModules() {
  loading.value = true
  const res = await store.fetchApi('/modules/scan')
  if (res && res.success) {
    modules.value = res.modules || []
  }
  loading.value = false
}

async function toggleModule(mod) {
  const res = await store.postApi('/modules/toggle', { name: mod.name, enabled: !mod.enabled })
  if (res && res.success) {
    mod.enabled = !mod.enabled
  }
}

async function handleUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  const form = new FormData()
  form.append('file', file)
  const token = localStorage.getItem('elaina_token')
  const res = await fetch('/api/modules/upload', { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form })
  const data = await res.json()
  if (data.success) { showUpload.value = false; loadModules() }
}

onMounted(() => { loadModules() })
</script>

<style scoped>
.modules-page { display: flex; flex-direction: column; }
.modules-toolbar {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;
}
.modules-toolbar h2 { color: var(--text); font-size: 18px; font-weight: 700; margin: 0; }
.modules-actions { display: flex; gap: 8px; }
.p-btn {
  display: flex; align-items: center; gap: 4px; padding: 6px 12px;
  border: 1px solid var(--border); border-radius: 6px; background: transparent;
  color: var(--text2); cursor: pointer; font-size: 12px;
}
.p-btn:hover { color: var(--text); border-color: var(--text3); }
.upload-btn { background: var(--accent); color: #fff; border-color: var(--accent); }
.upload-btn:hover { opacity: 0.9; }

.modules-list { display: flex; flex-direction: column; gap: 8px; }
.mod-empty { text-align: center; color: var(--text3); padding: 40px 0; font-size: 13px; }

.mod-card {
  background: var(--bg2); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px;
}
.mod-header { display: flex; align-items: center; justify-content: space-between; }
.mod-info { display: flex; flex-direction: column; }
.mod-name { color: var(--text); font-weight: 600; font-size: 14px; }
.mod-desc { color: var(--text2); font-size: 12px; margin-top: 2px; }
.mod-meta { display: flex; gap: 12px; margin-top: 8px; font-size: 11px; color: var(--text3); }
.mod-error { color: var(--danger); font-size: 12px; margin-top: 6px; }

/* Toggle Switch */
.toggle-switch { position: relative; display: inline-block; width: 36px; height: 20px; }
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
  position: absolute; cursor: pointer; inset: 0;
  background: var(--border); border-radius: 20px; transition: 0.2s;
}
.toggle-slider:before {
  content: ''; position: absolute; height: 16px; width: 16px;
  left: 2px; bottom: 2px; background: white; border-radius: 50%; transition: 0.2s;
}
.toggle-switch input:checked + .toggle-slider { background: var(--accent); }
.toggle-switch input:checked + .toggle-slider:before { transform: translateX(16px); }

/* Modal */
.modal-mask {
  position: fixed; inset: 0; background: rgba(0,0,0,0.3);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
}
.small-modal {
  width: 380px; background: var(--bg); border-radius: 10px; padding: 20px;
  border: 1px solid var(--border);
}
.small-modal h3 { font-size: 16px; margin-bottom: 8px; color: var(--text); }
.modal-desc { font-size: 12px; color: var(--text2); margin-bottom: 12px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
</style>
