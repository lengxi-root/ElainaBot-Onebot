<template>
  <div class="msg-page">
    <h2 class="msg-title">消息管理</h2>
    <div class="msg-layout">
      <!-- Chat list panel -->
      <div class="chat-list-panel">
        <div class="panel-header">
          <span>会话列表</span>
        </div>
        <input class="chat-search" type="text" v-model="searchText" placeholder="搜索..." />
        <div class="chat-tabs">
          <button class="chat-tab" :class="{ active: chatFilter === 'all' }" @click="chatFilter = 'all'">全部</button>
          <button class="chat-tab" :class="{ active: chatFilter === 'group' }" @click="chatFilter = 'group'">群聊</button>
          <button class="chat-tab" :class="{ active: chatFilter === 'private' }" @click="chatFilter = 'private'">私聊</button>
        </div>
        <div class="chat-items">
          <div
            v-for="chat in filteredChats"
            :key="chat.id"
            class="chat-item"
            :class="{ active: selectedChat?.id === chat.id }"
            @click="selectChat(chat)"
          >
            <div class="chat-avatar-wrap">
              <div class="chat-avatar-fallback">{{ (chat.name || chat.id)[0] }}</div>
              <span class="chat-avatar-badge" :class="chat.type === 'group' ? 'group' : 'private'">
                {{ chat.type === 'group' ? '群' : '私' }}
              </span>
            </div>
            <div class="chat-info">
              <div class="chat-name">{{ chat.name || chat.id }}</div>
              <div class="chat-sub">{{ chat.count || 0 }} 条消息</div>
            </div>
          </div>
          <div v-if="!filteredChats.length" class="chat-empty">暂无会话</div>
        </div>
      </div>

      <!-- Message area -->
      <div class="msg-area">
        <template v-if="selectedChat">
          <div class="msg-area-header">
            <span class="msg-area-title">{{ selectedChat.name || selectedChat.id }}</span>
            <span class="msg-area-sub">{{ selectedChat.type === 'group' ? '群聊' : '私聊' }} · {{ selectedChat.id }}</span>
          </div>
          <div class="msg-list" ref="msgListRef">
            <div v-if="hasMore" class="load-more" @click="loadMore">加载更多</div>
            <div v-for="msg in messages" :key="msg.id || msg.time" class="msg-bubble">
              <div class="msg-meta">
                <span class="msg-sender">{{ msg.user_id }}</span>
                <span class="msg-time">{{ msg.time }}</span>
              </div>
              <div class="msg-content">{{ msg.content }}</div>
            </div>
            <div v-if="!messages.length" class="msg-empty">暂无消息记录</div>
          </div>
        </template>
        <div v-else class="msg-placeholder">
          <p>选择左侧会话查看消息</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '../stores/app'

const store = useAppStore()
const chats = ref([])
const messages = ref([])
const selectedChat = ref(null)
const searchText = ref('')
const chatFilter = ref('all')
const page = ref(1)
const hasMore = ref(false)

const filteredChats = computed(() => {
  let list = chats.value
  if (chatFilter.value !== 'all') {
    list = list.filter(c => c.type === chatFilter.value)
  }
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(c => (c.name || c.id).toLowerCase().includes(q))
  }
  return list
})

async function loadChats() {
  const res = await store.fetchApi('/messages/chats')
  if (res && res.success) {
    chats.value = (res.chats || []).map(c => ({
      id: c.chat_id || '',
      type: c.type || 'private',
      name: c.nickname || c.chat_id || '',
      count: c.msg_count || 0,
      last_time: c.last_time || '',
    }))
  }
}

async function selectChat(chat) {
  selectedChat.value = chat
  page.value = 1
  messages.value = []
  await loadHistory()
}

async function loadHistory() {
  const chat = selectedChat.value
  if (!chat) return
  const res = await store.postApi('/messages/history', {
    chat_id: chat.id,
    type: chat.type,
    page: page.value,
    limit: 50,
  })
  if (res && res.success) {
    if (page.value === 1) {
      messages.value = res.messages || []
    } else {
      messages.value = [...(res.messages || []), ...messages.value]
    }
    hasMore.value = (res.messages || []).length >= 50
  }
}

async function loadMore() {
  page.value++
  await loadHistory()
}

onMounted(() => {
  loadChats()
})
</script>

<style scoped>
.msg-page { height: calc(100vh - 100px); display: flex; flex-direction: column; }
.msg-title { color: var(--text); font-size: 18px; font-weight: 700; margin: 0 0 12px; }
.msg-layout { flex: 1; display: flex; gap: 12px; min-height: 0; }

.chat-list-panel {
  width: 240px;
  flex-shrink: 0;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.panel-header {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  color: var(--text);
  font-size: 14px;
  font-weight: 600;
}
.chat-search {
  margin: 8px 10px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  outline: none;
  background: var(--bg);
  color: var(--text);
}
.chat-search:focus { border-color: var(--accent); }

.chat-tabs { display: flex; border-bottom: 1px solid var(--border); }
.chat-tab {
  flex: 1;
  padding: 6px 0;
  text-align: center;
  border: none;
  background: none;
  color: var(--text2);
  font-size: 12px;
  cursor: pointer;
  transition: color 0.15s;
}
.chat-tab:hover { color: var(--text); }
.chat-tab.active { color: var(--accent); border-bottom: 2px solid var(--accent); }

.chat-items { flex: 1; overflow-y: auto; }
.chat-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.12s;
}
.chat-item:hover { background: var(--border); }
.chat-item.active { background: var(--bg-float); }

.chat-avatar-wrap { position: relative; flex-shrink: 0; width: 36px; height: 36px; }
.chat-avatar-fallback {
  width: 36px; height: 36px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, var(--accent), var(--accent-light));
  color: #fff; font-weight: 700; font-size: 14px;
}
.chat-avatar-badge {
  position: absolute; bottom: -2px; right: -2px;
  font-size: 9px; padding: 1px 3px; border-radius: 3px;
  color: #fff; font-weight: 600;
}
.chat-avatar-badge.group { background: var(--success); }
.chat-avatar-badge.private { background: var(--accent); }

.chat-info { flex: 1; min-width: 0; }
.chat-name { font-size: 13px; font-weight: 500; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.chat-sub { font-size: 11px; color: var(--text3); }
.chat-empty { color: var(--text3); text-align: center; padding: 20px 0; font-size: 13px; }

.msg-area {
  flex: 1;
  background: var(--bg2);
  border: 1px solid var(--border);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}
.msg-area-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.msg-area-title { color: var(--text); font-weight: 600; font-size: 14px; }
.msg-area-sub { color: var(--text3); font-size: 12px; margin-left: 8px; }

.msg-list { flex: 1; overflow-y: auto; padding: 12px 16px; }
.load-more {
  text-align: center; color: var(--accent); font-size: 12px;
  cursor: pointer; padding: 8px 0; margin-bottom: 8px;
}
.load-more:hover { text-decoration: underline; }

.msg-bubble { margin-bottom: 12px; }
.msg-meta { margin-bottom: 2px; }
.msg-sender { color: var(--accent); font-size: 12px; font-weight: 500; margin-right: 8px; }
.msg-time { color: var(--text3); font-size: 11px; }
.msg-content {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text);
  line-height: 1.5;
  word-break: break-all;
}
.msg-empty { color: var(--text3); text-align: center; padding: 40px 0; font-size: 13px; }
.msg-placeholder {
  flex: 1; display: flex; align-items: center; justify-content: center;
  color: var(--text3); font-size: 14px;
}
</style>
