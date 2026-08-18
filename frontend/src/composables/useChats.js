import { computed, ref } from 'vue'

import {
  askQuestion,
  createChat,
  listChats,
  sendFeedback,
  toErrorMessage,
} from '@/services/api'
import { toPlainText } from '@/utils/markdown'

let nextLocalId = 0
const localId = () => `m${(nextLocalId += 1)}`

/**
 * Maps a persisted langchain message onto a UI message.
 *
 * The backend serialises HumanMessage/AIMessage with a `type` field
 * ("human"/"ai"), which is authoritative. Index parity is only a fallback
 * for older payloads: parity desynchronises permanently the moment a
 * single turn is missing, which silently mislabels every later message.
 *
 * `interactionId` is present on answers the monitoring layer recorded, so
 * a restored conversation can still be rated. It is absent when
 * monitoring is off, or when the answer predates it.
 */
function toUiMessage(raw, index) {
  const type = raw?.type
  let role
  if (type === 'human') role = 'user'
  else if (type === 'ai') role = 'assistant'
  else role = index % 2 === 0 ? 'user' : 'assistant'

  return {
    id: localId(),
    role,
    content: raw?.content ?? '',
    interactionId: raw?.interactionId ?? null,
  }
}

export function useChats() {
  const chats = ref([])
  const currentChatId = ref(null)
  const isLoadingChats = ref(false)
  const isSending = ref(false)
  const error = ref('')

  const currentChat = computed(
    () => chats.value.find((chat) => chat.id === currentChatId.value) ?? null,
  )
  const messages = computed(() => currentChat.value?.messages ?? [])
  const hasConversation = computed(() => messages.value.length > 0)

  /** Sidebar label: the opening question, flattened and clipped. */
  function chatTitle(chat) {
    const opener = chat.messages.find((message) => message.role === 'user')
    if (!opener) return 'Chat vazio'
    const text = toPlainText(opener.content)
    return text.length > 60 ? `${text.slice(0, 60).trimEnd()}…` : text
  }

  async function loadChats() {
    isLoadingChats.value = true
    error.value = ''
    try {
      const history = await listChats()
      chats.value = Object.entries(history).map(([id, chat]) => ({
        id,
        messages: (chat?.messages ?? []).map(toUiMessage),
      }))
      // Land on the most recent conversation that actually has content;
      // an empty one would look identical to the draft state anyway.
      const restorable = [...chats.value]
        .reverse()
        .find((chat) => chat.messages.length > 0)
      currentChatId.value = restorable?.id ?? null
    } catch (failure) {
      error.value = toErrorMessage(failure)
      chats.value = []
    } finally {
      isLoadingChats.value = false
    }
  }

  /**
   * Enters the draft state rather than allocating a chat immediately.
   * The backend row is created on first send, so reloading the page or
   * clicking "novo chat" repeatedly cannot litter the sidebar with empty
   * conversations.
   */
  function startDraft() {
    currentChatId.value = null
    error.value = ''
  }

  function selectChat(id) {
    currentChatId.value = id
    error.value = ''
  }

  async function sendMessage(text) {
    const question = text.trim()
    if (!question || isSending.value) return

    error.value = ''
    let chat = currentChat.value

    if (!chat) {
      try {
        const id = await createChat()
        chat = { id, messages: [] }
        chats.value.push(chat)
        currentChatId.value = id
      } catch (failure) {
        error.value = toErrorMessage(failure)
        return
      }
    }

    chat.messages.push({ id: localId(), role: 'user', content: question })
    isSending.value = true
    try {
      const { answer, interactionId } = await askQuestion({
        question,
        chatId: chat.id,
      })
      chat.messages.push({
        id: localId(),
        role: 'assistant',
        content: answer,
        interactionId,
      })
    } catch (failure) {
      const message = toErrorMessage(failure)
      error.value = message
      // Rendered in place as a failed turn so the transcript still shows
      // what happened, instead of a question that appears unanswered.
      chat.messages.push({
        id: localId(),
        role: 'assistant',
        content: message,
        failed: true,
      })
    } finally {
      isSending.value = false
    }
  }

  /**
   * Rates one answer, remembering the choice on the message.
   *
   * Changing an existing rating is allowed — the backend stores feedback
   * append-only, so a flip records a second row rather than editing the
   * first. Clicking the same thumb twice is ignored, so a stray double
   * click does not post twice.
   *
   * Failures surface as an error: a lost rating is unrecoverable, unlike
   * every other monitoring signal.
   */
  async function rateMessage(message, rating) {
    if (!message?.interactionId) return
    if (message.rating === rating || message.isRating) return

    message.isRating = true
    try {
      await sendFeedback({ interactionId: message.interactionId, rating })
      message.rating = rating
    } catch (failure) {
      error.value = toErrorMessage(failure)
    } finally {
      message.isRating = false
    }
  }

  /** Drops the failed turn and its question, then asks again. */
  async function retryLast() {
    const chat = currentChat.value
    if (!chat || isSending.value) return
    const last = chat.messages.at(-1)
    if (!last?.failed) return

    chat.messages.pop()
    const question = chat.messages.at(-1)
    if (question?.role !== 'user') return
    chat.messages.pop()
    await sendMessage(question.content)
  }

  return {
    chats,
    currentChatId,
    currentChat,
    messages,
    hasConversation,
    isLoadingChats,
    isSending,
    error,
    chatTitle,
    loadChats,
    startDraft,
    selectChat,
    sendMessage,
    rateMessage,
    retryLast,
  }
}
