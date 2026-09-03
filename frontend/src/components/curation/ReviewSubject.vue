<script setup>
import { computed } from 'vue'

import { signalDetail, signalLabel } from '@/composables/useMonitoring'

const props = defineProps({
  item: { type: Object, required: true },
})

// Strictly earlier turns: a later turn is not history, and showing one
// reveals that the user re-asked.
const priorTurns = computed(() =>
  props.item.thread.filter(
    (turn) => turn.turn_index < props.item.turn_index,
  ),
)
const hasThread = computed(() => priorTurns.value.length > 0)
const historyLabel = computed(() =>
  priorTurns.value.length === 1
    ? '1 turno anterior'
    : `${priorTurns.value.length} turnos anteriores`,
)
const score = computed(() =>
  props.item.top_score === null ? '—' : props.item.top_score.toFixed(3),
)
const hasSignals = computed(() => props.item.signals.length > 0)
</script>

<template>
  <div class="subject">
    <section v-if="hasThread" class="subject__history">
      <h3 class="subject__history-title">Conversa até aqui · {{ historyLabel }}</h3>
      <div
        v-for="turn in priorTurns"
        :key="turn.turn_index"
        class="subject__turn"
      >
        <p class="subject__turn-q">{{ turn.question }}</p>
        <p class="subject__turn-a">{{ turn.answer }}</p>
      </div>
    </section>

    <p v-if="hasThread" class="subject__label">Turno em avaliação</p>

    <div class="subject__question">{{ item.question }}</div>

    <div class="subject__answer">{{ item.answer || '—' }}</div>

    <dl class="subject__meta">
      <div><dt>score</dt><dd>{{ score }}</dd></div>
      <div><dt>latência</dt><dd>{{ item.latency_ms }} ms</dd></div>
      <div><dt>template</dt><dd>{{ item.template_name }}</dd></div>
      <div><dt>corpus</dt><dd>{{ item.corpus_version }}</dd></div>
      <div><dt>turno</dt><dd>{{ item.turn_index + 1 }}</dd></div>
    </dl>

    <v-expansion-panels variant="accordion" class="subject__panels">
      <v-expansion-panel elevation="0">
        <v-expansion-panel-title>
          Contexto recuperado ({{ item.retrieval_context.length }})
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <ol class="subject__chunks">
            <li
              v-for="(chunk, position) in item.retrieval_context"
              :key="position"
            >
              {{ chunk }}
            </li>
          </ol>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- Absent when nothing fired: stating the absence anchors the
         verdict on unflagged items. -->
    <div v-if="hasSignals" class="subject__signals">
      <h3 class="subject__signals-title">Problema detectado</h3>

      <ul class="subject__findings">
        <li v-for="signal in item.signals" :key="signal.type">
          <v-icon icon="mdi-alert-outline" size="15" class="mr-1" />
          <span class="subject__finding-type">
            {{ signalLabel(signal.type) }}
          </span>
          <span v-if="signalDetail(signal)" class="subject__finding-detail">
            {{ signalDetail(signal) }}
          </span>
        </li>
      </ul>

      <div v-if="item.feedback.length" class="subject__chips">
        <v-chip
          v-for="(entry, position) in item.feedback"
          :key="position"
          size="small"
          variant="tonal"
          label
          :prepend-icon="entry.rating > 0 ? 'mdi-thumb-up' : 'mdi-thumb-down'"
        >
          {{ entry.comment || (entry.rating > 0 ? 'positivo' : 'negativo') }}
        </v-chip>
      </div>
    </div>
  </div>
</template>

<style scoped>
.subject__question {
  font-family: var(--divination-font-display, inherit);
  font-size: 1.1rem;
  line-height: 1.4;
  margin-bottom: 14px;
  overflow-wrap: anywhere;
}

.subject__answer {
  white-space: pre-wrap;
  font-size: 0.92rem;
  line-height: 1.6;
  padding: 14px 16px;
  border-radius: 10px;
  background: rgba(var(--v-theme-on-surface), 0.05);
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  overflow-wrap: anywhere;
}

.subject__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin: 14px 0;
  font-size: 0.8rem;
}

.subject__meta dt {
  opacity: 0.55;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  font-size: 0.64rem;
}

.subject__meta dd {
  margin: 2px 0 0;
  font-variant-numeric: tabular-nums;
}

.subject__panels {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
  overflow: hidden;
}

.subject__chunks {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 0.8rem;
  opacity: 0.82;
}

.subject__chunks li {
  overflow-wrap: anywhere;
}

.subject__history {
  margin-bottom: 16px;
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(var(--v-theme-surface-light), 0.45);
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  /* A long thread must not push the turn under review off screen. */
  max-height: 320px;
  overflow-y: auto;
}

.subject__history-title,
.subject__label {
  font-size: 0.7rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  font-weight: 600;
  opacity: 0.55;
  margin: 0 0 10px;
}

.subject__label {
  margin-bottom: 6px;
}

.subject__turn {
  padding-bottom: 12px;
  margin-bottom: 12px;
  border-bottom: 1px solid rgba(var(--v-border-color), 0.5);
}

.subject__turn:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.subject__turn-q {
  margin: 0 0 4px;
  font-size: 0.85rem;
  font-weight: 600;
}

.subject__turn-a {
  margin: 0;
  font-size: 0.82rem;
  opacity: 0.75;
  white-space: pre-wrap;
}

.subject__signals {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(var(--v-theme-warning), 0.08);
  border: 1px solid rgba(var(--v-theme-warning), 0.35);
}

.subject__signals-title {
  font-size: 0.7rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  font-weight: 600;
  opacity: 0.7;
  margin: 0;
}

.subject__findings {
  list-style: none;
  margin: 8px 0 0;
  padding: 0;
}

.subject__findings li {
  font-size: 0.83rem;
  line-height: 1.5;
  margin-bottom: 4px;
  overflow-wrap: anywhere;
}

.subject__findings li:last-child {
  margin-bottom: 0;
}

.subject__finding-type {
  font-weight: 600;
}

.subject__finding-detail {
  opacity: 0.78;
}

.subject__finding-detail::before {
  content: ' — ';
  opacity: 0.5;
}

.subject__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
</style>
