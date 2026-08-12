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

export async function changeTemplate(template) {
  const { data } = await client.post('/v1/context', { newTemplate: template })
  return data
}

export { baseURL }
