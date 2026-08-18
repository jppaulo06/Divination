import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useChats } from '@/composables/useChats'
import * as api from '@/services/api'

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    listChats: vi.fn(),
    createChat: vi.fn(),
    askQuestion: vi.fn(),
    sendFeedback: vi.fn(),
  }
})

const humanThenAi = (question, answer) => ({
  messages: [
    { type: 'human', content: question },
    { type: 'ai', content: answer },
  ],
})

describe('useChats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('loadChats', () => {
    it('derives roles from the backend message type, not index parity', async () => {
      api.listChats.mockResolvedValue({
        a: {
          messages: [
            // A conversation whose first stored message is an answer: with
            // index parity this whole transcript would be mislabelled.
            { type: 'ai', content: 'resposta' },
            { type: 'human', content: 'pergunta' },
          ],
        },
      })

      const chat = useChats()
      await chat.loadChats()

      expect(chat.chats.value[0].messages.map((m) => m.role)).toEqual([
        'assistant',
        'user',
      ])
    })

    it('falls back to parity when no type is present', async () => {
      api.listChats.mockResolvedValue({
        a: { messages: [{ content: 'q' }, { content: 'a' }] },
      })

      const chat = useChats()
      await chat.loadChats()

      expect(chat.chats.value[0].messages.map((m) => m.role)).toEqual([
        'user',
        'assistant',
      ])
    })

    it('selects the most recent chat that has messages', async () => {
      api.listChats.mockResolvedValue({
        old: humanThenAi('primeira', 'resposta'),
        recent: humanThenAi('última', 'resposta'),
        empty: { messages: [] },
      })

      const chat = useChats()
      await chat.loadChats()

      expect(chat.currentChatId.value).toBe('recent')
    })

    it('surfaces a message and leaves no chats when the fetch fails', async () => {
      api.listChats.mockRejectedValue(new Error('boom'))

      const chat = useChats()
      await chat.loadChats()

      expect(chat.chats.value).toEqual([])
      expect(chat.error.value).toBeTruthy()
      expect(chat.isLoadingChats.value).toBe(false)
    })

    it('does not create a chat as a side effect of loading', async () => {
      // The previous implementation split this across beforeMount and
      // mounted, so a freshly created chat was overwritten by the list
      // that resolved afterwards.
      api.listChats.mockResolvedValue({})

      const chat = useChats()
      await chat.loadChats()

      expect(api.createChat).not.toHaveBeenCalled()
      expect(chat.currentChatId.value).toBeNull()
    })
  })

  describe('sendMessage', () => {
    it('creates the chat lazily on the first send', async () => {
      api.listChats.mockResolvedValue({})
      api.createChat.mockResolvedValue('new-chat')
      api.askQuestion.mockResolvedValue({
        answer: 'resposta',
        interactionId: 'int-1',
      })

      const chat = useChats()
      await chat.loadChats()
      await chat.sendMessage('Como funciona o ataque furtivo?')

      expect(api.createChat).toHaveBeenCalledTimes(1)
      expect(chat.currentChatId.value).toBe('new-chat')
      expect(chat.messages.value.map((m) => m.role)).toEqual([
        'user',
        'assistant',
      ])
      expect(chat.messages.value[1].interactionId).toBe('int-1')
    })

    it('reuses the selected chat instead of creating another', async () => {
      api.listChats.mockResolvedValue({ a: humanThenAi('q', 'a') })
      api.askQuestion.mockResolvedValue({ answer: 'resposta' })

      const chat = useChats()
      await chat.loadChats()
      await chat.sendMessage('segunda pergunta')

      expect(api.createChat).not.toHaveBeenCalled()
      expect(chat.messages.value).toHaveLength(4)
    })

    it('ignores blank input', async () => {
      const chat = useChats()
      await chat.sendMessage('   ')

      expect(api.createChat).not.toHaveBeenCalled()
      expect(api.askQuestion).not.toHaveBeenCalled()
    })

    it('records a failed turn so the question does not look unanswered', async () => {
      api.listChats.mockResolvedValue({ a: humanThenAi('q', 'a') })
      api.askQuestion.mockRejectedValue(new Error('down'))

      const chat = useChats()
      await chat.loadChats()
      await chat.sendMessage('pergunta que falha')

      const last = chat.messages.value.at(-1)
      expect(last.role).toBe('assistant')
      expect(last.failed).toBe(true)
      expect(chat.error.value).toBeTruthy()
      expect(chat.isSending.value).toBe(false)
    })

    it('does not append a user message when chat creation fails', async () => {
      api.listChats.mockResolvedValue({})
      api.createChat.mockRejectedValue(new Error('no'))

      const chat = useChats()
      await chat.loadChats()
      await chat.sendMessage('pergunta')

      expect(chat.chats.value).toEqual([])
      expect(chat.error.value).toBeTruthy()
    })
  })

  describe('retryLast', () => {
    it('replaces the failed turn with a fresh answer', async () => {
      api.listChats.mockResolvedValue({ a: { messages: [] } })
      api.askQuestion.mockRejectedValueOnce(new Error('down'))
      api.askQuestion.mockResolvedValueOnce({ answer: 'agora foi' })

      const chat = useChats()
      await chat.loadChats()
      chat.selectChat('a')
      await chat.sendMessage('pergunta')
      await chat.retryLast()

      expect(chat.messages.value).toHaveLength(2)
      expect(chat.messages.value[0].content).toBe('pergunta')
      expect(chat.messages.value[1].content).toBe('agora foi')
      expect(chat.messages.value[1].failed).toBeUndefined()
    })

    it('does nothing when the last turn succeeded', async () => {
      api.listChats.mockResolvedValue({ a: humanThenAi('q', 'a') })

      const chat = useChats()
      await chat.loadChats()
      await chat.retryLast()

      expect(api.askQuestion).not.toHaveBeenCalled()
      expect(chat.messages.value).toHaveLength(2)
    })
  })

  describe('restored conversations', () => {
    it('carries the interactionId so old answers stay rateable', async () => {
      api.listChats.mockResolvedValue({
        a: {
          messages: [
            { type: 'human', content: 'pergunta' },
            { type: 'ai', content: 'resposta', interactionId: 'int-9' },
          ],
        },
      })

      const chat = useChats()
      await chat.loadChats()

      expect(chat.messages.value[1].interactionId).toBe('int-9')
    })

    it('leaves answers the backend could not identify unrateable', async () => {
      api.listChats.mockResolvedValue({
        a: {
          messages: [
            { type: 'human', content: 'pergunta' },
            { type: 'ai', content: 'resposta', interactionId: null },
          ],
        },
      })

      const chat = useChats()
      await chat.loadChats()

      expect(chat.messages.value[1].interactionId).toBeNull()
    })

    it('rates an answer restored from history', async () => {
      api.listChats.mockResolvedValue({
        a: {
          messages: [
            { type: 'human', content: 'pergunta' },
            { type: 'ai', content: 'resposta', interactionId: 'int-9' },
          ],
        },
      })
      api.sendFeedback.mockResolvedValue(3)

      const chat = useChats()
      await chat.loadChats()
      await chat.rateMessage(chat.messages.value[1], -1)

      expect(api.sendFeedback).toHaveBeenCalledWith({
        interactionId: 'int-9',
        rating: -1,
      })
    })
  })

  describe('rateMessage', () => {
    async function chatWithAnswer(interactionId = 'int-1') {
      api.listChats.mockResolvedValue({})
      api.createChat.mockResolvedValue('c1')
      api.askQuestion.mockResolvedValue({ answer: 'resposta', interactionId })

      const chat = useChats()
      await chat.loadChats()
      await chat.sendMessage('pergunta')
      return chat
    }

    it('sends the rating and remembers it on the message', async () => {
      api.sendFeedback.mockResolvedValue(7)
      const chat = await chatWithAnswer()
      const answer = chat.messages.value.at(-1)

      await chat.rateMessage(answer, -1)

      expect(api.sendFeedback).toHaveBeenCalledWith({
        interactionId: 'int-1',
        rating: -1,
      })
      expect(answer.rating).toBe(-1)
      expect(answer.isRating).toBe(false)
    })

    it('ignores a second click on the same thumb', async () => {
      api.sendFeedback.mockResolvedValue(1)
      const chat = await chatWithAnswer()
      const answer = chat.messages.value.at(-1)

      await chat.rateMessage(answer, 1)
      await chat.rateMessage(answer, 1)

      expect(api.sendFeedback).toHaveBeenCalledTimes(1)
    })

    it('allows changing the rating, which the backend stores as a new row', async () => {
      api.sendFeedback.mockResolvedValue(1)
      const chat = await chatWithAnswer()
      const answer = chat.messages.value.at(-1)

      await chat.rateMessage(answer, -1)
      await chat.rateMessage(answer, 1)

      expect(api.sendFeedback).toHaveBeenCalledTimes(2)
      expect(answer.rating).toBe(1)
    })

    it('does nothing for an answer with no interactionId', async () => {
      const chat = await chatWithAnswer(null)
      const answer = chat.messages.value.at(-1)

      await chat.rateMessage(answer, -1)

      expect(api.sendFeedback).not.toHaveBeenCalled()
      expect(answer.rating).toBeUndefined()
    })

    it('surfaces a failure instead of pretending the rating was stored', async () => {
      // A rating that fails to store cannot be reconstructed later, so it
      // must not be swallowed the way interaction recording is.
      api.sendFeedback.mockRejectedValue(new Error('down'))
      const chat = await chatWithAnswer()
      const answer = chat.messages.value.at(-1)

      await chat.rateMessage(answer, -1)

      expect(chat.error.value).toBeTruthy()
      expect(answer.rating).toBeUndefined()
      expect(answer.isRating).toBe(false)
    })
  })

  describe('chatTitle', () => {
    it('uses the opening question flattened to plain text', async () => {
      api.listChats.mockResolvedValue({
        a: {
          messages: [
            { type: 'human', content: 'Como funciona o **ataque furtivo**?' },
            { type: 'ai', content: '<p>resposta</p>' },
          ],
        },
      })

      const chat = useChats()
      await chat.loadChats()

      // Previously the sidebar showed messages[1] — the marked-rendered
      // answer — so raw HTML tags leaked into the label.
      expect(chat.chatTitle(chat.chats.value[0])).toBe(
        'Como funciona o ataque furtivo?',
      )
    })

    it('clips long questions', async () => {
      api.listChats.mockResolvedValue({
        a: { messages: [{ type: 'human', content: 'p'.repeat(120) }] },
      })

      const chat = useChats()
      await chat.loadChats()
      const title = chat.chatTitle(chat.chats.value[0])

      expect(title.endsWith('…')).toBe(true)
      expect(title.length).toBeLessThanOrEqual(61)
    })

    it('labels a chat with no question', () => {
      const chat = useChats()
      expect(chat.chatTitle({ id: 'x', messages: [] })).toBe('Chat vazio')
    })
  })
})
