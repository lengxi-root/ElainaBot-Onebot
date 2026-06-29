<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useAppStore } from '../stores/app'
import { on, off } from '../utils/ws'
import axios from '../utils/axios'
import { parseMessageReference } from '../utils/messageReference'

const app = useAppStore()
let _unmounted = false
const nickCache = {}
const PAGE = 50
const isMobile = ref(window.innerWidth < 768)
const mobileView = ref('list')
const chatType = ref('group')
const chatDays = ref(1)
const chatSearch = ref('')
const chats = ref([])
const page = ref(1)
const total = ref(0)
const current = ref(null)
const history = ref([])
const historyRef = ref(null)
const msgType = ref('text')
const msgText = ref('')
const imgFile = ref(null)
const sending = ref(false)
const sendErr = ref('')
const recalling = ref('')
const rawDataMsg = ref(null)
const quotedMsg = ref(null)
const lastMsgId = ref('')
const oldestDate = ref('')
const hasMore = ref(true)
const loadingOlder = ref(false)
const mediaFileType = ref('1')
const imgPreview = ref('')
const mobileTypeOpen = ref(false)
const mobileMediaOpen = ref(false)
const msgTypeOptions = [
  { value: 'text', label: '普通消息' },
  { value: 'media', label: '富媒体' },
]
const mediaTypeOptions = [
  { value: '1', label: '图片' },
  { value: '2', label: '视频' },
  { value: '3', label: '语音' },
  { value: '4', label: '文件' },
]

const apiChatType = computed(() => chatType.value)
const groupRoles = ref({})
const remarkInput = ref('')
const remarkQqInput = ref('')
const remarkEditing = ref(null)
const remarkModalVisible = ref(false)
const addRemarkModalVisible = ref(false)
const addRemarkOpenid = ref('')
const addRemarkName = ref('')
const addRemarkQq = ref('')
const placeholder = computed(() => msgType.value === 'media' ? '输入资源 URL... (Ctrl+Enter 发送)' : '输入消息内容... (Ctrl+Enter 发送)')
const quotedPreview = computed(() => quotedMsg.value ? buildQuotePreview(quotedMsg.value) : '')
const mobileMsgTypeLabel = computed(() => msgTypeOptions.find(o => o.value === msgType.value)?.label || 'MD')
const mobileMediaTypeLabel = computed(() => mediaTypeOptions.find(o => o.value === mediaFileType.value)?.label || '图片')
const MEDIA_RE = /\[(图片|语音|视频|文件|媒体|media)](\S+)/

function handleResize() { isMobile.value = window.innerWidth < 768 }
function goBackToList() { mobileView.value = 'list'; current.value = null }
function closeMobileTypeMenu() { mobileTypeOpen.value = false; mobileMediaOpen.value = false }
function selectMobileMsgType(value) { msgType.value = value; closeMobileTypeMenu() }
function selectMobileMediaType(value) { mediaFileType.value = value; closeMobileTypeMenu() }
function getBotAvatar(bot_qq) { const bot = app.bots.find(b => b.bot_qq === bot_qq); return bot?.avatar || '' }
function qqAvatar(qq) { return `http://q1.qlogo.cn/g?b=qq&nk=${qq}&s=100` }
function groupQqAvatar(qq) { return `http://p.qlogo.cn/gh/${qq}/${qq}/100/` }
// OneBot 的 user_id 均为真实 QQ 号, 头像统一走 q1.qlogo.cn
function avatarUrl(_bot_qq, uid) { return qqAvatar(uid) }
function openUrl(u) { const a = document.createElement('a'); a.href = u; a.target = '_blank'; a.rel = 'noreferrer noopener'; a.click() }
const lightboxSrc = ref('')
function previewImg(src) { lightboxSrc.value = src }
function closeLightbox() { lightboxSrc.value = '' }
const COSTLY_DOMAINS = ['myqcloud.com', 'aliyuncs.com', 'cos.ap-']
function isCostlyUrl(url) { return COSTLY_DOMAINS.some(d => url.includes(d)) }
function revealImg(e) { const el = e.currentTarget; const src = el.dataset.src; if (src) { const img = document.createElement('img'); img.src = src; img.className = 'bubble-media-img'; img.style.cssText = 'max-width:160px;max-height:120px;width:auto;height:auto;border-radius:6px;display:block;cursor:pointer'; img.referrerPolicy = 'no-referrer'; img.loading = 'lazy'; img.onclick = () => previewImg(src); el.replaceWith(img) } }
function shortTime(t) { return t ? (t.length > 10 ? t.slice(11, 16) : t) : '' }
function stripYear(t) { if (!t) return ''; const m = t.match(/^\d{4}-(\d{2}-\d{2}\s+\d{2}:\d{2}(:\d{2})?)$/); return m ? m[1] : t }

function isAuditId(id) { return id && id.startsWith('msg_auditid_') }
function canRecall(m) { return !!m.message_id && !isAuditId(m.message_id) }
function canQuote(m) { return !!m.message_id && !isAuditId(m.message_id) && !m._recalled && !m._audit_rejected }
function showRaw(m) { rawDataMsg.value = rawDataMsg.value === m ? null : m }
function formatRaw(m) {
  if (m.raw_message) {
    try { return JSON.stringify(JSON.parse(m.raw_message), null, 2) } catch {}
    return m.raw_message
  }
  return JSON.stringify({ message_id: m.message_id, user_id: m.user_id, content: m.content, timestamp: m.timestamp, source: m.source, is_self: m.is_self, bot_qq: m.bot_qq }, null, 2)
}

function quoteAuthor(m) { return m.is_self ? '我' : (m.nickname || m.user_id || '未知用户') }
function buildQuotePreview(m) {
  if (m._segments) {
    const t = m._segments.map(s => s.kind === 'text' ? s.text : s.kind === 'at' ? atLabel(s) : s.kind === 'image' ? '[图片]' : s.kind === 'audio' ? '[语音]' : s.kind === 'video' ? '[视频]' : (s.text || '')).join('')
    return t.replace(/\s+/g, ' ').trim() || '空消息'
  }
  if (m._media) return [m._media.type ? `[${m._media.type}]` : '[媒体]', m._media.text, m._media.src].filter(Boolean).join(' ')
  return String(m.content || '').replace(/\n\[keyboard\] [\s\S]*$/, '').replace(/\s+/g, ' ').trim() || '空消息'
}
function quoteTargetText(q) { return q?.text || (q?.id ? `ID: ${q.id}` : '引用消息') }
function prepareMessage(m) {
  m._segments = parseSegments(m)
  m._media = m._segments ? null : parseMedia(m.content)
  m._recalled = !!m.recalled
  m._quote = parseMessageReference(m)
  return m
}
function resolveMessageReferences(messages) {
  const byReferenceId = {}, byMessageId = {}
  for (const m of messages) {
    if (m.reference_id) byReferenceId[m.reference_id] = m
    if (m.message_id) byMessageId[m.message_id] = m
  }
  for (const m of messages) {
    const q = m._quote
    if (!q?.id) continue
    const target = byReferenceId[q.id] || byMessageId[q.id]
    if (!target || target === m) continue
    q.author = quoteAuthor(target)
    q.text = buildQuotePreview(target)
    q.message_id = target.message_id || ''
  }
}
function quoteMsg(m) {
  if (!canQuote(m)) return
  quotedMsg.value = m
}
function clearQuote() { quotedMsg.value = null }

