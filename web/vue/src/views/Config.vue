<template>
  <div class="config-page">
    <div class="config-header">
      <div class="config-actions">
        <button class="cfg-btn" @click="loadConfig" :disabled="loading">刷新</button>
        <button class="cfg-btn save" @click="saveConfig" :disabled="!changed || saving">保存</button>
      </div>
    </div>

    <div class="config-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="config-tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key; loadConfig()"
      >{{ tab.label }}</button>
    </div>

    <div class="config-body">
      <div class="editor-wrap">
        <div class="editor-hint">
          <span>{{ activeTab }}.yaml</span>
          <span class="editor-hint-r" v-if="statusMsg">{{ statusMsg }}</span>
        </div>
        <textarea
          class="yaml-editor"
          v-model="content"
          spellcheck="false"
          @input="changed = true"
          @keydown.tab.prevent="insertTab"
        ></textarea>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const tabs = [{ key: 'settings', label: 'settings.yaml' }]
const activeTab = ref('settings')
const content = ref('')
const originalContent = ref('')
const changed = ref(false)
const loading = ref(false)
const saving = ref(false)
const statusMsg = ref('')

async function loadConfig() {
  loading.value = true
  statusMsg.value = ''
  const res = await store.fetchApi('/config')
  if (res && res.success) {
    content.value = res[activeTab.value] || ''
    originalContent.value = content.value
    changed.value = false
  }
  loading.value = false
}

async function saveConfig() {
  saving.value = true
  statusMsg.value = ''
  const res = await store.postApi('/config/save', { file: activeTab.value, content: content.value })
  if (res && res.success) {
    statusMsg.value = '保存成功'
    originalContent.value = content.value
    changed.value = false
  } else {
    statusMsg.value = res?.error || '保存失败'
  }
  saving.value = false
  setTimeout(() => { statusMsg.value = '' }, 3000)
}

function insertTab(e) {
  const ta = e.target
  const start = ta.selectionStart
  const end = ta.selectionEnd
  content.value = content.value.substring(0, start) + '  ' + content.value.substring(end)
  setTimeout(() => { ta.selectionStart = ta.selectionEnd = start + 2 }, 0)
  changed.value = true
}

onMounted(() => { loadConfig() })
</script>

<style scoped>
.config-page { display: flex; flex-direction: column; height: calc(100vh - 100px); }
.config-header {
  display: flex; align-items: center; justify-content: flex-end; margin-bottom: 12px;
}
.config-actions { display: flex; gap: 6px; }
.cfg-btn {
  padding: 5px 14px; border: 1px solid var(--border); border-radius: 6px;
  background: transparent; color: var(--text2); cursor: pointer; font-size: 13px;
}
.cfg-btn:hover { color: var(--text); border-color: var(--text3); }
.cfg-btn:disabled { opacity: 0.4; cursor: default; }
.cfg-btn.save { background: var(--accent); color: #fff; border-color: var(--accent); }
.cfg-btn.save:hover { background: var(--accent-hover); }

.config-tabs { display: flex; align-items: center; gap: 6px; margin-bottom: 12px; }
.config-tab {
  padding: 6px 16px; border: 1px solid var(--border); border-radius: 6px;
  background: transparent; color: var(--text2); cursor: pointer; font-size: 13px;
}
.config-tab:hover { color: var(--text); }
.config-tab.active { background: var(--accent); color: #fff; border-color: var(--accent); }

.config-body { flex: 1; display: flex; gap: 12px; min-height: 0; }
.editor-wrap { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.editor-hint {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; background: var(--bg3); border: 1px solid var(--border);
  border-bottom: none; border-radius: 8px 8px 0 0; color: var(--text2); font-size: 12px;
}
.editor-hint-r { color: var(--warning); }
.yaml-editor {
  flex: 1; resize: none; padding: 12px; background: var(--bg2); color: var(--text);
  border: 1px solid var(--border); border-radius: 0 0 8px 8px;
  font-family: var(--font-mono); font-size: 13px; line-height: 1.6;
  tab-size: 2; outline: none;
}
</style>
