<template>
  <div class="config-page">
    <header class="page-header">
      <h1>配置管理</h1>
      <p class="subtitle">编辑框架设置 (settings.yaml)</p>
    </header>

    <div class="card config-container">
      <div class="config-toolbar">
        <button @click="loadConfig" class="btn btn-secondary">刷新</button>
        <button @click="saveConfig" class="btn btn-primary" :disabled="!changed">保存</button>
      </div>

      <div class="config-editor">
        <textarea
          v-model="configText"
          @input="changed = true"
          class="config-textarea"
          spellcheck="false"
        ></textarea>
      </div>

      <p v-if="message" class="config-message" :class="{ 'msg-error': isError }">{{ message }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const configText = ref('')
const configData = ref({})
const changed = ref(false)
const message = ref('')
const isError = ref(false)

async function loadConfig() {
  const res = await store.fetchApi('/config')
  if (res && res.success) {
    configData.value = res.data || {}
    configText.value = JSON.stringify(res.data, null, 2)
    changed.value = false
    message.value = ''
  }
}

async function saveConfig() {
  try {
    const data = JSON.parse(configText.value)
    const res = await store.postApi('/config/save', { data })
    if (res && res.success) {
      message.value = '保存成功'
      isError.value = false
      changed.value = false
    } else {
      message.value = res?.error || '保存失败'
      isError.value = true
    }
  } catch (e) {
    message.value = 'JSON 格式错误'
    isError.value = true
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 24px;
  font-weight: 700;
}

.subtitle {
  color: var(--color-text-muted);
  font-size: 14px;
  margin-top: 4px;
}

.config-container {
  padding: 0;
  overflow: hidden;
}

.config-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border-light);
}

.config-editor {
  padding: 0;
}

.config-textarea {
  width: 100%;
  min-height: 500px;
  padding: 20px;
  border: none;
  outline: none;
  resize: vertical;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  background: var(--color-bg);
  color: var(--color-text);
}

.config-message {
  padding: 12px 20px;
  font-size: 13px;
  color: var(--color-success);
  border-top: 1px solid var(--color-border-light);
}

.msg-error {
  color: var(--color-danger);
}
</style>