async function recallMsg(m) {
  if (recalling.value || !m.message_id) return
  recalling.value = m.message_id
  try {
    const res = await axios.post('/api/message/recall', {
      chat_type: apiChatType.value,
      chat_id: current.value?.chat_id || '',
      bot_qq: m.bot_qq || app.currentBotId || '',
      message_id: m.message_id,
    })
    if (res.data?.success) {
      m._recalled = true
    } else {
      sendErr.value = res.data?.message || '撤回失败'
    }
  } catch (e) {
    sendErr.value = e.response?.data?.message || e.message || '撤回失败'
  } finally {
    recalling.value = ''
  }
}
function escapeHtml(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;') }

const IMG_URL_RE = /(?:<[^>]*>)*<(https?:\/\/[^>]*(?:multimedia\.nt\.qq\.com\.cn|qqbot\.ugcimg\.cn|gchat\.qpic\.cn)[^>]*)>/

const MD_IMG_RE = /!\[[^\]]*\]\(([^)]+)\)/

function parseMedia(content) {
  if (!content) return null
  const m = content.match(MEDIA_RE)
  if (m) { const text = content.replace(m[0], '').replace(/^\n+|\n+$/g, '').trim(); return { type: m[1], src: m[2], text } }
  const im = content.match(IMG_URL_RE)
  if (im) { const text = content.replace(im[0], '').replace(/^\n+|\n+$/g, '').trim(); return { type: '图片', src: im[1], text } }
  const md = content.match(MD_IMG_RE)
  if (md) { const text = content.replace(md[0], '').replace(/^\n+|\n+$/g, '').trim(); return { type: '图片', src: md[1], text } }
  return null
}

