<script setup>
import { computed } from 'vue'

import { PERSONALITIES } from '@/composables/usePersonality'

const props = defineProps({
  personality: { type: String, required: true },
  isChanging: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['change'])

const active = computed(
  () =>
    PERSONALITIES.find((item) => item.value === props.personality) ??
    PERSONALITIES[0],
)
</script>

<template>
  <v-menu location="bottom end">
    <template #activator="{ props: menuProps }">
      <v-btn
        v-bind="menuProps"
        :loading="isChanging"
        :icon="compact"
        variant="outlined"
        color="primary"
        :aria-label="compact ? 'Escolher personalidade' : undefined"
      >
        <v-icon v-if="compact" :icon="active.icon" />
        <template v-else>
          <v-icon :icon="active.icon" start size="18" />
          {{ active.label }}
          <v-icon icon="mdi-chevron-down" end size="18" />
        </template>
      </v-btn>
    </template>

    <v-list width="280" density="comfortable">
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
        <v-list-item-subtitle class="text-wrap">
          {{ item.hint }}
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>
  </v-menu>
</template>
