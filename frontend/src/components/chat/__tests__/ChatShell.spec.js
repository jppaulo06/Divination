import { flushPromises, mount } from '@vue/test-utils'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { h } from 'vue'
import { VApp } from 'vuetify/components'

import ChatShell from '@/components/chat/ChatShell.vue'
import vuetify from '@/plugins/vuetify'
import * as api from '@/services/api'

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    listChats: vi.fn(),
    createChat: vi.fn(),
    askQuestion: vi.fn(),
    changeTemplate: vi.fn(),
  }
})

// Vuetify's layout and overlay components reach for browser APIs that
// jsdom does not implement.
beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.visualViewport = null
  window.matchMedia ??= () => ({
    matches: false,
    addEventListener() {},
    removeEventListener() {},
  })
})

/** v-app-bar and v-navigation-drawer require an injected VApp layout. */
function mountShell() {
  return mount(
    { render: () => h(VApp, () => [h(ChatShell)]) },
    { global: { plugins: [vuetify] } },
  )
}

describe('ChatShell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    api.listChats.mockResolvedValue({})
  })

  it('mounts the whole tree without unresolved components', async () => {
    const wrapper = mountShell()
    await flushPromises()

    expect(wrapper.html()).toContain('Divination')
    // An unregistered component would survive into the output as its own
    // tag name rather than being rendered.
    expect(wrapper.html()).not.toMatch(/<v-[a-z-]+/)
  })

  it('shows the empty state and its suggestions when there is no history', async () => {
    const wrapper = mountShell()
    await flushPromises()

    expect(wrapper.text()).toContain('Consulte o oráculo')
    expect(wrapper.findAll('.empty__suggestion').length).toBeGreaterThan(0)
  })

  it('renders a restored conversation with distinct user and agent turns', async () => {
    api.listChats.mockResolvedValue({
      a: {
        messages: [
          { type: 'human', content: 'O que é vantagem?' },
          { type: 'ai', content: 'Você rola **dois** d20.' },
        ],
      },
    })

    const wrapper = mountShell()
    await flushPromises()

    expect(wrapper.findAll('.message--user')).toHaveLength(1)
    expect(wrapper.findAll('.message--agent')).toHaveLength(1)
    // Assistant markdown is rendered as HTML...
    expect(wrapper.find('.message--agent .markdown').html()).toContain(
      '<strong>dois</strong>',
    )
    expect(wrapper.text()).toContain('O que é vantagem?')
  })

  it('renders a question containing markup as literal text', async () => {
    api.listChats.mockResolvedValue({
      a: { messages: [{ type: 'human', content: '<img src=x onerror=1>' }] },
    })

    const wrapper = mountShell()
    await flushPromises()

    // ...but user input is bound as text, so this must not become an element.
    expect(wrapper.find('.message--user img').exists()).toBe(false)
    expect(wrapper.find('.message--user').text()).toContain('<img src=x')
  })

  it('sends a question and appends the answer', async () => {
    api.createChat.mockResolvedValue('chat-1')
    api.askQuestion.mockResolvedValue({
      answer: 'Resposta fundamentada.',
      interactionId: null,
    })

    const wrapper = mountShell()
    await flushPromises()

    await wrapper.find('textarea').setValue('Como funciona o ataque furtivo?')
    await wrapper.find('.composer__send').trigger('click')
    await flushPromises()

    expect(api.askQuestion).toHaveBeenCalledWith({
      question: 'Como funciona o ataque furtivo?',
      chatId: 'chat-1',
    })
    expect(wrapper.text()).toContain('Resposta fundamentada.')
    // The composer clears itself for the next question.
    expect(wrapper.find('textarea').element.value).toBe('')
  })

  it('keeps the send button disabled until something is typed', async () => {
    const wrapper = mountShell()
    await flushPromises()

    expect(wrapper.find('.composer__send').attributes('disabled')).toBeDefined()

    await wrapper.find('textarea').setValue('pergunta')
    expect(wrapper.find('.composer__send').attributes('disabled')).toBeUndefined()
  })

  it('ships a single dark theme with no toggle', async () => {
    const wrapper = mountShell()
    await flushPromises()

    expect(wrapper.find('.v-theme--divinationDark').exists()).toBe(true)
    expect(wrapper.html()).not.toContain('mdi-white-balance-sunny')
    expect(wrapper.html()).not.toContain('mdi-weather-night')
  })

  it('places the personality control in the composer, not the app bar', async () => {
    const wrapper = mountShell()
    await flushPromises()

    expect(wrapper.find('.composer .personality__activator').exists()).toBe(
      true,
    )
    expect(wrapper.find('.v-app-bar .personality__activator').exists()).toBe(
      false,
    )
    // The app bar keeps only identity and the drawer toggle.
    expect(wrapper.find('.v-app-bar .v-app-bar-nav-icon').exists()).toBe(true)
  })

  it('toggles the conversation drawer', async () => {
    const wrapper = mountShell()
    await flushPromises()

    const toggle = wrapper.find('.v-app-bar-nav-icon')
    expect(toggle.exists()).toBe(true)

    const before = toggle.attributes('aria-expanded')
    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).not.toBe(before)

    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe(before)
  })

  it('lists restored conversations by their opening question', async () => {
    api.listChats.mockResolvedValue({
      a: { messages: [{ type: 'human', content: 'Regras de conjuração' }] },
    })

    const wrapper = mountShell()
    await flushPromises()

    expect(wrapper.find('.sidebar__item-title').text()).toBe(
      'Regras de conjuração',
    )
  })
})
