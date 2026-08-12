import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'

import { createVuetify } from 'vuetify'
import { aliases, mdi } from 'vuetify/iconsets/mdi'

export const DARK_THEME = 'divinationDark'
export const LIGHT_THEME = 'divinationLight'

/**
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

/** Daylight counterpart: aged parchment rather than plain white. */
const divinationLight = {
  dark: false,
  colors: {
    background: '#F3EDE1',
    surface: '#FDFAF3',
    'surface-bright': '#FFFFFF',
    'surface-light': '#F8F3E8',
    'surface-variant': '#E7DECA',
    'on-surface-variant': '#4A4033',
    primary: '#8A6A16',
    'primary-darken-1': '#6B5210',
    secondary: '#6338D6',
    'secondary-darken-1': '#4E27B4',
    error: '#C4362C',
    info: '#2A6F8E',
    success: '#3B7A52',
    warning: '#A5701F',
  },
  variables: {
    'border-color': '#6B5210',
    'border-opacity': 0.18,
    'high-emphasis-opacity': 0.92,
    'medium-emphasis-opacity': 0.68,
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
      [LIGHT_THEME]: divinationLight,
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
    VTooltip: { location: 'bottom' },
  },
})
