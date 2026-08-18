<script setup>
import { onMounted } from 'vue'

import PageHeader from '@/components/admin/PageHeader.vue'
import BarList from '@/components/monitoring/BarList.vue'
import StatTile from '@/components/monitoring/StatTile.vue'
import { signalLabel } from '@/composables/useMonitoring'
import { useDefects } from '@/composables/useDefects'

const {
  summary,
  visible,
  groups,
  blindSpotShare,
  signatureFilter,
  isLoading,
  error,
  load,
  filterBy,
} = useDefects()

onMounted(load)

function score(value) {
  return value === null || value === undefined ? '—' : value.toFixed(3)
}
</script>

<template>
  <div class="viz">
    <PageHeader
      title="Defeitos confirmados"
      subtitle="Interações que uma revisão humana julgou defeituosas."
    >
      <template #actions>
        <v-btn
          variant="text"
          prepend-icon="mdi-refresh"
          :loading="isLoading"
          @click="load"
        >
          Atualizar
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

    <v-alert
      v-else-if="!isLoading && !summary?.total"
      type="info"
      variant="tonal"
      density="comfortable"
      class="mb-5"
    >
      Nenhum defeito confirmado ainda. Julgue interações em
      <RouterLink :to="{ name: 'curation-sampling' }">Curadoria</RouterLink>.
    </v-alert>

    <section class="tiles">
      <StatTile
        label="Defeitos"
        icon="mdi-bug-outline"
        :value="summary?.total ?? 0"
        hint="confirmados por revisão humana"
      />
      <StatTile
        label="Pontos cegos"
        icon="mdi-eye-off-outline"
        :value="summary?.missed_by_detectors ?? 0"
        :hint="`${blindSpotShare}% dos defeitos sem nenhum sinal`"
      />
      <StatTile
        label="Já viraram teste"
        icon="mdi-shield-check-outline"
        :value="summary?.promoted ?? 0"
        hint="promovidos para o dataset de regressão"
      />
    </section>

    <section class="panels">
      <v-card flat class="panel">
        <h2 class="panel__title">Defeitos por assinatura de sinais</h2>
        <p class="panel__sub">
          Quais detectores marcaram cada defeito. Vários defeitos com a mesma
          assinatura são uma causa comum, não coincidência. Clique para filtrar.
        </p>
        <BarList
          :rows="groups"
          :active-key="signatureFilter"
          selectable
          empty-text="Nenhum defeito confirmado ainda."
          @select="filterBy"
        />
      </v-card>
    </section>

    <section>
      <div class="queue__head">
        <h2 class="panel__title">
          Perguntas com defeito
          <span class="queue__count">{{ visible.length }}</span>
        </h2>
        <v-chip
          v-if="signatureFilter"
          size="small"
          variant="tonal"
          closable
          @click:close="filterBy(signatureFilter)"
        >
          {{ signatureFilter }}
        </v-chip>
      </div>

      <v-expansion-panels
        v-if="visible.length"
        variant="accordion"
        class="list"
      >
        <v-expansion-panel
          v-for="defect in visible"
          :key="defect.interaction_id"
          elevation="0"
        >
          <v-expansion-panel-title>
            <div class="row">
              <span class="row__question">{{ defect.question }}</span>
              <div class="row__chips">
                <v-chip
                  v-if="defect.missed_by_detectors"
                  size="x-small"
                  variant="tonal"
                  color="warning"
                  label
                  prepend-icon="mdi-eye-off-outline"
                >
                  ponto cego
                </v-chip>
                <v-chip
                  v-for="signal in defect.signals"
                  :key="signal.type"
                  size="x-small"
                  variant="outlined"
                  label
                >
                  {{ signalLabel(signal.type) }}
                </v-chip>
                <v-chip
                  v-if="defect.promoted_golden"
                  size="x-small"
                  variant="tonal"
                  color="success"
                  label
                >
                  {{ defect.promoted_golden }}
                </v-chip>
              </div>
            </div>
          </v-expansion-panel-title>

          <v-expansion-panel-text>
            <dl class="meta">
              <div>
                <dt>score</dt>
                <dd>{{ score(defect.top_score) }}</dd>
              </div>
              <div>
                <dt>template</dt>
                <dd>{{ defect.template_name }}</dd>
              </div>
              <div>
                <dt>corpus</dt>
                <dd>{{ defect.corpus_version }}</dd>
              </div>
              <div>
                <dt>modelo</dt>
                <dd>{{ defect.model }}</dd>
              </div>
            </dl>

            <h4 class="section">Resposta com defeito</h4>
            <p class="answer">{{ defect.answer || '—' }}</p>

            <template v-if="defect.rationale">
              <h4 class="section">Diagnóstico do revisor</h4>
              <p class="answer">{{ defect.rationale }}</p>
            </template>

            <h4 class="section">
              Contexto recuperado ({{ defect.retrieval_context.length }})
            </h4>
            <ol class="chunks">
              <li
                v-for="(chunk, index) in defect.retrieval_context"
                :key="index"
              >
                {{ chunk }}
              </li>
            </ol>

            <p class="next">
              Compare a resposta com o contexto: se a informação correta está
              nos trechos, o problema é de geração (prompt); se não está, é de
              retrieval ou de cobertura do corpus.
            </p>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </section>
  </div>
</template>

<style scoped>
.viz {
  --viz-series-1: #9b6dff;
}

.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  margin-bottom: 20px;
}

.panels {
  margin-bottom: 24px;
}

.panel {
  background: rgb(var(--v-theme-surface));
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  padding: 18px 20px 20px;
}

.panel__title {
  font-family: var(--divination-font-display, inherit);
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel__sub {
  margin: 4px 0 16px;
  font-size: 0.78rem;
  opacity: 0.58;
  line-height: 1.5;
}

.queue__head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.queue__count {
  font-size: 0.78rem;
  opacity: 0.55;
  font-variant-numeric: tabular-nums;
}

.list {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
  overflow: hidden;
}

.row {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  padding-right: 8px;
}

.row__question {
  font-size: 0.92rem;
  overflow-wrap: anywhere;
}

.row__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin: 0 0 14px;
  font-size: 0.8rem;
}

.meta dt {
  opacity: 0.55;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  font-size: 0.64rem;
}

.meta dd {
  margin: 2px 0 0;
  font-variant-numeric: tabular-nums;
}

.section {
  margin: 16px 0 6px;
  font-size: 0.7rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  opacity: 0.6;
  font-weight: 600;
}

.answer {
  margin: 0;
  white-space: pre-wrap;
  font-size: 0.87rem;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.chunks {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 0.8rem;
  opacity: 0.8;
}

.chunks li {
  overflow-wrap: anywhere;
}

.next {
  margin: 18px 0 0;
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), 0.05);
  font-size: 0.8rem;
  line-height: 1.5;
  opacity: 0.85;
}
</style>
