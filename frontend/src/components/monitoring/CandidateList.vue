<script setup>
import { signalLabel } from '@/composables/useMonitoring'

defineProps({
  candidates: { type: Array, required: true },
})

function ratingIcon(rating) {
  return rating > 0 ? 'mdi-thumb-up' : 'mdi-thumb-down'
}

function score(value) {
  return value === null || value === undefined ? '—' : value.toFixed(3)
}
</script>

<template>
  <p v-if="!candidates.length" class="cand__empty">
    Nenhuma interação sinalizada aguardando curadoria.
  </p>

  <v-expansion-panels v-else variant="accordion" class="cand">
    <v-expansion-panel
      v-for="candidate in candidates"
      :key="candidate.interaction_id"
      elevation="0"
    >
      <v-expansion-panel-title>
        <div class="cand__head">
          <span class="cand__question">{{ candidate.question }}</span>
          <div class="cand__chips">
            <v-chip
              v-for="signal in candidate.signals"
              :key="signal.type"
              size="x-small"
              variant="outlined"
              label
            >
              {{ signalLabel(signal.type) }}
            </v-chip>
            <v-chip
              v-for="(entry, index) in candidate.feedback"
              :key="`f${index}`"
              size="x-small"
              variant="tonal"
              label
              :prepend-icon="ratingIcon(entry.rating)"
            >
              {{ entry.comment || (entry.rating > 0 ? 'positivo' : 'negativo') }}
            </v-chip>
          </div>
        </div>
      </v-expansion-panel-title>

      <v-expansion-panel-text>
        <dl class="cand__meta">
          <div><dt>score</dt><dd>{{ score(candidate.top_score) }}</dd></div>
          <div><dt>latência</dt><dd>{{ candidate.latency_ms }} ms</dd></div>
          <div><dt>template</dt><dd>{{ candidate.template_name }}</dd></div>
          <div><dt>corpus</dt><dd>{{ candidate.corpus_version }}</dd></div>
          <div><dt>origem</dt><dd>{{ candidate.source }}</dd></div>
        </dl>

        <h4 class="cand__section">Resposta</h4>
        <p class="cand__answer">{{ candidate.answer || '—' }}</p>

        <h4 class="cand__section">
          Contexto recuperado ({{ candidate.retrieval_context.length }})
        </h4>
        <ol class="cand__chunks">
          <li v-for="(chunk, index) in candidate.retrieval_context" :key="index">
            {{ chunk }}
          </li>
        </ol>

        <h4 class="cand__section">Detalhes dos sinais</h4>
        <pre class="cand__details">{{
          JSON.stringify(
            Object.fromEntries(
              candidate.signals.map((s) => [s.type, s.details]),
            ),
            null,
            2,
          )
        }}</pre>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>

<style scoped>
.cand {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
  overflow: hidden;
}

.cand__head {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  padding-right: 8px;
}

.cand__question {
  font-size: 0.92rem;
  overflow-wrap: anywhere;
}

.cand__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.cand__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin: 0 0 16px;
  font-size: 0.8rem;
}

.cand__meta dt {
  opacity: 0.55;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  font-size: 0.66rem;
}

.cand__meta dd {
  margin: 2px 0 0;
  font-variant-numeric: tabular-nums;
}

.cand__section {
  margin: 16px 0 6px;
  font-size: 0.72rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  opacity: 0.6;
  font-weight: 600;
}

.cand__answer {
  margin: 0;
  white-space: pre-wrap;
  font-size: 0.87rem;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.cand__chunks {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 0.8rem;
  opacity: 0.8;
}

.cand__chunks li {
  overflow-wrap: anywhere;
}

.cand__details {
  margin: 0;
  padding: 12px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.06);
  font-size: 0.75rem;
  overflow-x: auto;
}
</style>