function renderContent(content) {
  if (!content) return ''
  let text = content, kbHtml = ''
  const ki = content.indexOf('\n[keyboard] ')
  if (ki !== -1) {
    text = content.slice(0, ki)
    try {
      const kb = JSON.parse(content.slice(ki + 12))
      const rows = kb?.content?.rows || []
      const _svg = 'width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"'
      const _icons = {
        0: `<svg ${_svg}><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>`,
        1: `<svg ${_svg}><polyline points="9 10 4 15 9 20"/><path d="M20 4v7a4 4 0 0 1-4 4H4"/></svg>`,
        2: `<svg ${_svg}><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>`,
      }
      const rowsHtml = rows.map(row => {
        const btns = (row.buttons || []).map(b => {
          const rd = b.render_data || {}, ac = b.action || {}
          const cls = ['kb-btn', `kb-t${ac.type ?? 2}`]; if (rd.style === 1) cls.push('kb-primary')
          const tips = []; if (ac.data) tips.push(ac.data); if (ac.enter) tips.push('回车发送')
          const icon = _icons[ac.type] || _icons[2]
          return `<span class="${cls.join(' ')}"${tips.length ? ` title="${tips.join(' · ')}"` : ''}>${icon}${escapeHtml(rd.label || '?')}</span>`
        })
        return `<div class="kb-row">${btns.join('')}</div>`
      })
      if (rowsHtml.length) kbHtml = `<div class="kb-wrap">${rowsHtml.join('')}</div>`
    } catch {}
  }
  let h = escapeHtml(text)
  h = h.replace(/```([\s\S]*?)```/g, '<pre class="md-code-block">$1</pre>')
  h = h.replace(/`([^`]+)`/g, '<code class="md-code">$1</code>')
  h = h.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
  h = h.replace(/\*(.+?)\*/g, '<i>$1</i>')
  h = h.replace(/~~(.+?)~~/g, '<s>$1</s>')
  h = h.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '')
  h = h.replace(/\[([^\]]+)]\(([^)]+)\)/g, '<a href="$2" target="_blank" class="md-link">$1</a>')
  h = h.replace(/\n/g, '<br>')
  return h + kbHtml
}

// 从 raw_message (OneBot 事件 JSON) 解析消息段, 用于富文本渲染 (@蓝标 / 图片 等)
function parseSegments(m) {
  if (!m.raw_message || typeof m.raw_message !== 'string' || m.raw_message[0] !== '{') return null
  let arr
  try { arr = JSON.parse(m.raw_message).message } catch { return null }
  if (!Array.isArray(arr) || !arr.length) return null
  const segs = []
  for (const seg of arr) {
    if (!seg || typeof seg !== 'object') continue
    const d = seg.data || {}
    switch (seg.type) {
      case 'text': if ((d.text ?? '') !== '') segs.push({ kind: 'text', text: String(d.text) }); break
      case 'at': segs.push({ kind: 'at', qq: String(d.qq ?? ''), name: d.name ? String(d.name) : '' }); break
      case 'image': segs.push({ kind: 'image', src: String(d.url || d.file || '') }); break
      case 'face': segs.push({ kind: 'tag', text: '[表情]' }); break
      case 'record': segs.push({ kind: 'audio', src: String(d.url || d.file || '') }); break
      case 'video': segs.push({ kind: 'video', src: String(d.url || d.file || '') }); break
      case 'reply': break
      default: segs.push({ kind: 'tag', text: `[${seg.type}]` })
    }
  }
  return segs.length ? segs : null
}
function atLabel(seg) { return seg.qq === 'all' ? '@全体成员' : `@${seg.name || seg.qq}` }

let _fetchTimer = null
async function fetchChats() {
  if (_unmounted) return
  try {
    const res = await axios.post('/api/message/chats', { type: chatType.value, search: chatSearch.value, bot_qq: app.currentBotId || '', page: page.value, page_size: PAGE, days: chatDays.value })
    if (_unmounted) return
    chats.value = res.data?.data?.chats || []
    total.value = res.data?.data?.total || chats.value.length
  } catch { if (!_unmounted) { chats.value = []; total.value = 0 } }
}

function memberInfo(uid) { return groupRoles.value[uid] || {} }
// 优先用消息自带的 sender.role (OneBot 群消息携带), 退回成员列表
function msgRole(m) { return String(m.role || memberInfo(m.user_id).role || '') }
function roleLabel(r) {
  if (r === 'owner') return '群主'
  if (r === 'admin') return '管理'
  if (r) return '群员'
  return ''
}
function roleClass(r) {
  if (r === 'owner') return 'role-owner'
  if (r === 'admin') return 'role-admin'
  return 'role-member'
}
// 机器人 QQ 号段判定 (这些号段/号码为机器人账号)
function isBotQq(uid) {
  const n = Number(uid)
  if (!n) return false
  return (n >= 2854000000 && n <= 2855000000) ||
    (n >= 3889000000 && n <= 3890000000) ||
    (n >= 4010000000 && n <= 4019999999) ||
    n === 3328144510 || n === 66600000
}
function isBot(uid) { return !!memberInfo(uid).is_bot || isBotQq(uid) }

const _rolesCache = {}
const _ROLES_CACHE_TTL = 120000
async function fetchGroupRoles(groupId) {
  if (!groupId) { groupRoles.value = {}; return }
  const cached = _rolesCache[groupId]
  if (cached && Date.now() - cached.ts < _ROLES_CACHE_TTL) { groupRoles.value = cached.data; return }
  try {
    const res = await axios.post('/api/message/group-roles', { group_id: groupId })
    const data = res.data?.data || {}
    _rolesCache[groupId] = { data, ts: Date.now() }
    groupRoles.value = data
  } catch { groupRoles.value = {} }
}

async function setRemark() {
  if (!remarkEditing.value) return
  try {
    await axios.post('/api/message/remarks', { group_id: remarkEditing.value, remark: remarkInput.value.trim(), group_qq: remarkQqInput.value.trim() })
    remarkModalVisible.value = false
    remarkEditing.value = null
    remarkInput.value = ''
    remarkQqInput.value = ''
    fetchChats()
  } catch {}
}

function startRemark(c) {
  remarkEditing.value = c.chat_id
  remarkInput.value = c.remark || ''
  remarkQqInput.value = c.group_qq || ''
  remarkModalVisible.value = true
}
function cancelRemark() {
  remarkModalVisible.value = false
  remarkEditing.value = null
  remarkInput.value = ''
  remarkQqInput.value = ''
}

function openAddRemark() {
  addRemarkOpenid.value = ''
  addRemarkName.value = ''
  addRemarkQq.value = ''
  addRemarkModalVisible.value = true
}
async function submitAddRemark() {
  const openid = addRemarkOpenid.value.trim()
  if (!openid) return
  try {
    await axios.post('/api/message/remarks', { group_id: openid, remark: addRemarkName.value.trim(), group_qq: addRemarkQq.value.trim() })
    addRemarkModalVisible.value = false
    fetchChats()
  } catch {}
}
function cancelAddRemark() {
  addRemarkModalVisible.value = false
}
function fetchChatsDebounced() {
  if (_fetchTimer) return
  _fetchTimer = setTimeout(() => { _fetchTimer = null; fetchChats() }, 5000)
}

let _selectId = 0
async function selectChat(chat) {
  const myId = ++_selectId
  current.value = chat; msgText.value = ''; sendErr.value = ''; imgFile.value = null; quotedMsg.value = null
  hasMore.value = true; oldestDate.value = ''; loadingOlder.value = false; groupRoles.value = {}
  if (isMobile.value) mobileView.value = 'chat'
  history.value = []
  try {
    const res = await axios.post('/api/message/history', { chat_type: apiChatType.value, chat_id: chat.chat_id, bot_qq: app.currentBotId || '' })
    if (myId !== _selectId) return
    const msgs = res.data?.data?.messages || []
    for (const m of msgs) prepareMessage(m)
    resolveMessageReferences(msgs)
    history.value = msgs; lastMsgId.value = res.data?.data?.last_msg_id || ''
    if (apiChatType.value === 'group') fetchGroupRoles(chat.chat_id)
    oldestDate.value = res.data?.data?.oldest_date || ''
    hasMore.value = res.data?.data?.has_more !== false
    await nextTick(); scrollBottom(); watchImgLoads()
  } catch { if (myId === _selectId) { history.value = []; lastMsgId.value = ''; hasMore.value = false } }
}

async function loadOlder() {
  if (loadingOlder.value || !hasMore.value || !current.value || !oldestDate.value) return
  loadingOlder.value = true
  try {
    const res = await axios.post('/api/message/history', {
      chat_type: apiChatType.value, chat_id: current.value.chat_id,
      bot_qq: app.currentBotId || '', before_date: oldestDate.value,
    })
    const msgs = res.data?.data?.messages || []
    if (!msgs.length) { hasMore.value = false; return }
    for (const m of msgs) prepareMessage(m)
    const el = historyRef.value
    const prevH = el ? el.scrollHeight : 0
    history.value = [...msgs, ...history.value]
    resolveMessageReferences(history.value)
    oldestDate.value = res.data?.data?.oldest_date || oldestDate.value
    hasMore.value = res.data?.data?.has_more !== false
    await nextTick()
    if (el) el.scrollTop = el.scrollHeight - prevH
  } catch { hasMore.value = false }
  finally { loadingOlder.value = false }
}

function onHistoryScroll() {
  const el = historyRef.value
  if (el && el.scrollTop < 60 && hasMore.value && !loadingOlder.value) loadOlder()
}

async function refreshMsgId() {
  if (!current.value) return
  try { const r = await axios.post('/api/message/history', { chat_type: apiChatType.value, chat_id: current.value.chat_id, bot_qq: app.currentBotId || '', limit: 1 }); lastMsgId.value = r.data?.data?.last_msg_id || lastMsgId.value } catch {}
}

function isNearBottom() { const el = historyRef.value; if (!el) return true; return el.scrollHeight - el.scrollTop - el.clientHeight < 80 }
function scrollBottom() { const el = historyRef.value; if (el) el.scrollTop = el.scrollHeight }

let _autoScroll = false
function watchImgLoads() {
  _autoScroll = true
  const el = historyRef.value; if (!el) return
  const stop = () => { _autoScroll = false; el.removeEventListener('wheel', stop); el.removeEventListener('touchmove', stop) }
  el.addEventListener('wheel', stop, { once: true, passive: true })
  el.addEventListener('touchmove', stop, { once: true, passive: true })
  const handler = () => { if (_autoScroll) scrollBottom() }
  el.querySelectorAll('img').forEach(img => { if (!img.complete) img.addEventListener('load', handler, { once: true }) })
  setTimeout(stop, 3000)
}

async function getNick(uid) {
  if (!uid) return '未知用户'; if (nickCache[uid]) return nickCache[uid]
  try { const n = (await axios.post('/api/message/nickname', { user_id: uid })).data?.data?.nickname || `用户${uid.slice(-6)}`; nickCache[uid] = n; return n } catch { return `用户${uid.slice(-6)}` }
}

async function onNewLog(data) {
  if (!data || _unmounted) return
  if (data.log_type === 'audit') { onAuditLog(data); return }
  if (data.log_type === 'lifecycle') { onLifecycleLog(data); return }
  if (data.log_type !== 'message') return; fetchChatsDebounced(); if (!current.value) return
  const gid = data.group_id || '', uid = data.user_id || '', cid = current.value.chat_id
  if ((apiChatType.value === 'group' && gid === cid) || (apiChatType.value === 'user' && uid === cid && !gid)) {
    const isSelf = data.direction === 'send'
    const nick = isSelf ? (data.bot_name || 'Bot') : await getNick(uid)
    if (_unmounted) return
    const item = prepareMessage({ id: history.value.length, message_id: data.message_id || '', reference_id: data.reference_id || '', user_id: uid, bot_qq: data.bot_qq || app.currentBot?.bot_qq || '', bot_qq: isSelf ? (data.bot_qq || '') : '', nickname: nick, content: data.content || '', timestamp: data.timestamp || '', is_self: isSelf, source: data.source || '', raw_message: data.raw_message || '' })
    history.value.push(item)
    resolveMessageReferences(history.value)
    if (isNearBottom()) nextTick(scrollBottom)
  }
}

async function onLifecycleLog(data) {
  if (!current.value || apiChatType.value !== 'group') return
  const evtType = data.type || ''
  if (evtType !== 'group_member_add' && evtType !== 'group_member_del') return
  const gid = data.group_id || '', uid = data.user_id || '', cid = current.value.chat_id
  if (gid !== cid) return
  const nick = await getNick(uid)
  if (_unmounted) return
  history.value.push({
    id: `lc_rt_${Date.now()}`,
    message_id: '', reference_id: '', user_id: uid,
    bot_qq: data.bot_qq || app.currentBot?.bot_qq || '',
    bot_qq: '', nickname: nick, content: '', timestamp: data.timestamp || '',
    is_self: false, source: '', raw_message: '', recalled: false,
    event_type: evtType === 'group_member_add' ? 'member_add' : 'member_remove',
  })
  if (isNearBottom()) nextTick(scrollBottom)
}

function onAuditLog(data) {
  if (!data.audit_id) return
  const m = history.value.find(msg => msg.message_id === data.audit_id)
  if (m) {
    if (data.passed && data.message_id) {
      m.message_id = data.message_id
    } else if (!data.passed) {
      m._audit_rejected = true
    }
  }
}

function onImgSelect(e) { const f = e.target.files?.[0]; if (f) { imgFile.value = f; imgPreview.value = URL.createObjectURL(f) }; e.target.value = '' }
function clearImg() { if (imgPreview.value) URL.revokeObjectURL(imgPreview.value); imgFile.value = null; imgPreview.value = '' }

function onKeydown(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMsg() } }

async function sendMsg() {
  if (sending.value || !current.value) return
  sending.value = true; sendErr.value = ''
  try {
    const content = msgText.value.trim()
    if (!content && !imgFile.value) { sending.value = false; return }
    const fd = new FormData()
    fd.append('chat_type', apiChatType.value); fd.append('chat_id', current.value.chat_id)
    fd.append('bot_qq', app.currentBotId || current.value.bot_qq || '')
    fd.append('msg_type', msgType.value); fd.append('content', content); fd.append('msg_id', lastMsgId.value)
    if (quotedMsg.value) {
      if (quotedMsg.value.reference_id) fd.append('message_reference_id', quotedMsg.value.reference_id)
      if (quotedMsg.value.message_id) fd.append('quote_message_id', quotedMsg.value.message_id)
    }
    if (imgFile.value && msgType.value === 'text') fd.append('image', imgFile.value)
    if (msgType.value === 'media') fd.append('media_file_type', mediaFileType.value)
    const res = await axios.post('/api/message/send', fd)
    if (res.data?.success) { msgText.value = ''; clearImg(); clearQuote() }
    else sendErr.value = res.data?.message || '发送失败'
  } catch (e) { sendErr.value = e.response?.data?.message || e.message || '发送失败' }
  finally { sending.value = false }
}

watch(chatType, () => { current.value = null; quotedMsg.value = null; history.value = []; chats.value = []; lastMsgId.value = ''; oldestDate.value = ''; hasMore.value = true; page.value = 1; remarkEditing.value = null; groupRoles.value = {}; fetchChats() })
watch(chatDays, () => { page.value = 1; fetchChats() })
watch(chatSearch, () => { page.value = 1; fetchChats() })
watch(() => app.currentBotId, () => { current.value = null; quotedMsg.value = null; history.value = []; lastMsgId.value = ''; oldestDate.value = ''; hasMore.value = true; page.value = 1; fetchChats() })

onMounted(() => { fetchChats(); on('new_log', onNewLog); window.addEventListener('resize', handleResize); document.addEventListener('click', closeMobileTypeMenu) })
onUnmounted(() => { _unmounted = true; off('new_log', onNewLog); window.removeEventListener('resize', handleResize); document.removeEventListener('click', closeMobileTypeMenu); if (_fetchTimer) { clearTimeout(_fetchTimer); _fetchTimer = null } })
</script>

<template>
  <div class="msg-page">
    <div class="msg-layout">
      <!-- Chat list -->
      <div :class="['chat-list-panel', { 'mobile-hidden': isMobile && mobileView !== 'list' }]">
        <div class="panel-header">
          <span>聊天列表</span>
          <n-radio-group v-model:value="chatType" size="tiny">
            <n-radio-button value="group">群</n-radio-button>
            <n-radio-button value="user">好友</n-radio-button>
          </n-radio-group>
          <n-radio-group v-model:value="chatDays" size="tiny" class="days-sel">
            <n-radio-button :value="1">1天</n-radio-button>
            <n-radio-button :value="2">2天</n-radio-button>
            <n-radio-button :value="3">3天</n-radio-button>
          </n-radio-group>
        </div>
        <n-input v-model:value="chatSearch" placeholder="搜索..." size="small" clearable class="chat-search" />
        <div class="chat-items">
          <div v-for="c in chats" :key="c.chat_id" :class="['chat-item', { active: current?.chat_id === c.chat_id }]" @click="selectChat(c)">
            <div class="chat-avatar-wrap">
              <img v-if="chatType === 'user' && c.chat_id" class="chat-avatar" :src="qqAvatar(c.chat_id)" loading="lazy" @error="e => e.target.style.display='none'" />
              <img v-else-if="chatType === 'group' && c.chat_id" class="chat-avatar" :src="groupQqAvatar(c.chat_id)" loading="lazy" @error="e => e.target.style.display='none'" />
              <img v-else-if="app.isAllBots && c.bot_qq && getBotAvatar(c.bot_qq)" class="chat-avatar" :src="getBotAvatar(c.bot_qq)" loading="lazy" @error="e => e.target.style.display='none'" />
              <div v-else class="chat-avatar-fallback">{{ (c.nickname || c.chat_id || '?').charAt(0) }}</div>
              <span v-if="c.is_full_access" class="chat-avatar-badge">全</span>
            </div>
            <div class="chat-info">
              <div class="chat-nick">{{ c.nickname || c.chat_id }}</div>
              <div v-if="c.nickname && c.nickname !== c.chat_id" class="chat-id">{{ c.chat_id }}</div>
              <div class="chat-preview">{{ c.last_content || '' }}</div>
            </div>
            <div class="chat-meta">
              <div class="chat-time">{{ shortTime(c.last_time) }}</div>
              <div v-if="c.msg_count" class="chat-count">{{ c.msg_count }}</div>
              <button v-if="chatType !== 'user'" class="remark-btn" title="备注" @click.stop="startRemark(c)">✎</button>
            </div>
          </div>
          <div v-if="!chats.length" class="chat-empty">暂无聊天</div>
        </div>
        <div v-if="total > PAGE" class="chat-pager">
          <button :disabled="page <= 1" @click="page--; fetchChats()">&lt;</button>
          <span>{{ page }} / {{ Math.ceil(total / PAGE) }}</span>
          <button :disabled="page >= Math.ceil(total / PAGE)" @click="page++; fetchChats()">&gt;</button>
        </div>
      </div>

      <!-- History panel -->
      <div :class="['chat-history-panel', { 'mobile-hidden': isMobile && mobileView !== 'chat' }]">
        <template v-if="current">
          <div class="panel-header">
            <button v-if="isMobile" class="mobile-back-btn" @click="goBackToList">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
            </button>
            <span>{{ current.nickname || current.chat_id }}</span>
            <span v-if="current.nickname && current.nickname !== current.chat_id" class="panel-header-remark">({{ current.chat_id }})</span>
            <span class="panel-header-info">
              <template v-if="lastMsgId">msg_id: {{ lastMsgId.slice(0, 16) }}...</template>
              <button class="refresh-msgid-btn" @click="refreshMsgId" title="刷新消息ID">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2v6h-6" /><path d="M3 12a9 9 0 0 1 15-6.7L21 8" /><path d="M3 22v-6h6" /><path d="M21 12a9 9 0 0 1-15 6.7L3 16" /></svg>
              </button>
            </span>
          </div>
          <div class="history-body" ref="historyRef" @scroll="onHistoryScroll">
            <div v-if="loadingOlder" class="history-hint">加载中...</div>
            <div v-else-if="!hasMore && history.length" class="history-hint">没有更多消息了</div>
            <template v-for="m in history" :key="m.id">
            <div v-if="m.event_type" class="event-wrap">
              <div class="event-box">
                <img v-if="m.bot_qq && m.user_id" class="event-avatar" :src="avatarUrl(m.bot_qq, m.user_id)" loading="lazy" @error="e => e.target.style.display='none'" />
                <div v-else class="event-avatar-fallback">{{ (m.nickname || '?').charAt(0) }}</div>
                <span class="event-uid">{{ m.user_id }}</span>
                <span class="event-text">{{ m.event_type === 'member_add' ? '已加入本群' : '已退出本群' }}</span>
              </div>
            </div>
            <div v-else :class="['bubble-wrap', { self: m.is_self === true }]">
              <div class="bubble-avatar-wrap">
                <img v-if="m.is_self && m.bot_qq" class="msg-avatar" :src="qqAvatar(m.bot_qq)" loading="lazy" @error="e => e.target.style.display='none'" />
                <div v-else-if="m.is_self" class="msg-avatar-bot">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="14" rx="3" /><circle cx="9" cy="11" r="1.5" fill="currentColor" /><circle cx="15" cy="11" r="1.5" fill="currentColor" /><path d="M12 2v2M6 20l2-2M18 20l-2-2" /></svg>
                </div>
                <img v-else-if="m.bot_qq && m.user_id" class="msg-avatar" :src="avatarUrl(m.bot_qq, m.user_id)" loading="lazy" @error="e => e.target.style.display='none'" />
                <div v-else class="msg-avatar-fallback">{{ (m.nickname || '?').charAt(0) }}</div>
              </div>
              <div class="bubble-main">
                <div class="bubble-name">
                  {{ m.nickname }}
                  <span v-if="m.source === 'web_panel'" class="bubble-src-tag">Web</span>
                  <span v-if="msgRole(m) && !m.is_self && apiChatType === 'group'" :class="['bubble-role-tag', roleClass(msgRole(m))]">{{ roleLabel(msgRole(m)) }}</span>
                  <span v-if="isBot(m.user_id) && !m.is_self && apiChatType === 'group'" class="bubble-role-tag role-bot">Bot</span>
                  <span v-if="m.user_id && !m.is_self" class="bubble-uid">{{ m.user_id }}</span>
                </div>
                <div class="bubble-row">
                  <div :class="['bubble', { 'bubble-self': m.is_self }]">
                    <div v-if="m._quote" class="bubble-quote-ref">
                      <div class="bubble-quote-author">引用 {{ m._quote.author || '消息' }}</div>
                      <div class="bubble-quote-content">{{ quoteTargetText(m._quote) }}</div>
                    </div>
                    <span v-if="m._recalled" class="recalled-tag">已撤回</span>
                    <span v-else-if="m._audit_rejected" class="recalled-tag audit-reject">审核未通过</span>
                    <span v-else-if="m.is_self && isAuditId(m.message_id)" class="audit-tag">审核中</span>
                    <div v-if="m._segments" class="bubble-segs" style="word-break:break-all;overflow-wrap:anywhere;white-space:pre-wrap">
                      <template v-for="(seg, si) in m._segments" :key="si">
                        <span v-if="seg.kind === 'text'">{{ seg.text }}</span>
                        <span v-else-if="seg.kind === 'at'" class="bubble-at">{{ atLabel(seg) }}</span>
                        <template v-else-if="seg.kind === 'image'">
                          <span v-if="isCostlyUrl(seg.src)" class="bubble-media-placeholder" :data-src="seg.src" @click="revealImg($event)">🖼 点击加载图片 (外部存储)</span>
                          <img v-else :src="seg.src" class="bubble-media-img" style="max-width:160px;max-height:120px;width:auto;height:auto" referrerpolicy="no-referrer" @click="previewImg(seg.src)" @error="e => e.target.style.display='none'" loading="lazy" />
                        </template>
                        <audio v-else-if="seg.kind === 'audio'" :src="seg.src" controls preload="none" class="bubble-media-audio" />
                        <video v-else-if="seg.kind === 'video'" :src="seg.src" controls preload="none" class="bubble-media-video" />
                        <span v-else-if="seg.kind === 'tag'" class="bubble-media-text">{{ seg.text }}</span>
                      </template>
                    </div>
                    <template v-else-if="m._media">
                      <span v-if="m._media.text" class="bubble-media-text">{{ m._media.text }}</span>
                      <template v-if="['图片','media'].includes(m._media.type)">
                        <span v-if="isCostlyUrl(m._media.src)" class="bubble-media-placeholder" :data-src="m._media.src" @click="revealImg($event)">🖼 点击加载图片 (外部存储)</span>
                        <img v-else :src="m._media.src" class="bubble-media-img" style="max-width:160px;max-height:120px;width:auto;height:auto" referrerpolicy="no-referrer" @click="previewImg(m._media.src)" @error="e => e.target.style.display='none'" loading="lazy" />
                      </template>
                      <audio v-else-if="m._media.type === '语音'" :src="m._media.src" controls preload="none" class="bubble-media-audio" />
                      <video v-else-if="m._media.type === '视频'" :src="m._media.src" controls preload="none" class="bubble-media-video" />
                      <a v-else :href="m._media.src" target="_blank" class="bubble-media-link"> 📁 {{ m._media.src.split('/').pop() }}</a>
                    </template>
                    <div v-else v-html="renderContent(m.content)" style="word-break:break-all;overflow-wrap:anywhere;white-space:pre-wrap" />
                  </div>
                  <div class="bubble-actions">
                    <button v-if="canQuote(m)" class="action-btn" title="引用这条消息" @click="quoteMsg(m)">引</button>
                    <button class="action-btn" title="原始数据" @click="showRaw(m)">{ }</button>
                    <button v-if="canRecall(m) && !m._recalled" class="action-btn recall" :disabled="recalling === m.message_id" title="撤回" @click="recallMsg(m)">
                      {{ recalling === m.message_id ? '...' : '↩' }}
                    </button>
                  </div>
                </div>
                <span class="bubble-ts">{{ stripYear(m.timestamp) }}</span>
                <pre v-if="rawDataMsg === m" class="raw-data-box">{{ formatRaw(m) }}</pre>
              </div>
            </div>
            </template>
            <div v-if="!history.length" class="chat-empty" style="padding-top:48px">暂无消息记录，可在下方发送消息</div>
          </div>

          <!-- Send area -->
          <div class="send-area">
            <div v-if="quotedMsg" class="quote-preview">
              <div class="quote-main">
                <span class="quote-title">引用 {{ quoteAuthor(quotedMsg) }}</span>
                <span class="quote-text">{{ quotedPreview }}</span>
              </div>
              <button class="quote-clear" title="取消引用" @click="clearQuote">×</button>
            </div>
            <div class="send-toolbar">
              <select v-model="msgType" class="send-type-select"><option value="text">普通消息</option><option value="media">富媒体</option></select>
              <select v-if="msgType === 'media'" v-model="mediaFileType" class="send-type-select"><option value="1">图片</option><option value="2">视频</option><option value="3">语音</option><option value="4">文件</option></select>
              <label v-if="msgType === 'text'" class="send-img-label" title="选择图片">
                <input type="file" accept="image/*" @change="onImgSelect" hidden />
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="send-icon"><rect x="3" y="3" width="18" height="18" rx="3" /><circle cx="8.5" cy="8.5" r="1.5" fill="currentColor" /><path d="M21 15l-5-5L5 21" /></svg>
              </label>
              <span v-if="imgFile" class="send-img-tag">
                <img v-if="imgPreview" :src="imgPreview" class="send-img-preview" /> {{ imgFile.name }}
                <span class="send-img-remove" @click="clearImg">×</span>
              </span>
            </div>

            <!-- Normal send -->
            <div class="send-input-row">
              <div class="mobile-type-menu" @click.stop>
                <button type="button" class="mobile-type-trigger" @click="mobileTypeOpen = !mobileTypeOpen">
                  <span>{{ mobileMsgTypeLabel }}</span><span class="mobile-type-caret"></span>
                </button>
                <div v-if="mobileTypeOpen" class="mobile-type-options">
                  <button v-for="opt in msgTypeOptions" :key="opt.value" type="button" :class="{ active: msgType === opt.value }" @click="selectMobileMsgType(opt.value)">{{ opt.label }}</button>
                </div>
              </div>
              <div v-if="msgType === 'media'" class="mobile-type-menu mobile-media-menu" @click.stop>
                <button type="button" class="mobile-type-trigger" @click="mobileMediaOpen = !mobileMediaOpen">
                  <span>{{ mobileMediaTypeLabel }}</span><span class="mobile-type-caret"></span>
                </button>
                <div v-if="mobileMediaOpen" class="mobile-type-options">
                  <button v-for="opt in mediaTypeOptions" :key="opt.value" type="button" :class="{ active: mediaFileType === opt.value }" @click="selectMobileMediaType(opt.value)">{{ opt.label }}</button>
                </div>
              </div>
              <textarea v-model="msgText" class="send-input" rows="2" :placeholder="placeholder" @keydown="onKeydown" />
              <button class="send-btn" @click="sendMsg" :disabled="sending">{{ sending ? '...' : '发送' }}</button>
            </div>
            <div v-if="msgType === 'media'" class="send-hint"> 输入资源 URL, 将以富媒体消息 ({{ { '1':'图片','2':'视频','3':'语音','4':'文件' }[mediaFileType] }}) 发送 </div>
            <div v-if="sendErr" class="send-error">{{ sendErr }}</div>
          </div>
        </template>

        <div v-else class="no-chat">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:48px;height:48px;color:var(--text3);margin-bottom:12px"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" /></svg>
          <div>选择一个聊天查看消息</div>
        </div>
      </div>
    </div>
    <div v-if="lightboxSrc" class="lightbox-overlay" @click="closeLightbox">
      <img :src="lightboxSrc" class="lightbox-img" referrerpolicy="no-referrer" @click.stop />
      <span class="lightbox-close" @click="closeLightbox">&times;</span>
    </div>

    <n-modal v-model:show="remarkModalVisible" preset="dialog" title="群备注" positive-text="保存" negative-text="取消" @positive-click="setRemark" @negative-click="cancelRemark" style="width:380px">
      <div style="padding:8px 0">
        <div style="margin-bottom:8px;font-size:13px;color:var(--text2)">群号: {{ remarkEditing }}</div>
        <n-input v-model:value="remarkInput" placeholder="备注名称（留空则清除备注）" @keydown.enter="setRemark(); remarkModalVisible = false" />
      </div>
    </n-modal>

    <n-modal v-model:show="addRemarkModalVisible" preset="dialog" title="添加群备注" positive-text="保存" negative-text="取消" @positive-click="submitAddRemark" @negative-click="cancelAddRemark" style="width:380px">
      <div style="padding:8px 0">
        <n-input v-model:value="addRemarkOpenid" placeholder="群号" style="margin-bottom:8px" autofocus />
        <n-input v-model:value="addRemarkName" placeholder="备注名称" @keydown.enter="submitAddRemark(); addRemarkModalVisible = false" />
      </div>
    </n-modal>
  </div>
</template>

<style scoped>
.msg-page {
  height:calc(100vh - 100px);
  display:flex;
  flex-direction:column
}
.msg-title {
  color:var(--text);
  font-size:18px;
  font-weight:700;
  margin:0 0 12px
}
.msg-layout {
  flex:1;
  display:flex;
  gap:12px;
  min-height:0
}
.chat-list-panel {
  width:240px;
  flex-shrink:0;
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:var(--radius);
  box-shadow:var(--shadow-sm);
  display:flex;
  flex-direction:column;
  overflow:hidden
}
.panel-header {
  padding:10px 14px;
  border-bottom:1px solid var(--border);
  display:flex;
  align-items:center;
  flex-wrap:wrap;
  gap:6px;
  color:var(--text);
  font-size:14px;
  font-weight:600
}
.panel-header > span:first-child { margin-right:0 }
.add-remark-btn {
  background:none;
  border:1px solid var(--border);
  cursor:pointer;
  color:var(--text2);
  font-size:16px;
  font-weight:700;
  width:22px;
  height:22px;
  border-radius:4px;
  display:flex;
  align-items:center;
  justify-content:center;
  transition:color .15s,background .15s;
  margin-right:auto;
  line-height:1;
  padding:0
}
.add-remark-btn:hover {
  color:var(--accent);
  background:var(--bg-float)
}
.days-sel { font-weight:400 }
.chat-search {
  margin:8px 10px
}
.chat-items {
  flex:1;
  overflow-y:auto
}
.chat-item {
  display:flex;
  align-items:center;
  gap:10px;
  padding:10px 14px;
  cursor:pointer;
  transition:background .12s
}
.chat-item:hover {
  background:var(--bg3)
}
.chat-item.active {
  background:var(--accent-soft)
}
.chat-avatar-wrap {
  position:relative;
  flex-shrink:0;
  width:36px;
  height:36px
}
.chat-avatar {
  width:36px;
  height:36px;
  border-radius:50%;
  -o-object-fit:cover;
  object-fit:cover
}
.chat-avatar-fallback {
  width:36px;
  height:36px;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  background:linear-gradient(135deg,var(--accent),var(--accent-light));
  color:#fff;
  font-weight:700;
  font-size:14px
}
.chat-avatar-badge {
  position:absolute;
  bottom:-2px;
  right:-2px;
  width:16px;
  height:16px;
  border-radius:50%;
  background:#52c41a;
  color:#fff;
  font-size:9px;
  font-weight:700;
  display:flex;
  align-items:center;
  justify-content:center;
  border:2px solid var(--bg2);
  line-height:1
}
.chat-info {
  flex:1;
  min-width:0
}
.chat-nick {
  color:var(--text);
  font-size:14px;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
  display:flex;
  align-items:center;
  gap:4px
}
.chat-id {
  color:var(--text3);
  font-size:11px;
  font-family:monospace
}
.chat-preview {
  color:var(--text2);
  font-size:12px;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
  margin-top:2px
}
.chat-meta {
  flex-shrink:0;
  text-align:right
}
.chat-time {
  color:var(--text3);
  font-size:11px
}
.chat-count {
  background:var(--accent);
  color:#fff;
  font-size:10px;
  border-radius:8px;
  padding:1px 6px;
  margin-top:4px;
  display:inline-block
}
.chat-remark-label {
  font-size:10px;
  color:var(--accent);
  line-height:1.3
}
.remark-btn {
  background:none;
  border:none;
  cursor:pointer;
  color:var(--text3);
  font-size:12px;
  padding:2px 4px;
  border-radius:4px;
  transition:color .15s,background .15s;
  line-height:1
}
.remark-btn:hover {
  color:var(--accent);
  background:var(--bg3)
}
.panel-header-remark {
  font-size:12px;
  color:var(--accent);
  margin-left:4px
}
.chat-empty {
  color:var(--text3);
  text-align:center;
  padding:32px 0;
  font-size:13px
}
.chat-pager {
  display:flex;
  align-items:center;
  justify-content:center;
  gap:10px;
  padding:6px 10px;
  border-top:1px solid var(--border);
  flex-shrink:0;
  font-size:12px;
  color:var(--text2)
}
.chat-pager button {
  background:var(--bg3);
  border:1px solid var(--border);
  border-radius:4px;
  padding:2px 10px;
  cursor:pointer;
  color:var(--text);
  font-size:12px;
  transition:background .15s
}
.chat-pager button:hover:not(:disabled) {
  background:var(--accent);
  color:#fff
}
.chat-pager button:disabled {
  opacity:.3;
  cursor:default
}
.chat-history-panel {
  flex:1;
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:var(--radius);
  box-shadow:var(--shadow-sm);
  display:flex;
  flex-direction:column;
  overflow:hidden
}
.history-body {
  flex:1;
  overflow-y:auto;
  padding:12px 16px
}
.history-hint {
  text-align:center;
  color:var(--text3);
  font-size:12px;
  padding:8px 0
}
.event-wrap {
  display:flex;
  justify-content:center;
  margin-bottom:14px
}
.event-box {
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding:6px 16px;
  background:var(--border);
  border-radius:16px;
  font-size:13px;
  color:var(--text2)
}
.event-avatar {
  width:24px;
  height:24px;
  border-radius:50%;
  object-fit:cover;
  flex-shrink:0
}
.event-avatar-fallback {
  width:24px;
  height:24px;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  background:var(--text3);
  color:#fff;
  font-size:11px;
  font-weight:700;
  flex-shrink:0
}
.event-uid {
  font-family:monospace;
  font-size:12px;
  color:var(--text2);
  max-width:160px;
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap
}
.event-text {
  color:var(--text3);
  font-size:12px;
  white-space:nowrap
}
.no-chat {
  flex:1;
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:center;
  color:var(--text3)
}
.bubble-wrap {
  display:flex;
  gap:8px;
  margin-bottom:14px;
  max-width:100%
}
.bubble-wrap.self {
  flex-direction:row-reverse
}
.bubble-avatar-wrap {
  flex-shrink:0
}
.msg-avatar {
  width:32px;
  height:32px;
  border-radius:50%;
  -o-object-fit:cover;
  object-fit:cover
}
.msg-avatar-bot {
  width:32px;
  height:32px;
  border-radius:50%;
  flex-shrink:0;
  display:flex;
  align-items:center;
  justify-content:center;
  background:linear-gradient(135deg,var(--accent),#7289da);
  color:#fff
}
.msg-avatar-bot svg {
  width:20px;
  height:20px
}
.msg-avatar-fallback {
  width:32px;
  height:32px;
  border-radius:50%;
  display:flex;
  align-items:center;
  justify-content:center;
  background:var(--accent);
  color:#fff;
  font-size:12px;
  font-weight:700
}
.bubble-main {
  max-width:70%;
  min-width:0;
  overflow:hidden;
  word-break:break-all;
  overflow-wrap:anywhere
}
:deep(.bubble-main *) {
  word-break:break-all !important;
  overflow-wrap:anywhere !important
}
.bubble-name {
  color:var(--text2);
  font-size:11px;
  margin-bottom:3px
}
.self .bubble-name {
  text-align:right
}
.bubble-uid {
  color:var(--text3);
  margin-left:4px;
  font-family:monospace;
  font-size:10px
}
.bubble-ts {
  font-size:10px;
  color:var(--text3);
  margin-top:2px;
  display:block
}
.bubble-src-tag {
  font-size:9px;
  padding:0 4px;
  border-radius:3px;
  line-height:15px;
  background:#e8f5e9;
  color:#2e7d32;
  font-weight:600;
  margin-left:4px
}
.ob-tag {
  background:#e3f2fd;
  color:#1565c0
}
.bubble-role-tag {
  font-size:9px;
  padding:0 4px;
  border-radius:3px;
  line-height:15px;
  font-weight:600;
  margin-left:4px
}
.role-owner {
  background:#fff3e0;
  color:#e65100
}
.role-admin {
  background:#e8f5e9;
  color:#2e7d32
}
.role-member {
  background:#f5f5f5;
  color:#757575
}
.role-bot {
  background:#e3f2fd;
  color:#1565c0
}
.bubble {
  display:block;
  padding:8px 12px;
  border-radius:10px;
  font-size:14px;
  word-break:break-all;
  overflow-wrap:anywhere;
  min-width:0;
  background:var(--border);
  color:var(--text)
}
.bubble-self {
  background:var(--accent);
  color:#fff
}
.bubble-quote-ref {
  max-width:260px;
  margin-bottom:6px;
  padding:5px 8px;
  border-left:3px solid var(--accent);
  border-radius:6px;
  background:rgba(255,255,255,.42);
  color:var(--text2)
}
.bubble-self .bubble-quote-ref {
  border-left-color:rgba(255,255,255,.85);
  background:rgba(255,255,255,.18);
  color:rgba(255,255,255,.88)
}
.bubble-quote-author {
  font-size:11px;
  font-weight:600;
  line-height:1.3;
  margin-bottom:2px
}
.bubble-quote-content {
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  font-size:12px;
  line-height:1.35
}
.bubble-media-img {
  max-width:160px !important;
  max-height:120px !important;
  width:auto !important;
  height:auto !important;
  border-radius:6px;
  display:block;
  cursor:pointer;
  object-fit:contain
}
.bubble-media-img:hover {
  opacity:.9
}
.bubble-media-placeholder {
  display:inline-block;
  padding:8px 14px;
  background:rgba(100,180,255,.15);
  border:1px dashed rgba(100,180,255,.5);
  border-radius:6px;
  color:#7ab8ff;
  cursor:pointer;
  font-size:13px;
  user-select:none
}
.bubble-media-placeholder:hover {
  background:rgba(100,180,255,.25);
  color:#a0d0ff
}
.bubble-media-audio {
  display:block;
  max-width:260px;
  height:32px
}
.bubble-media-video {
  max-width:320px;
  max-height:220px;
  border-radius:6px;
  display:block
}
.bubble-media-link {
  color:var(--accent);
  text-decoration:none;
  font-size:13px;
  display:inline-flex;
  align-items:center;
  gap:4px
}
.bubble-media-link:hover {
  text-decoration:underline
}
.bubble-media-text {
  display:block;
  margin-top:4px;
  font-size:13px;
  word-break:break-all;
  word-wrap:break-word;
  white-space:pre-wrap
}
.bubble-at {
  color:#3b82f6;
  font-weight:600;
  background:#3b82f614;
  border-radius:4px;
  padding:0 3px;
}
.bubble-self .bubble-at { color:#dbeafe; background:#ffffff26; }
:deep(.md-code) {
  background:#00000026;
  padding:1px 4px;
  border-radius:3px;
  font-size:12px;
  font-family:monospace
}
:deep(.bubble-self .md-code) {
  background:#fff3
}
:deep(.md-code-block) {
  background:#0000001f;
  padding:6px 8px;
  border-radius:5px;
  font-size:12px;
  font-family:monospace;
  white-space:pre-wrap !important;
  word-break:break-all !important;
  overflow-wrap:anywhere !important;
  margin:4px 0;
  display:block;
  max-width:100%
}
:deep(.bubble-self .md-code-block) {
  background:#ffffff26
}
:deep(.md-link) {
  color:var(--accent);
  text-decoration:underline
}
:deep(.bubble-self .md-link) {
  color:#b3d4ff
}
:deep(.kb-wrap) {
  margin-top:6px;
  display:flex;
  flex-direction:column;
  gap:6px
}
:deep(.kb-row) {
  display:flex;
  gap:6px;
  flex-wrap:wrap
}
:deep(.kb-btn) {
  display:inline-flex;
  align-items:center;
  gap:3px;
  background:var(--accent);
  color:#fff;
  border:1px solid var(--accent);
  border-radius:6px;
  padding:4px 10px;
  font-size:11px;
  font-weight:500;
  cursor:default;
  white-space:nowrap
}
:deep(.kb-btn.kb-t0) {
  background:var(--info);
  border-color:var(--info)
}
:deep(.bubble-self .kb-btn) {
  background:#ffffff30;
  border-color:#ffffff50
}
.bubble-row {
  display:flex;
  align-items:flex-end;
  gap:6px;
  min-width:0;
  max-width:100%
}
.self .bubble-row {
  flex-direction:row-reverse
}
.bubble-actions {
  display:grid;
  grid-template-rows:repeat(2, 17px);
  grid-auto-flow:column;
  grid-auto-columns:max-content;
  gap:2px;
  opacity:0;
  transition:opacity .15s
}
.bubble-row:hover .bubble-actions {
  opacity:1
}
.action-btn {
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:4px;
  color:var(--text2);
  font-size:10px;
  min-width:24px;
  height:17px;
  padding:0 5px;
  cursor:pointer;
  white-space:nowrap;
  line-height:1;
  display:flex;
  align-items:center;
  justify-content:center
}
.action-btn:hover {
  color:var(--accent);
  border-color:var(--accent)
}
.action-btn.recall:hover:not(:disabled) {
  color:var(--danger);
  border-color:var(--danger)
}
.action-btn:disabled {
  opacity:.4;
  cursor:default
}
.recalled-tag {
  display:inline-block;
  background:rgba(255,152,0,.15);
  color:#e65100;
  font-size:11px;
  padding:1px 6px;
  border-radius:3px;
  margin-bottom:4px
}
.audit-reject {
  background:rgba(244,67,54,.15);
  color:#c62828
}
.audit-tag {
  display:inline-block;
  background:rgba(33,150,243,.12);
  color:#1565c0;
  font-size:11px;
  padding:1px 6px;
  border-radius:3px;
  margin-bottom:4px
}
.raw-data-box {
  background:var(--bg2);
  border:1px solid var(--border);
  border-radius:6px;
  padding:8px 10px;
  font-size:11px;
  color:var(--text2);
  margin-top:4px;
  max-height:200px;
  overflow:auto;
  white-space:pre-wrap;
  word-break:break-all
}
.send-area {
  border-top:1px solid var(--border);
  padding:10px 14px;
  flex-shrink:0
}
.quote-preview {
  display:flex;
  align-items:center;
  gap:8px;
  margin-bottom:8px;
  padding:7px 10px;
  border-left:3px solid var(--accent);
  border-radius:6px;
  background:var(--bg3);
  color:var(--text2);
  min-width:0
}
.quote-main {
  flex:1;
  display:flex;
  flex-direction:column;
  gap:2px;
  min-width:0
}
.quote-title {
  color:var(--accent);
  font-size:12px;
  font-weight:600
}
.quote-text {
  overflow:hidden;
  text-overflow:ellipsis;
  white-space:nowrap;
  font-size:12px
}
.quote-clear {
  width:22px;
  height:22px;
  border:1px solid var(--border);
  border-radius:5px;
  background:var(--bg2);
  color:var(--text3);
  cursor:pointer;
  line-height:18px;
  flex-shrink:0
}
.quote-clear:hover {
  color:var(--danger);
  border-color:var(--danger)
}
.send-toolbar {
  display:flex;
  align-items:center;
  gap:8px;
  margin-bottom:6px
}
.send-type-select {
  background:var(--bg3);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:6px;
  padding:3px 8px;
  font-size:12px;
  cursor:pointer;
  outline:none
}
.mobile-type-select {
  display:none
}
.mobile-type-menu {
  display:none
}
.mobile-type-trigger {
  height:100%;
  min-width:48px;
  border:1px solid var(--border);
  border-radius:6px;
  background:var(--bg3);
  color:var(--text);
  font-size:12px;
  cursor:pointer;
  display:flex;
  align-items:center;
  justify-content:center;
  gap:5px
}
.mobile-type-caret {
  width:0;
  height:0;
  border-left:4px solid transparent;
  border-right:4px solid transparent;
  border-bottom:5px solid currentColor;
  opacity:.75
}
.mobile-type-options {
  position:absolute;
  left:0;
  bottom:calc(100% + 6px);
  z-index:20;
  min-width:86px;
  padding:4px;
  border:1px solid var(--border);
  border-radius:8px;
  background:var(--bg2);
  box-shadow:0 10px 28px rgba(0,0,0,.25)
}
.mobile-type-options button {
  width:100%;
  border:0;
  border-radius:5px;
  background:transparent;
  color:var(--text);
  padding:7px 9px;
  text-align:left;
  font-size:12px;
  cursor:pointer
}
.mobile-type-options button:hover,
.mobile-type-options button.active {
  background:var(--accent);
  color:#fff
}
.send-img-label {
  cursor:pointer;
  display:flex;
  align-items:center
}
.send-icon {
  width:20px;
  height:20px;
  color:var(--text2);
  transition:color .15s
}
.send-img-label:hover .send-icon {
  color:var(--accent)
}
.send-img-tag {
  font-size:11px;
  color:var(--accent);
  background:var(--bg3);
  border-radius:4px;
  padding:2px 6px;
  display:flex;
  align-items:center;
  gap:4px
}
.send-img-preview {
  width:24px;
  height:24px;
  border-radius:3px;
  -o-object-fit:cover;
  object-fit:cover;
  flex-shrink:0
}
.send-img-remove {
  cursor:pointer;
  font-size:14px;
  color:var(--text3)
}
.send-img-remove:hover {
  color:var(--danger)
}
.ark-form {
  display:flex;
  flex-direction:column;
  gap:6px;
  margin-top:4px
}
.ark-grid {
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:4px 12px
}
.ark-field {
  display:flex;
  align-items:center;
  gap:4px
}
.ark-field label {
  font-size:10px;
  color:var(--text3);
  min-width:80px;
  flex-shrink:0;
  text-align:right;
  font-family:monospace
}
.ark-field input {
  flex:1;
  min-width:0;
  background:var(--bg3);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:5px;
  padding:4px 6px;
  font-size:12px;
  outline:none;
  transition:border-color .15s
}
.ark-field input:focus {
  border-color:var(--accent)
}
.ark-hint {
  font-size:11px;
  color:var(--text3);
  margin-top:2px
}
.ark-send-btn {
  align-self:flex-end;
  margin-top:4px
}
.send-input-row {
  display:flex;
  gap:8px
}
.send-input {
  flex:1;
  resize:none;
  background:var(--bg3);
  color:var(--text);
  border:1px solid var(--border);
  border-radius:8px;
  padding:8px 10px;
  font-size:13px;
  outline:none;
  font-family:inherit;
  transition:border-color .15s
}
.send-input:focus {
  border-color:var(--accent)
}
.send-btn {
  background:var(--accent);
  color:#fff;
  border:none;
  border-radius:8px;
  padding:0 20px;
  font-size:13px;
  font-weight:600;
  cursor:pointer;
  transition:opacity .15s;
  align-self:flex-end;
  height:36px
}
.send-btn:hover {
  opacity:.85
}
.send-btn:disabled {
  opacity:.4;
  cursor:default
}
.send-hint {
  font-size:11px;
  color:var(--text3);
  margin-top:4px
}
.send-error {
  font-size:12px;
  color:var(--danger);
  margin-top:4px
}
.panel-header-info {
  font-size:11px;
  color:var(--text3);
  font-family:monospace;
  display:flex;
  align-items:center;
  gap:4px
}
.refresh-msgid-btn {
  background:none;
  border:none;
  padding:2px;
  cursor:pointer;
  color:var(--text3);
  display:flex;
  align-items:center;
  border-radius:4px;
  transition:color .15s,background .15s
}
.refresh-msgid-btn:hover {
  color:var(--accent);
  background:var(--bg3)
}
.refresh-msgid-btn svg {
  width:14px;
  height:14px
}
.mobile-back-btn {
  display:flex;
  align-items:center;
  justify-content:center;
  width:28px;
  height:28px;
  border:none;
  background:var(--bg3);
  border-radius:6px;
  color:var(--text);
  cursor:pointer;
  flex-shrink:0;
  transition:background .15s
}
.mobile-back-btn:hover {
  background:var(--border)
}
.mobile-back-btn svg {
  width:18px;
  height:18px
}
@media(max-width:767px) {
  .msg-page {
  height:calc(100vh - 60px)
}
.msg-layout {
  flex-direction:column;
  height:100%
}
.chat-list-panel {
  width:100%;
  max-height:none;
  height:100%;
  flex:1;
  border-radius:10px
}
.chat-list-panel.mobile-hidden {
  display:none
}
.chat-history-panel {
  width:100%;
  height:100%;
  flex:1;
  border-radius:10px
}
.chat-history-panel.mobile-hidden {
  display:none
}
.bubble-main {
  max-width:85%
}
.history-body {
  padding:10px
}
.send-area {
  padding:8px 10px
}
.send-toolbar {
  display:none
}
.send-input-row {
  flex-direction:row;
  align-items:flex-end;
  gap:6px
}
.mobile-type-menu {
  display:block;
  position:relative;
  flex-shrink:0;
  align-self:stretch
}
.send-input {
  flex:1;
  min-width:0
}
.ark-mobile-select {
  display:block;
  position:relative;
  margin-bottom:6px;
  width:54px;
  height:32px
}
.send-btn {
  width:auto;
  height:auto;
  padding:6px 12px;
  font-size:12px;
  flex-shrink:0;
  align-self:stretch
}
.panel-header {
  padding:8px 10px;
  font-size:13px
}
.ark-grid {
  grid-template-columns:1fr
}
.msg-title {
  font-size:16px;
  margin:0 0 8px
}
}
.lightbox-overlay {
  position:fixed;
  top:0;left:0;right:0;bottom:0;
  background:rgba(0,0,0,.75);
  z-index:9999;
  display:flex;
  align-items:center;
  justify-content:center;
  cursor:pointer
}
.lightbox-img {
  max-width:90vw;
  max-height:90vh;
  object-fit:contain;
  border-radius:8px;
  cursor:default
}
.lightbox-close {
  position:fixed;
  top:16px;right:24px;
  color:#fff;
  font-size:36px;
  cursor:pointer;
  line-height:1
}
</style>
