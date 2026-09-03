<script setup>
import { onBeforeUnmount, onMounted } from 'vue'

import PageHeader from '@/components/admin/PageHeader.vue'
import ReviewSubject from '@/components/curation/ReviewSubject.vue'
import {
  useCuration,
  VERDICT_DEFECT,
  VERDICT_NOISE,
} from '@/composables/useCuration'

const {
  sample,
  index,
  current,
  isDone,
  isLoading,
  isSaving,
  error,
  rationale,
  hasSignals,
  reviewedCount,
  draw,
  restore,
  judge,
  skip,
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
  else return

  event.preventDefault()
}

onMounted(() => {
  // Continues the stored sample rather than drawing a new one, so
  // revisiting the page does not silently hand out different work.
  restore()
  window.addEventListener('keydown', onKey)
})

onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div>
    <PageHeader
      title="Curadoria · Amostragem"
      subtitle="Amostra estratificada: metade sinalizada, metade não."
    >
      <template #actions>
        <span v-if="sample.length" class="progress">
          {{ Math.min(index + 1, sample.length) }} / {{ sample.length }}
        </span>
        <v-btn
          variant="text"
          prepend-icon="mdi-shuffle-variant"
          :loading="isLoading"
          @click="draw()"
        >
          Nova amostra
        </v-btn>
      </template>
    </PageHeader>

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
        <span class="metric__label">Nesta amostra</span>
        <span class="metric__value">
          {{ Math.min(index + 1, sample.length) }} de {{ sample.length }}
        </span>
        <span class="metric__hint">
          amostra estratificada: metade sinalizada, metade não
        </span>
      </div>
      <div class="metric">
        <span class="metric__label">Já julgadas</span>
        <span class="metric__value">{{ reviewedCount }}</span>
        <span class="metric__hint">
          revisar uma amostra basta — não é preciso julgar toda a base
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
        <ReviewSubject :item="current" />
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
          {{ hasSignals ? 'Aceitar' : 'Tem defeito' }}
          <kbd class="kbd">d</kbd>
        </v-btn>
        <v-btn
          variant="tonal"
          :loading="isSaving"
          :prepend-icon="hasSignals ? 'mdi-close' : 'mdi-check'"
          @click="judge(VERDICT_NOISE)"
        >
          {{ hasSignals ? 'Rejeitar' : 'Está correta' }}
          <kbd class="kbd">n</kbd>
        </v-btn>
        <v-spacer />
        <v-btn variant="text" @click="skip">
          Pular <kbd class="kbd">s</kbd>
        </v-btn>
      </div>

      <p class="hint">
        {{
          hasSignals
            ? 'Aceitar confirma que o problema apontado é real; rejeitar marca o sinal como falso positivo.'
            : 'Nenhum detector marcou esta interação — julgue a resposta pelo seu conteúdo.'
        }}
      </p>
    </template>
  </div>
</template>

<style scoped>
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

.progress {
  font-size: 0.82rem;
  opacity: 0.62;
  font-variant-numeric: tabular-nums;
}
</style>
