<template>
  <div class="config-page">
    <header class="page-header">
      <h1>配置管理</h1>
      <p class="subtitle">编辑框架配置文件 (YAML)</p>
    </header>

    <div class="card config-container">
      <div class="config-toolbar">
        <div class="toolbar-left">
          <div class="file-tabs">
            <button
              v-for="tab in configTabs"
              :key="tab.key"
              :class="{ active: currentTab === tab.key }"
              @click="switchTab(tab.key)"
            >{{ tab.label }}</button>
          </div>
        </div>
        <div class="toolbar-right">
          <button @click="loadConfig" class="btn btn-secondary btn-sm">刷新</button>
          <button @click="saveConfig" class="btn btn-primary btn-sm" :disabled="!changed">保存</button>
        </div>
      </div>

      <div class="config-editor">
        <div class="line-numbers">
          <span v-for="n in lineCount" :key="n">{{ n }}</span>
        </div>
        <textarea
          ref="editorRef"
          v-model="configText"
          @input="onInput"
          @keydown="handleTab"
          class="config-textarea"
          spellcheck="false"
        ></textarea>
      </div>

      <div v-if="message" class="config-status" :class="{ error: isError }">
        {{ message }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const editorRef = ref(null)
const configText = ref('')
const changed = ref(false)
const message = ref('')
const isError = ref(false)
const currentTab = ref('settings')
const configData = ref({})

const configTabs = [
  { key: 'settings', label: 'settings.yaml' },
]

const lineCount = computed(() => {
  return (configText.value.match(/\n/g) || []).length + 1
})

async function loadConfig() {
  const res = await store.fetchApi('/config')
  if (res && res.success) {
    configData.value = {}
    for (const key of Object.keys(res)) {
      if (key !== 'success') {
        configData.value[key] = res[key]
      }
    }
    configText.value = configData.value[currentTab.value] || ''
    changed.value = false
    message.value = ''
  }
}

function switchTab(tab) {
  if (changed.value) {
    if (!confirm('未保存的修改将丢失，是否继续？')) return
  }
  currentTab.value = tab
  configText.value = configData.value[tab] || ''
  changed.value = false
  message.value = ''
}

function onInput() {
  changed.value = true
  message.value = ''
}

function handleTab(e) {
  if (e.key === 'Tab') {
    e.preventDefault()
    const ta = editorRef.value
    const start = ta.selectionStart
    const end = ta.selectionEnd
    const val = ta.value
    ta.value = val.substring(0, start) + '  ' + val.substring(end)
    ta.selectionStart = ta.selectionEnd = start + 2
    configText.value = ta.value
    changed.value = true
  }
}

async function saveConfig() {
  const res = await store.postApi('/config/save', {
    file: currentTab.value,
    content: configText.value,
  })
  if (res && res.success) {
    message.value = '保存成功'
    isError.value = false
    changed.value = false
    configData.value[currentTab.value] = configText.value
  } else {
    message.value = res?.error || '保存失败'
    isError.value = true
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 22px; font-weight: 700; }
.subtitle { color: var(--color-text-muted); font-size: 13px; margin-top: 2px; }

.config-container { padding: 0; overflow: hidden; }

.config-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px; border-bottom: 1px solid var(--color-border-light); gap: 8px;
}
.toolbar-left { display: flex; align-items: center; gap: 8px; }
.toolbar-right { display: flex; gap: 8px; }

.file-tabs { display: flex; gap: 2px; }
.file-tabs button {
  padding: 6px 12px; border: none; background: none; font-size: 13px;
  color: var(--color-text-muted); border-radius: 4px; font-family: var(--font-mono);
  cursor: pointer; transition: all var(--transition);
}
.file-tabs button.active {
  background: var(--color-primary-light); color: var(--color-primary); font-weight: 500;
}
.file-tabs button:hover:not(.active) { background: var(--color-bg-tertiary); }

.btn-sm { font-size: 12px; padding: 5px 12px; }

.config-editor { display: flex; position: relative; }

.line-numbers {
  padding: 16px 8px 16px 12px; background: var(--color-bg-secondary);
  border-right: 1px solid var(--color-border-light); user-select: none;
  display: flex; flex-direction: column; min-width: 40px; text-align: right;
}
.line-numbers span {
  font-family: var(--font-mono); font-size: 12px; line-height: 1.6;
  color: var(--color-text-muted); height: 19.2px;
}

.config-textarea {
  flex: 1; min-height: 500px; padding: 16px; border: none; outline: none;
  resize: vertical; font-family: var(--font-mono); font-size: 12px;
  line-height: 1.6; background: var(--color-bg); color: var(--color-text);
  tab-size: 2;
}

.config-status {
  padding: 8px 16px; font-size: 12px; color: var(--color-success);
  border-top: 1px solid var(--color-border-light);
}
.config-status.error { color: var(--color-danger); }
</style>
