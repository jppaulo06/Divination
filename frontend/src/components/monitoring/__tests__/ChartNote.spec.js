import { describe, expect, it } from 'vitest'
import { mount as baseMount } from '@vue/test-utils'

import vuetify from '@/plugins/vuetify'
import ChartNote from '../ChartNote.vue'

const mount = (options = {}) =>
  baseMount(ChartNote, { global: { plugins: [vuetify] }, ...options })

describe('ChartNote', () => {
  it('starts collapsed so the panel stays scannable', () => {
    const wrapper = mount({ slots: { default: '<p>como ler</p>' } })

    expect(wrapper.find('.note__body').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('como ler')
  })

  it('reveals the explanation on click', async () => {
    const wrapper = mount({ slots: { default: '<p>como ler</p>' } })

    await wrapper.find('.note__toggle').trigger('click')

    expect(wrapper.find('.note__body').text()).toBe('como ler')
  })

  it('collapses again', async () => {
    const wrapper = mount({ slots: { default: '<p>x</p>' } })
    const toggle = wrapper.find('.note__toggle')

    await toggle.trigger('click')
    await toggle.trigger('click')

    expect(wrapper.find('.note__body').exists()).toBe(false)
  })

  it('announces its state to assistive tech', async () => {
    const wrapper = mount({ slots: { default: '<p>x</p>' } })
    const toggle = wrapper.find('.note__toggle')

    expect(toggle.attributes('aria-expanded')).toBe('false')
    await toggle.trigger('click')
    expect(toggle.attributes('aria-expanded')).toBe('true')
  })

  it('uses a button, so it is reachable by keyboard', () => {
    const toggle = mount({ slots: { default: '<p>x</p>' } }).find(
      '.note__toggle',
    )

    expect(toggle.element.tagName).toBe('BUTTON')
    expect(toggle.attributes('type')).toBe('button')
  })

  it('takes a custom label', () => {
    const wrapper = mount({
      props: { label: 'O que é isto?' },
      slots: { default: '<p>x</p>' },
    })

    expect(wrapper.text()).toContain('O que é isto?')
  })
})
