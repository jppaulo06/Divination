<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], required: true },
  hint: { type: String, default: '' },
  icon: { type: String, default: '' },
})
</script>

<template>
  <v-card class="tile" flat>
    <div class="tile__head">
      <v-icon v-if="icon" :icon="icon" size="16" class="tile__icon" />
      <span class="tile__label">{{ label }}</span>
    </div>
    <div class="tile__value">{{ value }}</div>
    <div v-if="hint" class="tile__hint">{{ hint }}</div>
  </v-card>
</template>

<style scoped>
.tile {
  background: rgb(var(--v-theme-surface-light));
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  padding: 16px 18px;
  height: 100%;
}

.tile__head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}

.tile__icon {
  opacity: 0.6;
}

.tile__label {
  font-size: 0.72rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  opacity: 0.62;
}

/* Hero number: the tile's whole job, so it carries the weight. */
.tile__value {
  font-family: var(--divination-font-display, inherit);
  font-size: 2rem;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.tile__hint {
  margin-top: 6px;
  font-size: 0.78rem;
  opacity: 0.58;
}
</style>
