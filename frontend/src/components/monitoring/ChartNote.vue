<script setup>
import { ref } from 'vue'

defineProps({
  label: { type: String, default: 'Como ler' },
})

// Collapsed by default: the panel has to stay scannable for someone who
// already knows the chart, and readable for someone who does not.
const open = ref(false)
</script>

<template>
  <div class="note">
    <button
      type="button"
      class="note__toggle"
      :aria-expanded="open"
      @click="open = !open"
    >
      <v-icon
        :icon="open ? 'mdi-chevron-up' : 'mdi-help-circle-outline'"
        size="14"
      />
      {{ open ? 'Fechar' : label }}
    </button>

    <div v-if="open" class="note__body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.note {
  margin-bottom: 14px;
}

.note__toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px 2px 4px;
  border-radius: 999px;
  font-size: 0.72rem;
  color: inherit;
  opacity: 0.6;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.note__toggle:hover,
.note__toggle:focus-visible {
  opacity: 1;
  background: rgba(var(--v-theme-on-surface), 0.07);
}

.note__body {
  margin-top: 8px;
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.05);
  border: 1px solid rgba(var(--v-border-color), 0.4);
  font-size: 0.79rem;
  line-height: 1.55;
}

.note__body :deep(p) {
  margin: 0 0 8px;
}

.note__body :deep(p:last-child) {
  margin-bottom: 0;
}

.note__body :deep(dl) {
  margin: 0;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 4px 10px;
}

.note__body :deep(dt) {
  font-weight: 600;
  white-space: nowrap;
}

.note__body :deep(dd) {
  margin: 0;
  opacity: 0.85;
}

.note__body :deep(.note__warn) {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(var(--v-border-color), 0.4);
  opacity: 0.9;
}
</style>
