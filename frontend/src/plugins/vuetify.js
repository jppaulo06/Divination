import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'

import { createVuetify } from 'vuetify'
import { aliases, mdi } from 'vuetify/iconsets/mdi'

const DARK_THEME = 'divinationDark'

/**
 * The app ships a single dark palette by design — there is no light
 * counterpart and no toggle. Components read these through the generated
 * --v-theme-* custom properties rather than hardcoding colour, so a
 * second theme could be reintroduced here without touching them.
 *
 * Dark "arcane manuscript" palette: violet-ink surfaces lit by gold.
 * Surfaces climb in luminance as they come forward (background ->
 * surface -> surface-bright) so elevation reads without heavy shadows.
 */
const divinationDark = {
  dark: true,
  colors: {
    background: '#0D0916',
    surface: '#161022',
    'surface-bright': '#241A33',
    'surface-light': '#1E1729',
    'surface-variant': '#2A1F3C',
    'on-surface-variant': '#CFC4DF',
    primary: '#D8B34A',
    'primary-darken-1': '#B4902C',
    secondary: '#9B6DFF',
    'secondary-darken-1': '#7A45F0',
    error: '#F2645A',
    info: '#63B4D9',
    success: '#5FAE7C',
    warning: '#E0A458',
  },
  variables: {
    'border-color': '#D8B34A',
    'border-opacity': 0.14,
    'high-emphasis-opacity': 0.96,
    'medium-emphasis-opacity': 0.72,
    'theme-kbd': '#241A33',
    'theme-on-kbd': '#F3EEE3',
  },
}

export default createVuetify({
  icons: {
    defaultSet: 'mdi',
    aliases,
    sets: { mdi },
  },
  theme: {
    defaultTheme: DARK_THEME,
    themes: {
      [DARK_THEME]: divinationDark,
    },
  },
  // Component-wide defaults keep radii and weights consistent without
  // repeating the same props on every call site.
  defaults: {
    VBtn: {
      rounded: 'lg',
      variant: 'flat',
      class: 'text-none font-weight-medium',
    },
    VTextarea: {
      variant: 'solo-filled',
      rounded: 'lg',
      hideDetails: true,
      flat: true,
    },
    VCard: { rounded: 'lg' },
    VList: { density: 'comfortable' },
  },
})
