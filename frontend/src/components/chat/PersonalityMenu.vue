<script setup>
import { computed } from 'vue'

import { PERSONALITIES } from '@/composables/usePersonality'

const props = defineProps({
  personality: { type: String, required: true },
  isChanging: { type: Boolean, default: false },
  /** Icon-only, for sitting inline in the composer row. */
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['change'])

const active = computed(
  () =>
    PERSONALITIES.find((item) => item.value === props.personality) ??
    PERSONALITIES[0],
)

// Not shown visually — the button is icon-only, so this is what assistive
// technology announces. POST /v1/context changes server-side state for
// every chat, so it names the mode currently in effect rather than the
// action.
const label = computed(() => `Personalidade: ${active.value.label}`)

// The activator keeps a constant "adjust" icon instead of mirroring the
// active mode: as a settings control it should signal that something is
// configurable, and a shield read as security instead. The per-mode icons
// stay in the menu, where each one sits beside its own label.
const ACTIVATOR_ICON = 'mdi-tune-variant'
</script>

<template>
  <v-menu location="top start">
    <template #activator="{ props: menuProps }">
      <v-btn
        v-bind="menuProps"
        :loading="isChanging"
        :icon="compact"
        :variant="compact ? 'text' : 'outlined'"
        :aria-label="label"
        color="primary"
        class="personality__activator"
      >
        <v-icon v-if="compact" :icon="ACTIVATOR_ICON" />
        <template v-else>
          <v-icon :icon="ACTIVATOR_ICON" start size="18" />
          {{ active.label }}
          <v-icon icon="mdi-chevron-down" end size="18" />
        </template>
      </v-btn>
    </template>

    <v-list width="320" density="comfortable" class="personality">
      <v-list-subheader>Personalidade do oráculo</v-list-subheader>
      <v-list-item
        v-for="item in PERSONALITIES"
        :key="item.value"
        :active="item.value === personality"
        @click="emit('change', item.value)"
      >
        <template #prepend>
          <v-icon :icon="item.icon" size="20" />
        </template>
        <v-list-item-title>{{ item.label }}</v-list-item-title>
        <v-list-item-subtitle>
          {{ item.hint }}
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>
  </v-menu>
</template>

<style scoped>
/*
 * Vuetify clamps subtitles to a single line with -webkit-line-clamp and
 * display: -webkit-box, which cut these descriptions off mid-word.
 */
.personality :deep(.v-list-item-subtitle) {
  display: block;
  -webkit-line-clamp: unset;
  overflow: visible;
  text-overflow: clip;
  white-space: normal;
  font-size: 0.78rem;
  line-height: 1.4;
  margin-top: 3px;
}

.personality :deep(.v-list-item) {
  padding-top: 8px;
  padding-bottom: 8px;
}
</style>
