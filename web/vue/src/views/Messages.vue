<template>
  <div class="messages-page">
    <header class="page-header">
      <h1>消息浏览</h1>
      <p class="subtitle">查看聊天记录</p>
    </header>

    <div class="msg-layout">
      <!-- Chat List -->
      <div class="card chat-list-panel">
        <div class="panel-header">
          <input v-model="search" placeholder="搜索..." class="search-input" @input="loadChats" />
          <div class="type-tabs">
            <button :class="{ active: chatType === '' }" @click="chatType = ''; loadChats()">全部</button>
            <button :class="{ active: chatType === 'group' }" @click="chatType = 'group'; loadChats()">群聊</button>
            <button :class="{ active: chatType === 'private' }" @click="chatType = 'private'; loadChats()">私聊</button>
          </div>
        </div>
        <div class="chat-items">
          <div
            v-for="chat in chats" :key="chat.chat_id + chat.type"
            class="chat-item"
            :class="{ active: selectedChat?.chat_id === chat.chat_id }"
            @click="selectChat(chat)"
          >
            <div class="chat-avatar">{{ chat.type === 'group' ? '群' : '私' }}</div>
            <div class="chat-info">
              <span class="chat-name">{{ chat.nickname || chat.chat_id }}</span>
              <span class="chat-meta">{{ chat.msg_count }} 条消息</span>
            </div>
            <span class="chat-time">{{ formatTime(chat.last_time) }}</span>
          </div>
          <p v-if="!chats.length" class="empty-text">暂无聊天记录</p>
        </div>
      </div>

      <!-- Chat History -->
      <div class="card chat-history-panel">
        <template v-if="selectedChat">
          <div class="panel-header">
            <h3>{{ selectedChat.nickname || selectedChat.chat_id }}</h3>
            <span class="badge" :class="selectedChat.type === 'group' ? 'badge-success' : 'badge-warning'">
              {{ selectedChat.type === 'group' ? '群聊' : '私聊' }}
            </span>
          </div>
          <div class="history-body" ref="historyRef">
            <div v-if="historyPage > 1" class="load-more">
              <button class="btn btn-secondary" @click="loadMore">加载更多</button>
            </div>
            <div v-for="msg in history" :key="msg.id || msg.message_id" class="history-msg">
              <div class="msg-bubble">
                <div class="msg-header">
                  <span class="msg-user">{{ msg.user_id }}</span>
                  <span class="msg-ts">{{ msg.timestamp }}</span>
                </div>
                <div class="msg-text">{{ msg.content }}</div>
              </div>
            </div>
            <p v-if="!history.length" class="empty-text">暂无消息</p>
          </div>
          <div class="history-footer">
            <span class="page-info">共 {{ historyTotal }} 条</span>
          </div>
        </template>
        <div v-else class="empty-panel">
          <p>选择一个聊天查看消息记录</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const chats = ref([])
const search = ref('')
const chatType = ref('')
const selectedChat = ref(null)
const history = ref([])
const historyPage = ref(1)
const historyTotal = ref(0)

async function loadChats() {
  const params = new URLSearchParams()
  if (search.value) params.set('search', search.value)
  if (chatType.value) params.set('type', chatType.value)
  const res = await store.fetchApi(`/messages/chats?${params}`)
  if (res && res.success) {
    chats.value = res.chats || []
  }
}

async function selectChat(chat) {
  selectedChat.value = chat
  historyPage.value = 1
  history.value = []
  await loadHistory()
}

async function loadHistory() {
  if (!selectedChat.value) return
  const res = await store.postApi('/messages/history', {
    chat_id: selectedChat.value.chat_id,
    type: selectedChat.value.type,
    page: historyPage.value,
    limit: 50,
  })
  if (res && res.success) {
    const msgs = (res.messages || []).reverse()
    if (historyPage.value === 1) {
      history.value = msgs
    } else {
      history.value = [...msgs, ...history.value]
    }
    historyTotal.value = res.total || 0
  }
}

function loadMore() {
  historyPage.value++
  loadHistory()
}

function formatTime(ts) {
  if (!ts) return ''
  return ts.slice(5, 16)
}

onMounted(loadChats)
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 22px; font-weight: 700; }
.subtitle { color: var(--color-text-muted); font-size: 13px; margin-top: 2px; }

.msg-layout { display: grid; grid-template-columns: 300px 1fr; gap: 16px; height: calc(100vh - 140px); }

.chat-list-panel { display: flex; flex-direction: column; overflow: hidden; }
.chat-history-panel { display: flex; flex-direction: column; overflow: hidden; }

.panel-header {
  padding: 12px 16px; border-bottom: 1px solid var(--color-border-light);
  display: flex; align-items: center; gap: 8px; flex-shrink: 0;
}

.panel-header h3 { font-size: 14px; font-weight: 600; }

.search-input {
  flex: 1; padding: 6px 10px; border: 1px solid var(--color-border); border-radius: var(--radius-sm);
  background: var(--color-bg-secondary); font-size: 13px; outline: none; font-family: inherit;
}
.search-input:focus { border-color: var(--color-primary); }

.type-tabs { display: flex; gap: 2px; }
.type-tabs button {
  padding: 4px 8px; border: none; background: none; font-size: 12px;
  color: var(--color-text-muted); border-radius: 4px; font-family: inherit;
}
.type-tabs button.active { background: var(--color-primary-light); color: var(--color-primary); font-weight: 500; }

.chat-items { flex: 1; overflow-y: auto; }

.chat-item {
  display: flex; align-items: center; gap: 10px; padding: 10px 16px;
  cursor: pointer; transition: background var(--transition); border-bottom: 1px solid var(--color-border-light);
}
.chat-item:hover { background: var(--color-bg-secondary); }
.chat-item.active { background: var(--color-primary-light); }

.chat-avatar {
  width: 32px; height: 32px; border-radius: 50%; background: var(--color-bg-tertiary);
  display: flex; align-items: center; justify-content: center; font-size: 12px;
  color: var(--color-text-muted); flex-shrink: 0; font-weight: 500;
}
.chat-info { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.chat-name { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chat-meta { font-size: 11px; color: var(--color-text-muted); }
.chat-time { font-size: 11px; color: var(--color-text-muted); flex-shrink: 0; }

.history-body { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 8px; }

.load-more { text-align: center; padding: 8px; }
.load-more .btn { font-size: 12px; padding: 4px 12px; }

.history-msg { display: flex; }
.msg-bubble {
  max-width: 80%; background: var(--color-bg-secondary); border-radius: 8px; padding: 8px 12px;
}
.msg-header { display: flex; gap: 8px; align-items: baseline; margin-bottom: 4px; }
.msg-user { font-size: 12px; font-weight: 600; color: var(--color-primary); }
.msg-ts { font-size: 11px; color: var(--color-text-muted); }
.msg-text { font-size: 13px; line-height: 1.5; word-break: break-all; }

.history-footer {
  padding: 8px 16px; border-top: 1px solid var(--color-border-light); flex-shrink: 0;
}
.page-info { font-size: 12px; color: var(--color-text-muted); }

.empty-panel {
  flex: 1; display: flex; align-items: center; justify-content: center;
  color: var(--color-text-muted); font-size: 14px;
}
.empty-text { color: var(--color-text-muted); font-size: 13px; text-align: center; padding: 20px; }

@media (max-width: 768px) {
  .msg-layout { grid-template-columns: 1fr; height: auto; }
  .chat-list-panel { max-height: 300px; }
}
</style>
