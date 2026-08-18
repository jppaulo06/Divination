<script setup>
import { onBeforeUnmount, onMounted } from 'vue'

import ReviewSubject from '@/components/curation/ReviewSubject.vue'
import {
  asPercent,
  useCuration,
  VERDICT_DEFECT,
  VERDICT_NOISE,
} from '@/composables/useCuration'

const {
  sample,
  stats,
  index,
  current,
  isDone,
  isLoading,
  isSaving,
  error,
  rationale,
  signalsRevealed,
  reviewedCount,
  load,
  judge,
  skip,
  revealSignals,
} = useCuration()

/**
 * Keyboard first: reviewing a sample is a repetitive pass, and reaching
 * for the mouse on every item is what stops people at five instead of a
 * hundred. Ignored while typing a rationale.
 */
function onKey(event) {
  const tag = event.target?.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA') return
  if (event.metaKey || event.ctrlKey || event.altKey) return

  const key = event.key.toLowerCase()
  if (key === 'd') judge(VERDICT_DEFECT)
  else if (key === 'n') judge(VERDICT_NOISE)
  else if (key === 's' || key === 'arrowright') skip()
  else if (key === 'r') revealSignals()
  else return

  event.preventDefault()
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKey)
})

onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <v-app-bar :height="64" flat class="topbar">
    <v-btn
      icon="mdi-arrow-left"
      variant="text"
      aria-label="Voltar para o monitoramento"
      :to="{ name: 'monitoring' }"
    />
    <div class="topbar__brand">
      <v-icon icon="mdi-scale-balance" color="primary" size="22" />
      <span class="topbar__name">Curadoria</span>
    </div>

    <v-spacer />

    <span v-if="sample.length" class="topbar__progress">
      {{ Math.min(index + 1, sample.length) }} / {{ sample.length }}
    </span>

    <v-btn
      variant="text"
      prepend-icon="mdi-shuffle-variant"
      :loading="isLoading"
      class="ml-2"
      @click="load()"
    >
      Nova amostra
    </v-btn>
  </v-app-bar>

  <v-main class="main">
    <div class="page">
      <v-alert
        v-if="error"
        type="error"
        variant="tonal"
        density="comfortable"
        class="mb-5"
      >
        {{ error }}
      </v-alert>

      <section class="metrics">
        <div class="metric">
          <span class="metric__label">Precisão dos detectores</span>
          <span class="metric__value">{{ asPercent(stats?.precision) }}</span>
          <span class="metric__hint">
            {{ stats?.flagged?.defects ?? 0 }} defeitos em
            {{ stats?.flagged?.reviewed ?? 0 }} sinalizadas revisadas
          </span>
        </div>
        <div class="metric">
          <span class="metric__label">Recall estimado</span>
          <span class="metric__value">
            {{ asPercent(stats?.estimated_recall) }}
          </span>
          <span class="metric__hint">
            {{ stats?.unflagged?.defects ?? 0 }} defeitos encontrados em
            {{ stats?.unflagged?.reviewed ?? 0 }} não sinalizadas
          </span>
        </div>
        <div class="metric">
          <span class="metric__label">Revisadas nesta sessão</span>
          <span class="metric__value">{{ reviewedCount }}</span>
          <span class="metric__hint">
            amostra estratificada: metade sinalizada, metade não
          </span>
        </div>
      </section>

      <v-card v-if="isLoading" flat class="panel panel--quiet">
        <v-progress-circular indeterminate size="22" />
        <span>Sorteando amostra…</span>
      </v-card>

      <v-card v-else-if="isDone" flat class="panel panel--quiet">
        <v-icon icon="mdi-check-circle-outline" size="22" color="primary" />
        <span>Amostra revisada. Sorteie outra para continuar.</span>
      </v-card>

      <v-card v-else-if="!current" flat class="panel panel--quiet">
        <v-icon icon="mdi-inbox-outline" size="22" />
        <span>
          Nada para revisar. Gere tráfego com
          <code>scripts/generate_traffic.py</code>.
        </span>
      </v-card>

      <template v-else>
        <v-card flat class="panel">
          <ReviewSubject
            :item="current"
            :signals-revealed="signalsRevealed"
            @reveal="revealSignals"
          />
        </v-card>

        <v-textarea
          v-model="rationale"
          label="Justificativa (opcional)"
          rows="2"
          auto-grow
          class="mt-4"
        />

        <div class="actions">
          <v-btn
            color="error"
            :loading="isSaving"
            prepend-icon="mdi-bug-outline"
            @click="judge(VERDICT_DEFECT)"
          >
            Defeito <kbd class="kbd">d</kbd>
          </v-btn>
          <v-btn
            variant="tonal"
            :loading="isSaving"
            prepend-icon="mdi-weather-cloudy"
            @click="judge(VERDICT_NOISE)"
          >
            Ruído <kbd class="kbd">n</kbd>
          </v-btn>
          <v-spacer />
          <v-btn variant="text" @click="skip">
            Pular <kbd class="kbd">s</kbd>
          </v-btn>
        </div>

        <p class="hint">
          Os sinais ficam escondidos até você julgar — ver o que os
          detectores acharam antes ancoraria o julgamento que serve para
          medi-los. <kbd class="kbd">r</kbd> revela.
        </p>
      </template>
    </div>
  </v-main>
</template>

<style scoped>
.main {
  min-height: 100dvh;
}

.page {
  max-width: 820px;
  margin: 0 auto;
  padding: 26px 20px 72px;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.metric {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 14px 16px;
  border-radius: 10px;
  background: rgb(var(--v-theme-surface-light));
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.metric__label {
  font-size: 0.68rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  opacity: 0.6;
}

.metric__value {
  font-family: var(--divination-font-display, inherit);
  font-size: 1.6rem;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.metric__hint {
  font-size: 0.74rem;
  opacity: 0.55;
}

.panel {
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  padding: 20px 22px;
}

.panel--quiet {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 0.9rem;
  opacity: 0.8;
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  flex-wrap: wrap;
}

.kbd {
  margin-left: 8px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  background: rgba(var(--v-theme-on-surface), 0.14);
}

.hint {
  margin: 16px 0 0;
  font-size: 0.78rem;
  opacity: 0.6;
  line-height: 1.5;
}

.topbar {
  background: rgba(var(--v-theme-surface), 0.82) !important;
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.topbar__brand {
  display: flex;
  align-items: baseline;
  gap: 9px;
  padding-inline: 6px;
}

.topbar__name {
  font-family: var(--divination-font-display, inherit);
  font-size: 1.15rem;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.topbar__progress {
  font-size: 0.82rem;
  opacity: 0.62;
  font-variant-numeric: tabular-nums;
}
</style>
