import axios from 'axios'

const baseURL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

// Retrieval + LLM round trips are slow; the default (no timeout) would
// hang forever on a dead backend, and a short one would kill good answers.
const client = axios.create({
  baseURL,
  timeout: 120_000,
  headers: { 'Content-Type': 'application/json' },
})

/**
 * Turns an axios rejection into a message worth showing a user.
 * The backend replies in camelCase (pydantic `to_camel` aliases), so
 * request bodies are sent under those alias names too.
 */
export function toErrorMessage(error) {
  if (error?.code === 'ECONNABORTED') {
    return 'A consulta demorou demais para responder. Tente novamente.'
  }
  if (error?.response) {
    const detail = error.response.data?.detail
    if (typeof detail === 'string') return detail
    return `O servidor respondeu com erro ${error.response.status}.`
  }
  if (error?.request) {
    return `Não foi possível falar com o servidor em ${baseURL}.`
  }
  return error?.message || 'Erro inesperado.'
}

export async function listChats() {
  const { data } = await client.get('/v1/chats')
  return data?.projectHistory ?? {}
}

export async function createChat() {
  const { data } = await client.post('/v1/chats', {})
  return data.chatId
}

export async function askQuestion({ question, chatId }) {
  const { data } = await client.post('/v1/answer', {
    userQuestion: question,
    chatId,
  })
  return {
    answer: data.projectAnswer,
    // Present once the backend monitoring layer is enabled; carried so a
    // rating control can be attached to this specific answer later.
    interactionId: data.interactionId ?? null,
  }
}

/**
 * Rates one answer. `rating` is -1 (thumb down) or +1 (thumb up).
 *
 * Unlike the other calls this one must not be fire-and-forget: a rating
 * that fails to store cannot be reconstructed later, so the rejection is
 * left to the caller to surface.
 */
export async function sendFeedback({ interactionId, rating, comment = null }) {
  const { data } = await client.post('/v1/feedback', {
    interactionId,
    rating,
    comment,
  })
  return data.feedbackId
}

export async function fetchMonitoringSummary() {
  const { data } = await client.get('/v1/monitoring/summary')
  return data
}

export async function fetchCandidates({ limit = 25, signalType = null } = {}) {
  const params = { limit }
  if (signalType) params.signal_type = signalType
  const { data } = await client.get('/v1/monitoring/candidates', { params })
  return data
}

export async function fetchCurationSample({
  size = 20,
  flaggedShare = 0.5,
} = {}) {
  const { data } = await client.get('/v1/curation/sample', {
    params: { size, flagged_share: flaggedShare },
  })
  return data
}

export async function submitReview({
  interactionId,
  verdict,
  rationale = null,
}) {
  const { data } = await client.post('/v1/curation/reviews', {
    interactionId,
    verdict,
    rationale,
  })
  return data.reviewId
}

export async function fetchCurationStats() {
  const { data } = await client.get('/v1/curation/stats')
  return data
}

export async function changeTemplate(template) {
  const { data } = await client.post('/v1/context', { newTemplate: template })
  return data
}

export { baseURL }
