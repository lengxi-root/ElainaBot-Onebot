function parseJsonObject(value) {
  if (!value) return null
  if (typeof value === 'object') return value
  if (typeof value !== 'string' || !value.trim().startsWith('{')) return null
  try { return JSON.parse(value) } catch { return null }
}

function listify(value) {
  if (!value) return []
  return Array.isArray(value) ? value : [value]
}

function readExtValue(ext, keys) {
  for (const item of listify(ext)) {
    if (typeof item !== 'string') continue
    const query = item.includes('?') ? item.slice(item.indexOf('?') + 1) : item
    const params = new URLSearchParams(query)
    for (const key of keys) {
      const value = params.get(key)
      if (value) return value
    }
  }
  return ''
}

function findQuotedElement(elements, referenceId) {
  if (!Array.isArray(elements) || !elements.length) return null
  return elements.find(e => e?.msg_idx && e.msg_idx === referenceId) || elements[0]
}

function quoteFromElement(element, referenceId) {
  if (!element && !referenceId) return null
  const author = element?.author || {}
  return {
    id: referenceId || element?.msg_idx || '',
    author: author.username || author.id || (author.bot ? 'Bot' : '引用消息'),
    text: String(element?.content || '').replace(/\s+/g, ' ').trim(),
  }
}

function extractIncomingQuote(payload) {
  const data = payload?.d || payload
  if (!data || typeof data !== 'object') return null
  const scene = data.message_scene || {}
  const referenceId = readExtValue(scene.ext, ['ref_msg_idx', 'ref_msg_id', 'reference_id', 'message_reference_id'])
  const element = findQuotedElement(data.msg_elements, referenceId)
  if (!referenceId && !element) return null
  return quoteFromElement(element, referenceId)
}

function extractPayloadQuote(payload) {
  if (!payload || typeof payload !== 'object') return null
  const ref = payload.message_reference || {}
  const referenceId = ref.message_id || payload.message_reference_id || payload.reference_message_id || ''
  if (!referenceId) return null
  return { id: String(referenceId), author: '', text: '' }
}

export function parseMessageReference(message) {
  const raw = parseJsonObject(message?.raw_message)
  return extractIncomingQuote(raw) || extractPayloadQuote(raw)
}
