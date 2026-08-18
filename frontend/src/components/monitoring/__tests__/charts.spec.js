import { describe, expect, it } from 'vitest'
import { mount as baseMount } from '@vue/test-utils'

import vuetify from '@/plugins/vuetify'
import BarList from '../BarList.vue'
import ScoreHistogram from '../ScoreHistogram.vue'

// The charts are plain HTML, but their annotations use v-icon, which
// needs the Vuetify defaults instance injected.
const mount = (component, options = {}) =>
  baseMount(component, {
    ...options,
    global: { plugins: [vuetify], ...(options.global ?? {}) },
  })

const rows = [
  { key: 'weak_retrieval', label: 'Retrieval fraco', value: 5 },
  { key: 'refusal_or_hedge', label: 'Recusa', value: 3 },
  { key: 'user_negative_feedback', label: 'Negativa', value: 2 },
]

describe('BarList', () => {
  it('scales bars against the largest value, not the total', () => {
    const wrapper = mount(BarList, { props: { rows } })
    const widths = wrapper
      .findAll('.bars__fill')
      .map((bar) => bar.attributes('style'))

    expect(widths[0]).toContain('width: 100%')
    expect(widths[1]).toContain('width: 60%')
  })

  it('keeps a nonzero bar visible for a small value', () => {
    const wrapper = mount(BarList, {
      props: { rows: [{ key: 'a', label: 'A', value: 1000 }, { key: 'b', label: 'B', value: 1 }] },
    })

    const smallest = wrapper.findAll('.bars__fill')[1].attributes('style')
    expect(smallest).toContain('width: 1.5%')
  })

  it('shows each value with its share of the total', () => {
    const wrapper = mount(BarList, { props: { rows } })

    expect(wrapper.text()).toContain('50%')
  })

  it('renders an empty state rather than an empty chart', () => {
    const wrapper = mount(BarList, {
      props: { rows: [], emptyText: 'Nada ainda.' },
    })

    expect(wrapper.text()).toContain('Nada ainda.')
    expect(wrapper.find('.bars').exists()).toBe(false)
  })

  it('emits the row key when selectable', async () => {
    const wrapper = mount(BarList, { props: { rows, selectable: true } })
    await wrapper.findAll('.bars__row')[1].trigger('click')

    expect(wrapper.emitted('select')[0]).toEqual(['refusal_or_hedge'])
  })

  it('stays inert when not selectable', async () => {
    const wrapper = mount(BarList, { props: { rows } })
    await wrapper.findAll('.bars__row')[0].trigger('click')

    expect(wrapper.emitted('select')).toBeUndefined()
  })
})

describe('ScoreHistogram', () => {
  // The real spread observed in production: every score well under the
  // 0.7 threshold.
  const bins = [
    { lo: 0.579, hi: 0.604, count: 2 },
    { lo: 0.604, hi: 0.629, count: 1 },
    { lo: 0.629, hi: 0.654, count: 2 },
  ]

  it('keeps the threshold inside the domain even when no score reaches it', () => {
    const wrapper = mount(ScoreHistogram, {
      props: { bins, threshold: 0.7, belowThreshold: 5, count: 5 },
    })

    const marker = wrapper.find('.hist__threshold')
    expect(marker.exists()).toBe(true)

    // Off-scale would render past 100% and disappear; it must land inside.
    const left = Number(marker.attributes('style').match(/left:\s*([\d.]+)%/)[1])
    expect(left).toBeGreaterThan(0)
    expect(left).toBeLessThanOrEqual(100)
  })

  it('calls out a threshold that every score falls below', () => {
    const wrapper = mount(ScoreHistogram, {
      props: { bins, threshold: 0.7, belowThreshold: 5, count: 5 },
    })

    expect(wrapper.text()).toContain('100% do tráfego')
  })

  it('stays quiet when scores straddle the threshold', () => {
    const wrapper = mount(ScoreHistogram, {
      props: { bins, threshold: 0.6, belowThreshold: 2, count: 5 },
    })

    expect(wrapper.text()).not.toContain('100% do tráfego')
  })

  it('gives a single-valued distribution a visible column', () => {
    const wrapper = mount(ScoreHistogram, {
      props: {
        bins: [{ lo: 0.91, hi: 0.91, count: 1 }],
        threshold: 0.7,
        belowThreshold: 0,
        count: 1,
      },
    })

    const style = wrapper.find('.hist__bar').attributes('style')
    expect(style).toMatch(/width:\s*[\d.]+%/)
    expect(style).not.toContain('width: 0%')
  })

  it('renders an empty state with no bins', () => {
    const wrapper = mount(ScoreHistogram, {
      props: { bins: [], threshold: 0.7 },
    })

    expect(wrapper.find('.hist').exists()).toBe(false)
    expect(wrapper.text()).toContain('Nenhum score')
  })
})
