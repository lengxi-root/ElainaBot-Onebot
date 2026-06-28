let ws = null
let sse = null
let listeners = {}
let reconnectTimer = null
let wsFailCount = 0

const RECONNECT_DELAY = 3000
const MAX_WS_FAILS = 2

export function connect() {
  wsFailCount >= MAX_WS_FAILS ? connectSSE() : connectWS()
}

export function disconnect() {
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
  if (ws) { ws.close(); ws = null }
  if (sse) { sse.close(); sse = null }
}

export function on(event, handler) {
  if (!listeners[event]) listeners[event] = []
  listeners[event].push(handler)
}

export function off(event, handler) {
  if (listeners[event]) {
    listeners[event] = listeners[event].filter(h => h !== handler)
  }
}

function connectWS() {
  if (ws && ws.readyState <= 1) return
  const token = localStorage.getItem('elaina_token')
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${proto}://${location.host}/ws/panel?token=${token || ''}`

  ws = new WebSocket(url)
  ws.onopen = () => { wsFailCount = 0; emit('open'); clearReconnect() }
  ws.onmessage = (e) => { handleMessage(e.data) }
  ws.onclose = () => { wsFailCount++; emit('close'); scheduleReconnect() }
  ws.onerror = () => { ws.close() }
}

function connectSSE() {
  if (sse && sse.readyState <= 1) return
  const token = localStorage.getItem('elaina_token')
  const url = `${location.origin}/api/sse/panel?token=${token || ''}`

  sse = new EventSource(url)
  sse.onopen = () => { emit('open'); clearReconnect() }
  sse.onmessage = (e) => { handleMessage(e.data) }
  sse.onerror = () => { sse.close(); sse = null; emit('close'); scheduleReconnect() }
}

function handleMessage(raw) {
  try {
    const msg = JSON.parse(raw)
    emit(msg.type, msg.data)
  } catch {}
}

function emit(event, data) {
  for (const h of listeners[event] || []) {
    try { h(data) } catch {}
  }
}

function clearReconnect() {
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
}

function scheduleReconnect() {
  if (!reconnectTimer) {
    reconnectTimer = setTimeout(() => { reconnectTimer = null; connect() }, RECONNECT_DELAY)
  }
}
