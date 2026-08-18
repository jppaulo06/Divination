<script setup>
import { onMounted } from 'vue'

import PageHeader from '@/components/admin/PageHeader.vue'
import BarList from '@/components/monitoring/BarList.vue'
import ScoreHistogram from '@/components/monitoring/ScoreHistogram.vue'
import StatTile from '@/components/monitoring/StatTile.vue'
import { useMonitoring } from '@/composables/useMonitoring'

const {
  summary,
  isLoading,
  error,
  hasData,
  signalRows,
  sourceRows,
  flaggedShare,
  load,
} = useMonitoring()

onMounted(load)
</script>

<template>
  <div class="viz">
    <PageHeader
      title="Monitoramento"
      subtitle="O que a produção fez, e o que os detectores acharam estranho."
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
      class="mb-6"
    >
      {{ error }}
    </v-alert>

    <v-alert
      v-else-if="!isLoading && !hasData"
      type="info"
      variant="tonal"
      density="comfortable"
      class="mb-6"
    >
      Nenhuma interação registrada ainda. Converse com o assistente, ou popule a
      base com
      <code>python scripts/generate_traffic.py</code>.
    </v-alert>

    <section class="tiles">
      <StatTile
        label="Interações"
        icon="mdi-message-text-outline"
        :value="summary?.interactions ?? 0"
        :hint="`p50 ${summary?.latency_ms?.p50 ?? 0} ms · máx ${
          summary?.latency_ms?.max ?? 0
        } ms`"
      />
      <StatTile
        label="Sinalizadas"
        icon="mdi-flag-outline"
        :value="summary?.flagged_interactions ?? 0"
        :hint="`${flaggedShare}% do tráfego`"
      />
      <StatTile
        label="Aguardando curadoria"
        icon="mdi-inbox-arrow-down-outline"
        :value="summary?.pending_candidates ?? 0"
        :hint="`${summary?.reviewed_interactions ?? 0} já revisadas`"
      />
      <StatTile
        label="Avaliações"
        icon="mdi-thumbs-up-down-outline"
        :value="
          (summary?.feedback?.positive ?? 0) +
          (summary?.feedback?.negative ?? 0)
        "
        :hint="`${summary?.feedback?.negative ?? 0} negativas · ${
          summary?.feedback?.positive ?? 0
        } positivas`"
      />
    </section>

    <section class="panels">
      <v-card flat class="panel">
        <h2 class="panel__title">Sinais por tipo</h2>
        <p class="panel__sub">Quantas vezes cada detector disparou.</p>
        <BarList
          :rows="signalRows"
          empty-text="Nenhum sinal levantado ainda."
        />
      </v-card>

      <v-card flat class="panel">
        <h2 class="panel__title">Distribuição do score de retrieval</h2>
        <p class="panel__sub">
          Um score por interação — o melhor chunk que o retriever achou.
        </p>
        <ScoreHistogram
          :bins="summary?.retrieval_scores?.bins ?? []"
          :threshold="summary?.retrieval_scores?.threshold ?? null"
          :below-threshold="summary?.retrieval_scores?.below_threshold ?? 0"
          :count="summary?.retrieval_scores?.count ?? 0"
        />
      </v-card>

      <v-card flat class="panel">
        <h2 class="panel__title">Origem do tráfego</h2>
        <p class="panel__sub">
          Execuções de eval e tráfego sintético ficam marcados, não excluídos.
        </p>
        <BarList :rows="sourceRows" empty-text="Sem tráfego registrado." />
      </v-card>
    </section>
  </div>
</template>

<style scoped>
/*
 * Chart roles live here so the marks are written against roles rather
 * than raw hex. The app ships a single dark theme, so there is one set of
 * values; --viz-series-1 is the app's secondary violet, validated against
 * this surface for lightness band, chroma and 3:1 contrast.
 */
.viz {
  --viz-series-1: #9b6dff;
}

.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  margin-bottom: 22px;
}

.panels {
  /* One visualisation per row: each chart gets the full column width so
     the bars and bins are readable rather than cramped side by side. */
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
  margin-bottom: 26px;
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
}
</style>
