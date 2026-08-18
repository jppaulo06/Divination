<script setup>
import { computed } from 'vue'

const props = defineProps({
  rows: { type: Array, required: true },
  // Set when clicking a row should filter something; omitted makes the
  // chart inert.
  activeKey: { type: String, default: null },
  selectable: { type: Boolean, default: false },
  emptyText: { type: String, default: 'Sem dados ainda.' },
})

const emit = defineEmits(['select'])

const total = computed(() =>
  props.rows.reduce((sum, row) => sum + row.value, 0),
)
const max = computed(() =>
  props.rows.reduce((peak, row) => Math.max(peak, row.value), 0),
)

// One series, so every bar takes the same hue: bar length already encodes
// the magnitude, and colouring each row would spend the identity channel
// re-encoding it.
function widthFor(value) {
  if (!max.value) return '0%'
  return `${Math.max((value / max.value) * 100, 1.5)}%`
}

function shareFor(value) {
  if (!total.value) return ''
  return `${Math.round((value / total.value) * 100)}%`
}
</script>

<template>
  <p v-if="!rows.length" class="bars__empty">{{ emptyText }}</p>

  <ul v-else class="bars">
    <li
      v-for="row in rows"
      :key="row.key"
      class="bars__row"
      :class="{
        'bars__row--selectable': selectable,
        'bars__row--active': activeKey === row.key,
        'bars__row--dimmed': activeKey && activeKey !== row.key,
      }"
      @click="selectable && emit('select', row.key)"
    >
      <span class="bars__label">{{ row.label }}</span>
      <span class="bars__track">
        <span class="bars__fill" :style="{ width: widthFor(row.value) }" />
      </span>
      <span class="bars__value">
        {{ row.value }}
        <span class="bars__share">{{ shareFor(row.value) }}</span>
      </span>
    </li>
  </ul>
</template>

<style scoped>
.bars {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bars__row {
  display: grid;
  grid-template-columns: minmax(120px, 34%) 1fr auto;
  align-items: center;
  gap: 12px;
  border-radius: 8px;
  padding: 2px 4px;
}

.bars__row--selectable {
  cursor: pointer;
}

.bars__row--selectable:hover {
  background: rgba(var(--v-theme-on-surface), 0.05);
}

.bars__row--dimmed {
  opacity: 0.45;
}

.bars__row--active {
  background: rgba(var(--v-theme-on-surface), 0.07);
}

/* Text wears text tokens, never the series colour. */
.bars__label {
  font-size: 0.85rem;
  opacity: 0.86;
  overflow-wrap: anywhere;
}

.bars__track {
  position: relative;
  height: 10px;
  border-radius: 999px;
  background: rgba(var(--v-theme-on-surface), 0.08);
  overflow: hidden;
}

.bars__fill {
  display: block;
  height: 100%;
  /* Rounded data-end only, anchored to the baseline at the left. */
  border-radius: 0 4px 4px 0;
  background: var(--viz-series-1);
  transition: width 0.25s ease;
}

.bars__value {
  font-size: 0.85rem;
  font-variant-numeric: tabular-nums;
  min-width: 62px;
  text-align: right;
}

.bars__share {
  opacity: 0.5;
  margin-left: 6px;
}

.bars__empty {
  margin: 0;
  font-size: 0.85rem;
  opacity: 0.6;
}

@media (max-width: 600px) {
  .bars__row {
    grid-template-columns: 1fr auto;
  }

  .bars__track {
    grid-column: 1 / -1;
    order: 3;
  }
}
</style>
