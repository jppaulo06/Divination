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
  const notice = ref('')
  const noticeType = ref('success')

  async function setPersonality(value) {
    if (!value || value === personality.value || isChanging.value) return
    const previous = personality.value
    isChanging.value = true
    try {
      await changeTemplate(value)
      personality.value = value
      localStorage.setItem(STORAGE_KEY, value)
      const chosen = PERSONALITIES.find((item) => item.value === value)
      noticeType.value = 'success'
      notice.value = `Personalidade alterada para ${chosen.label.toLowerCase()}.`
    } catch (failure) {
      // Keep the control showing what the backend actually has.
      personality.value = previous
      noticeType.value = 'error'
      notice.value = toErrorMessage(failure)
    } finally {
      isChanging.value = false
    }
  }

  return { personality, isChanging, notice, noticeType, setPersonality }
}
