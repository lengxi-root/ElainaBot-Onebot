<template>
  <div class="messages-page">
    <header class="page-header">
      <h1>消息记录</h1>
      <p class="subtitle">实时消息监控</p>
    </header>

    <div class="card messages-container">
      <div class="messages-toolbar">
        <select v-model="filter" class="filter-select">
          <option value="all">全部</option>
          <option value="group">群聊</option>
          <option value="private">私聊</option>
        </select>
        <button @click="loadMessages" class="btn btn-secondary">刷新</button>
      </div>

      <div class="messages-list" ref="listRef">
        <div
          v-for="msg in filteredMessages"
          :key="msg.id || msg.message_id"
          class="message-item"
        >
          <div class="msg-meta">
            <span class="msg-time">{{ msg.timestamp }}</span>
            <span class="badge" :class="msg.message_type === 'group' ? 'badge-success' : 'badge-warning'">
              {{ msg.message_type === 'group' ? '群聊' : '私聊' }}
            </span>
            <span class="msg-id" v-if="msg.group_id">群 {{ msg.group_id }}</span>
            <span class="msg-sender">{{ msg.user_id }}</span>
          </div>
          <div class="msg-content">{{ msg.content }}</div>
        </div>
        <p v-if="!filteredMessages.length" class="empty-text">暂无消息</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const messages = ref([])
const filter = ref('all')

const filteredMessages = computed(() => {
  if (filter.value === 'all') return messages.value
  return messages.value.filter((m) => m.message_type === filter.value)
})

async function loadMessages() {
  const res = await store.fetchApi('/messages/recent')
  if (res && res.success) {
    messages.value = res.data || []
  }
}

function onWsMessage(e) {
  const msg = e.detail
  if (msg.type === 'message') {
    messages.value.unshift(msg.data)
    if (messages.value.length > 200) messages.value.pop()
  }
}

onMounted(() => {
  loadMessages()
  window.addEventListener('ws-message', onWsMessage)
})

onUnmounted(() => {
  window.removeEventListener('ws-message', onWsMessage)
})
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

.messages-container {
  padding: 0;
  overflow: hidden;
}

.messages-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border-light);
}

.filter-select {
  padding: 6px 12px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  outline: none;
  background: var(--color-bg);
}

.messages-list {
  max-height: 600px;
  overflow-y: auto;
  padding: 12px 20px;
}

.message-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border-light);
}

.message-item:last-child {
  border-bottom: none;
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.msg-time {
  font-size: 12px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
}

.msg-id,
.msg-sender {
  font-size: 12px;
  color: var(--color-text-secondary);
}

.msg-content {
  font-size: 14px;
  color: var(--color-text);
  word-break: break-all;
}

.empty-text {
  color: var(--color-text-muted);
  font-size: 13px;
  text-align: center;
  padding: 40px;
}
</style>
