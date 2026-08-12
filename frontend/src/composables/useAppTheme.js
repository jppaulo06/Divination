import { computed } from 'vue'
import { useTheme } from 'vuetify'

import { DARK_THEME, LIGHT_THEME } from '@/plugins/vuetify'

const STORAGE_KEY = 'divination:theme'

/** Theme toggle whose choice survives a reload. */
export function useAppTheme() {
  const theme = useTheme()

  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored === DARK_THEME || stored === LIGHT_THEME) {
    theme.global.name.value = stored
  }

  const isDark = computed(() => theme.global.name.value === DARK_THEME)

  function toggleTheme() {
    const next = isDark.value ? LIGHT_THEME : DARK_THEME
    theme.global.name.value = next
    localStorage.setItem(STORAGE_KEY, next)
  }

  return { isDark, toggleTheme }
}
