import { ref } from 'vue'

import { changeTemplate, toErrorMessage } from '@/services/api'

const STORAGE_KEY = 'divination:personality'

// Mirrors the template names accepted by POST /v1/context.
export const PERSONALITIES = [
  {
    value: 'default',
    label: 'Restritiva',
    icon: 'mdi-shield-check-outline',
    hint: 'Responde apenas com base nas regras recuperadas.',
  },
  {
    value: 'creative',
    label: 'Criativa',
    icon: 'mdi-auto-fix',
    hint: 'Usa as regras como base, com liberdade narrativa.',
  },
]

export function usePersonality() {
  const stored = localStorage.getItem(STORAGE_KEY)
  const initial = PERSONALITIES.some((item) => item.value === stored)
    ? stored
    : 'default'

  const personality = ref(initial)
  const isChanging = ref(false)
  const error = ref('')

  async function setPersonality(value) {
    if (!value || value === personality.value || isChanging.value) return
    const previous = personality.value
    isChanging.value = true
    error.value = ''
    try {
      await changeTemplate(value)
      personality.value = value
      localStorage.setItem(STORAGE_KEY, value)
      // Success is deliberately silent: the menu's own checked state and
      // the button label already show which personality is live.
    } catch (failure) {
      // A failure has to be reported, or the control would keep showing a
      // personality the backend never accepted.
      personality.value = previous
      error.value = toErrorMessage(failure)
    } finally {
      isChanging.value = false
    }
  }

  return { personality, isChanging, error, setPersonality }
}
