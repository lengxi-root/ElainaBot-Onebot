import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const API_BASE = '/api'

function getHeaders() {
  const token = localStorage.getItem('elaina_token')
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

export const useAppStore = defineStore('app', () => {
  const systemInfo = ref(null)
  const connected = ref(false)
  const bots = ref([])
  const currentBotId = ref('')
  const sidebarCollapsed = ref(false)

  // WS/SSE state
  let wsInstance = null
  let sseInstance = null
  let wsFailCount = 0
  const WS_MAX_FAIL = 3
  const RECONNECT_DELAY = 3000

  const currentBot = computed(() =>
    currentBotId.value ? bots.value.find(b => b.appid === currentBotId.value || b.self_id === currentBotId.value) : null
  )
  const isAllBots = computed(() => !currentBotId.value)

  async function fetchApi(path, options = {}) {
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        headers: getHeaders(),
        ...options,
      })
      if (res.status === 401 && !path.startsWith('/auth/')) {
        localStorage.removeItem('elaina_token')
        window.location.href = '/web/login'
        return null
      }
      return res.json()
    } catch (e) {
      return null
    }
  }

  async function postApi(path, data) {
    return fetchApi(path, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  }

  async function loadSystemInfo() {
    const res = await fetchApi('/system/info')
    if (res && res.success) {
      systemInfo.value = res.data
    }
  }

  async function fetchBots() {
    const res = await fetchApi('/bots')
    if (res && res.success) {
      bots.value = res.bots || []
      if (bots.value.length === 1 && !currentBotId.value) {
        switchBot(bots.value[0].appid || bots.value[0].self_id)
      }
    }
  }

  function switchBot(id) {
    currentBotId.value = id
    localStorage.setItem('elaina_bot', id)
  }

  // ============ WebSocket + SSE fallback ============

  function connectWs() {
    _disconnectAll()
    _tryWebSocket()
  }

  function _disconnectAll() {
    if (wsInstance) {
      wsInstance.onclose = null
      wsInstance.close()
      wsInstance = null
    }
    if (sseInstance) {
      sseInstance.close()
      sseInstance = null
    }
  }

  function _tryWebSocket() {
    const token = localStorage.getItem('elaina_token')
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/panel?token=${token || ''}`

    wsInstance = new WebSocket(url)

    wsInstance.onopen = () => {
      connected.value = true
      wsFailCount = 0
    }

    wsInstance.onmessage = (event) => {
      _handleMessage(event.data)
    }

    wsInstance.onclose = () => {
      connected.value = false
      wsInstance = null
      wsFailCount++
      if (wsFailCount >= WS_MAX_FAIL) {
        _trySSE()
      } else {
        setTimeout(_tryWebSocket, RECONNECT_DELAY)
      }
    }

    wsInstance.onerror = () => {
      wsInstance.close()
    }
  }

  function _trySSE() {
    const token = localStorage.getItem('elaina_token')
    const url = `${window.location.origin}/api/sse/panel?token=${token || ''}`

    sseInstance = new EventSource(url)

    sseInstance.onopen = () => {
      connected.value = true
    }

    sseInstance.onmessage = (event) => {
      _handleMessage(event.data)
    }

    sseInstance.onerror = () => {
      sseInstance.close()
      sseInstance = null
      connected.value = false
      setTimeout(() => {
        wsFailCount = 0
        _tryWebSocket()
      }, RECONNECT_DELAY)
    }
  }

  function _handleMessage(raw) {
    try {
      const msg = JSON.parse(raw)
      window.dispatchEvent(new CustomEvent('ws-message', { detail: msg }))

      if (msg.type === 'system_info' && msg.data) {
        systemInfo.value = { ...systemInfo.value, ...msg.data }
      }
    } catch (e) {}
  }

  return {
    systemInfo,
    connected,
    bots,
    currentBotId,
    currentBot,
    isAllBots,
    sidebarCollapsed,
    fetchApi,
    postApi,
    loadSystemInfo,
    fetchBots,
    switchBot,
    connectWs,
  }
})
