import { defineStore } from 'pinia'
import { ref } from 'vue'

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
  const ws = ref(null)

  async function fetchApi(path, options = {}) {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: getHeaders(),
      ...options,
    })
    if (res.status === 401) {
      localStorage.removeItem('elaina_token')
      window.location.href = '/web/login'
      return null
    }
    return res.json()
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

  function connectWs() {
    const token = localStorage.getItem('elaina_token')
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/ws/panel?token=${token}`

    const socket = new WebSocket(url)

    socket.onopen = () => {
      connected.value = true
    }

    socket.onclose = () => {
      connected.value = false
      setTimeout(connectWs, 3000)
    }

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        window.dispatchEvent(new CustomEvent('ws-message', { detail: msg }))
      } catch (e) {}
    }

    ws.value = socket
  }

  return {
    systemInfo,
    connected,
    fetchApi,
    postApi,
    loadSystemInfo,
    connectWs,
  }
})
