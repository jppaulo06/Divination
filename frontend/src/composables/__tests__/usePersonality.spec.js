import { beforeEach, describe, expect, it, vi } from 'vitest'

import { usePersonality } from '@/composables/usePersonality'
import * as api from '@/services/api'

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, changeTemplate: vi.fn() }
})

describe('usePersonality', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('defaults to the restrictive template', () => {
    expect(usePersonality().personality.value).toBe('default')
  })

  it('restores a persisted choice', () => {
    localStorage.setItem('divination:personality', 'creative')
    expect(usePersonality().personality.value).toBe('creative')
  })

  it('ignores an unrecognised persisted value', () => {
    localStorage.setItem('divination:personality', 'nonsense')
    expect(usePersonality().personality.value).toBe('default')
  })

  it('switches template and stays silent on success', async () => {
    api.changeTemplate.mockResolvedValue('creative')

    const p = usePersonality()
    await p.setPersonality('creative')

    expect(api.changeTemplate).toHaveBeenCalledWith('creative')
    expect(p.personality.value).toBe('creative')
    expect(localStorage.getItem('divination:personality')).toBe('creative')
    // No success message: the menu's checked state already conveys it.
    expect(p.error.value).toBe('')
    expect(p.isChanging.value).toBe(false)
  })

  it('reverts and reports when the backend rejects the change', async () => {
    api.changeTemplate.mockRejectedValue(new Error('down'))

    const p = usePersonality()
    await p.setPersonality('creative')

    // The control must not claim a personality the backend never took.
    expect(p.personality.value).toBe('default')
    expect(p.error.value).toBeTruthy()
    expect(localStorage.getItem('divination:personality')).toBeNull()
    expect(p.isChanging.value).toBe(false)
  })

  it('does not re-send the personality already in effect', async () => {
    const p = usePersonality()
    await p.setPersonality('default')

    expect(api.changeTemplate).not.toHaveBeenCalled()
  })
})
