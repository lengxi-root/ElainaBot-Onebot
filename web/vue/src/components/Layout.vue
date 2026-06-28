<template>
  <div class="layout-root">
    <aside class="sidebar" :class="{ collapsed: store.sidebarCollapsed }">
      <div class="sidebar-logo">
        <img class="logo-icon" :src="logoUrl" alt="Elaina" />
        <span v-if="!store.sidebarCollapsed" class="logo-text">Elaina</span>
      </div>
      <div v-if="!store.sidebarCollapsed" class="sidebar-bot-select">
        <select class="bot-select-input" v-model="store.currentBotId" @change="store.switchBot(store.currentBotId)">
          <option value="">全部机器人</option>
          <option v-for="bot in store.bots" :key="bot.self_id" :value="bot.self_id">
            {{ bot.nickname || bot.self_id }}
          </option>
        </select>
      </div>
      <nav class="sidebar-nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
        >
          <SvgIcon :name="item.icon" :size="18" />
          <span v-if="!store.sidebarCollapsed">{{ item.label }}</span>
        </router-link>
      </nav>
      <div class="sidebar-toggle" @click="store.sidebarCollapsed = !store.sidebarCollapsed">
        <SvgIcon :name="store.sidebarCollapsed ? 'expand' : 'collapse'" :size="16" />
      </div>
    </aside>

    <div class="main-area">
      <header class="topbar">
        <div class="topbar-left">
          <div class="ws-status">
            <span class="ws-dot" :class="store.connected ? 'online' : 'offline'"></span>
            <span class="ws-label">{{ store.connected ? '已连接' : '未连接' }}</span>
          </div>
        </div>
        <div class="topbar-right">
          <button class="tool-btn" @click="handleLogout" title="退出登录">
            <SvgIcon name="logout" :size="16" />
          </button>
        </div>
      </header>
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import SvgIcon from './SvgIcon.vue'

const route = useRoute()
const router = useRouter()
const store = useAppStore()
const logoUrl = import.meta.env.BASE_URL + 'favicon.svg'

const navItems = [
  { path: '/web/', icon: 'home', label: '仪表盘' },
  { path: '/web/messages', icon: 'chatbubbles', label: '消息' },
  { path: '/web/statistics', icon: 'stats-chart', label: '统计' },
  { path: '/web/plugins', icon: 'extension-puzzle', label: '插件' },
  { path: '/web/modules', icon: 'server', label: '模块' },
  { path: '/web/config', icon: 'cog', label: '配置' },
  { path: '/web/logs', icon: 'terminal', label: '日志' },
  { path: '/web/database', icon: 'database', label: '数据库' },
]

function isActive(path) {
  if (path === '/web/') return route.path === '/web/' || route.path === '/web'
  return route.path.startsWith(path)
}

function handleLogout() {
  localStorage.removeItem('elaina_token')
  router.push('/web/login')
}

// Init
store.loadSystemInfo()
store.fetchBots()
store.connectWs()
</script>

<style scoped>
.layout-root {
  display: flex;
  height: 100vh;
  overflow: hidden;
  background: var(--bg);
}

.sidebar {
  width: 220px;
  flex-shrink: 0;
  background: var(--bg2);
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  transition: width 0.2s;
  z-index: 100;
}
.sidebar.collapsed { width: 64px; }
.sidebar.collapsed .logo-text,
.sidebar.collapsed .sidebar-bot-select,
.sidebar.collapsed .nav-item span { display: none; }
.sidebar.collapsed .nav-item { justify-content: center; padding: 12px 0; }

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  border-bottom: 1px solid var(--border);
}
.logo-icon { width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0; object-fit: contain; }
.logo-text { color: var(--text); font-weight: 600; font-size: 16px; white-space: nowrap; }

.sidebar-bot-select { padding: 8px 12px; }
.bot-select-input {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  background: var(--bg);
  color: var(--text);
  outline: none;
  cursor: pointer;
}
.bot-select-input:focus { border-color: var(--accent); }

.sidebar-nav { flex: 1; overflow-y: auto; padding: 8px 0; }
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  margin: 2px 8px;
  border-radius: 8px;
  color: var(--text2);
  cursor: pointer;
  transition: all 0.15s;
  text-decoration: none;
  font-size: 14px;
}
.nav-item:hover { background: var(--border); color: var(--text); }
.nav-item.active { background: var(--accent); color: #fff; }

.sidebar-toggle {
  padding: 12px;
  text-align: center;
  border-top: 1px solid var(--border);
  cursor: pointer;
  color: var(--text3);
}
.sidebar-toggle:hover { color: var(--text); }

.main-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
  flex-shrink: 0;
}
.topbar-left, .topbar-right { display: flex; align-items: center; gap: 12px; }

.ws-status { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text2); }
.ws-dot { width: 8px; height: 8px; border-radius: 50%; }
.ws-dot.online { background: var(--success); box-shadow: 0 0 6px var(--success); }
.ws-dot.offline { background: var(--danger); }
.ws-label { font-size: 12px; }

.tool-btn {
  display: flex;
  align-items: center;
  padding: 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text2);
  cursor: pointer;
  transition: all 0.15s;
}
.tool-btn:hover { color: var(--text); border-color: var(--text3); }

.content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
</style>
