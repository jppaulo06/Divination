<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  bins: { type: Array, required: true },
  threshold: { type: Number, default: null },
  belowThreshold: { type: Number, default: 0 },
  count: { type: Number, default: 0 },
})

const hasBins = computed(() => props.bins.length > 0)

// A zero-count bin has nothing to draw; min-height would otherwise render
// it as a stub that reads as a real observation.
const filledBins = computed(() => props.bins.filter(bin => bin.count > 0))

/**
 * The domain always includes the threshold, even when no score reaches
 * it. That is the point of the chart: if every bar sits to the left of
 * the marker, the detector is firing on all traffic and the threshold is
 * telling you nothing.
 */
const domain = computed(() => {
  if (!hasBins.value) return { min: 0, max: 1, span: 1 }

  const lows = props.bins.map(bin => bin.lo)
  const highs = props.bins.map(bin => bin.hi)
  let min = Math.min(...lows)
  let max = Math.max(...highs)

  if (props.threshold !== null) {
    min = Math.min(min, props.threshold)
    max = Math.max(max, props.threshold)
  }

  const padding = (max - min || 0.02) * 0.06
  min -= padding
  max += padding
  return { min, max, span: max - min }
})

const peak = computed(() =>
  props.bins.reduce((highest, bin) => Math.max(highest, bin.count), 0),
)

//: Headroom above the tallest bar so its count label has somewhere to sit.
const MAX_BAR_HEIGHT = 86

function column(bin) {
  const { min, span } = domain.value
  const left = ((bin.lo - min) / span) * 100
  // A single-valued distribution collapses to zero width; give it a
  // visible column instead of an invisible sliver.
  const width = Math.max(((bin.hi - bin.lo) / span) * 100, 4)
  return { left: `${left}%`, width: `${width}%` }
}

function barHeight(bin) {
  if (!peak.value) return '0%'
  return `${(bin.count / peak.value) * MAX_BAR_HEIGHT}%`
}

const hovered = ref(null)

/**
 * Which side the hover readout aligns to.
 *
 * Centred by default, but pinned inward at the extremes: a readout
 * centred on the first or last column overflows the panel, the same way
 * the threshold label did.
 */
function readoutAlignment(bin) {
  const { min, span } = domain.value
  const centre = ((bin.lo + bin.hi) / 2 - min) / span
  if (centre < 0.15) return 'start'
  if (centre > 0.85) return 'end'
  return 'centre'
}

const thresholdOffset = computed(() => {
  if (props.threshold === null) return null
  const { min, span } = domain.value
  return ((props.threshold - min) / span) * 100
})

const thresholdLeft = computed(() =>
  thresholdOffset.value === null ? null : `${thresholdOffset.value}%`,
)

// Past two thirds of the width the label would overflow the panel, so it
// flips to the inner side of the line.
const labelFlipped = computed(
  () => thresholdOffset.value !== null && thresholdOffset.value > 66,
)

const allBelow = computed(
  () => props.count > 0 && props.belowThreshold === props.count,
)

const format = value => value.toFixed(3)
</script>

<template>
  <p v-if="!hasBins" class="hist__empty">
    Nenhum score de retrieval registrado ainda.
  </p>

  <div v-else class="hist">
    <div class="hist__plot">
      <!--
        The whole column is the hit target, not just the bar: a short bar
        is a few pixels tall and would be near-impossible to hover.
      -->
      <div
        v-for="(bin, index) in filledBins"
        :key="index"
        class="hist__col"
        :class="{ 'hist__col--active': hovered === index }"
        :style="column(bin)"
        @mouseenter="hovered = index"
        @mouseleave="hovered = null"
      >
        <span class="hist__count">{{ bin.count }}</span>
        <span class="hist__bar" :style="{ height: barHeight(bin) }" />

        <!-- Own element rather than a title attribute, which the browser
             delays by about a second before showing. -->
        <span
          v-if="hovered === index"
          class="hist__readout"
          :class="`hist__readout--${readoutAlignment(bin)}`"
        >
          {{ format(bin.lo) }}–{{ format(bin.hi) }}
          <strong>{{ bin.count }}</strong>
          {{ bin.count === 1 ? 'interação' : 'interações' }}
        </span>
      </div>

      <div
        v-if="thresholdLeft"
        class="hist__threshold"
        :style="{ left: thresholdLeft }"
      >
        <span
          class="hist__threshold-label"
          :class="{ 'hist__threshold-label--flipped': labelFlipped }"
        >
          limiar {{ threshold }}
        </span>
      </div>
    </div>

    <div class="hist__axis">
      <span>{{ format(domain.min) }}</span>
      <span>score do melhor chunk</span>
      <span>{{ format(domain.max) }}</span>
    </div>

    <p v-if="allBelow" class="hist__note">
      <v-icon icon="mdi-alert-outline" size="14" />
      Todos os {{ count }} scores estão abaixo do limiar, então
      <code>weak_retrieval</code> dispara em 100% do tráfego — é uma constante,
      não um sinal.
    </p>
  </div>
</template>

<style scoped>
.hist__plot {
  position: relative;
  /* Tall enough that a full-column-width chart keeps a readable aspect
     ratio instead of flattening into a wide sliver. */
  height: var(--hist-height, 240px);
  border-bottom: 1px solid rgba(var(--v-border-color), 0.35);
  /* The hover readout sits above its column, so nothing here may clip. */
  overflow: visible;
}

.hist__col {
  position: absolute;
  top: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  align-items: stretch;
  /* 2px surface gap between neighbouring fills. */
  box-sizing: border-box;
  border-inline: 1px solid transparent;
}

.hist__bar {
  min-height: 2px;
  border-radius: 4px 4px 0 0;
  background: var(--viz-series-1);
  transition: filter 0.15s ease;
}

.hist__col--active .hist__bar {
  filter: brightness(1.3);
}

/* Direct label so the magnitude reads without hovering at all. */
.hist__count {
  font-size: 0.68rem;
  line-height: 1.4;
  text-align: center;
  font-variant-numeric: tabular-nums;
  opacity: 0.62;
}

.hist__col--active .hist__count {
  opacity: 1;
}

.hist__readout {
  position: absolute;
  bottom: calc(100% + 4px);
  z-index: 2;
  white-space: nowrap;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 0.72rem;
  font-variant-numeric: tabular-nums;
  background: rgb(var(--v-theme-surface-bright));
  border: 1px solid rgba(var(--v-border-color), 0.5);
  box-shadow: 0 4px 14px rgb(0 0 0 / 45%);
}

.hist__readout--centre {
  left: 50%;
  transform: translateX(-50%);
}

.hist__readout--start {
  left: 0;
}

.hist__readout--end {
  right: 0;
}

.hist__threshold {
  position: absolute;
  top: 0;
  bottom: 0;
  border-left: 2px dashed rgba(var(--v-theme-on-surface), 0.45);
}

.hist__threshold-label {
  position: absolute;
  top: 2px;
  left: 6px;
  white-space: nowrap;
  font-size: 0.7rem;
  opacity: 0.7;
}

.hist__threshold-label--flipped {
  left: auto;
  right: 6px;
  text-align: right;
}

.hist__axis {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 0.72rem;
  opacity: 0.55;
  font-variant-numeric: tabular-nums;
}

.hist__note {
  margin: 12px 0 0;
  font-size: 0.8rem;
  opacity: 0.75;
  line-height: 1.45;
}

.hist__empty {
  margin: 0;
  font-size: 0.85rem;
  opacity: 0.6;
}
</style>
