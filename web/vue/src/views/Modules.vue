<template>
  <div class="modules-page">
    <header class="page-header">
      <h1>模块管理</h1>
      <p class="subtitle">可选拓展模块</p>
    </header>

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

async function loadModules() {
  const res = await store.fetchApi('/modules/list')
  if (res && res.success) {
    modules.value = res.data || []
  }
}

async function toggleModule(name, enabled) {
  await store.postApi('/modules/toggle', { name, enabled })
  await loadModules()
}

onMounted(loadModules)
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

.modules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.module-card {
  padding: 20px;
}

.module-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.module-header h3 {
  font-size: 15px;
  font-weight: 600;
}

.module-desc {
  font-size: 13px;
  color: var(--color-text-muted);
  margin-top: 2px;
}

.module-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--color-text-muted);
}

.module-error {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-danger);
  background: #fee2e2;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
}

/* Toggle Switch */
.toggle {
  position: relative;
  width: 40px;
  height: 22px;
  flex-shrink: 0;
}

.toggle input {
  opacity: 0;
  width: 0;
  height: 0;
}

.toggle-slider {
  position: absolute;
  inset: 0;
  background: var(--color-border);
  border-radius: 11px;
  cursor: pointer;
  transition: background var(--transition);
}

.toggle-slider::before {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: white;
  top: 3px;
  left: 3px;
  transition: transform var(--transition);
}

.toggle input:checked + .toggle-slider {
  background: var(--color-primary);
}

.toggle input:checked + .toggle-slider::before {
  transform: translateX(18px);
}

.empty-text {
  color: var(--color-text-muted);
  font-size: 14px;
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px;
}

.empty-text code {
  background: var(--color-bg-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 13px;
}
</style>
