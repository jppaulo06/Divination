import { beforeAll, describe, expect, it } from 'vitest'
import { mount as baseMount } from '@vue/test-utils'

import vuetify from '@/plugins/vuetify'
import ReviewSubject from '../ReviewSubject.vue'

beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
})

const mount = (props) =>
  baseMount(ReviewSubject, { props, global: { plugins: [vuetify] } })

/** A three-turn thread whose subject is the turn at `subjectIndex`. */
function item(subjectIndex, extra = {}) {
  const thread = [0, 1, 2].map((turn_index) => ({
    turn_index,
    question: `pergunta ${turn_index}`,
    answer: `resposta ${turn_index}`,
    is_subject: turn_index === subjectIndex,
  }))
  return {
    question: `pergunta ${subjectIndex}`,
    answer: `resposta ${subjectIndex}`,
    turn_index: subjectIndex,
    thread,
    top_score: 0.62,
    latency_ms: 900,
    template_name: 'default',
    corpus_version: 'v1',
    retrieval_context: ['chunk'],
    signals: [{ type: 'weak_retrieval' }],
    ...extra,
  }
}

describe('ReviewSubject history', () => {
  it('shows only turns before the subject', () => {
    const wrapper = mount({ item: item(2) })
    const turns = wrapper.findAll('.subject__turn')

    expect(turns).toHaveLength(2)
    expect(turns[0].text()).toContain('pergunta 0')
    expect(turns[1].text()).toContain('pergunta 1')
  })

  it('never shows turns that came after the subject', () => {
    // Filtering on !is_subject used to include later turns, which leaks
    // that the user re-asked — the signal the blinding is meant to hide.
    const wrapper = mount({ item: item(0) })

    expect(wrapper.find('.subject__history').exists()).toBe(false)
    expect(wrapper.findAll('.subject__turn')).toHaveLength(0)
    expect(wrapper.text()).not.toContain('pergunta 1')
    expect(wrapper.text()).not.toContain('pergunta 2')
  })

  it('renders history inline, not behind an accordion', () => {
    const wrapper = mount({ item: item(2) })
    const history = wrapper.find('.subject__history')

    expect(history.exists()).toBe(true)
    // Retrieval chunks stay collapsed; history must not be.
    expect(history.element.closest('.v-expansion-panel')).toBeNull()
    expect(wrapper.find('.subject__label').text()).toBe('Turno em avaliação')
  })

  it('pluralises the turn count', () => {
    expect(mount({ item: item(1) }).find('.subject__history-title').text()).toContain(
      '1 turno anterior',
    )
    expect(mount({ item: item(2) }).find('.subject__history-title').text()).toContain(
      '2 turnos anteriores',
    )
  })

  it('omits the history block for a single-turn conversation', () => {
    const single = item(0)
    single.thread = [single.thread[0]]
    const wrapper = mount({ item: single })

    expect(wrapper.find('.subject__history').exists()).toBe(false)
    expect(wrapper.find('.subject__label').exists()).toBe(false)
    expect(wrapper.text()).toContain('pergunta 0')
  })

  it('keeps signals hidden until revealed', () => {
    const wrapper = mount({ item: item(2), signalsRevealed: false })
    expect(wrapper.text()).toContain('Revelar sinais (1)')
  })
})
