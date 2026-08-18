<script setup>
import { onMounted } from 'vue'

import BarList from '@/components/monitoring/BarList.vue'
import CandidateList from '@/components/monitoring/CandidateList.vue'
import ScoreHistogram from '@/components/monitoring/ScoreHistogram.vue'
import StatTile from '@/components/monitoring/StatTile.vue'
import { useMonitoring } from '@/composables/useMonitoring'

const {
  summary,
  candidates,
  isLoading,
  error,
  signalFilter,
  hasData,
  signalRows,
  sourceRows,
  flaggedShare,
  load,
  filterBy,
} = useMonitoring()

onMounted(load)
</script>

<template>
  <v-app-bar :height="64" flat class="topbar">
    <v-btn
      icon="mdi-arrow-left"
      variant="text"
      aria-label="Voltar para o chat"
      :to="{ name: 'home' }"
    />
    <div class="topbar__brand">
      <v-icon icon="mdi-radar" color="primary" size="22" />
      <span class="topbar__name">Monitoramento</span>
    </div>

    <v-spacer />

    <v-btn
      variant="text"
      prepend-icon="mdi-scale-balance"
      :to="{ name: 'curation' }"
    >
      Curadoria
    </v-btn>

    <v-btn
      variant="text"
      prepend-icon="mdi-refresh"
      :loading="isLoading"
      @click="load"
    >
      Atualizar
    </v-btn>
  </v-app-bar>

  <v-main class="main">
    <div class="viz page">
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
        Nenhuma interação registrada ainda. Converse com o assistente, ou
        popule a base com
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
          <p class="panel__sub">
            Clique para filtrar a fila de curadoria.
          </p>
          <BarList
            :rows="signalRows"
            :active-key="signalFilter"
            selectable
            empty-text="Nenhum sinal levantado ainda."
            @select="filterBy"
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
            Execuções de eval e tráfego sintético ficam marcados, não
            excluídos.
          </p>
          <BarList
            :rows="sourceRows"
            empty-text="Sem tráfego registrado."
          />
        </v-card>
      </section>

      <section class="queue">
        <div class="queue__head">
          <h2 class="panel__title">
            Fila de curadoria
            <span class="queue__count">{{ candidates.length }}</span>
          </h2>
          <v-chip
            v-if="signalFilter"
            size="small"
            variant="tonal"
            closable
            @click:close="filterBy(signalFilter)"
          >
            {{ signalFilter }}
          </v-chip>
        </div>
        <p class="panel__sub">
          Interações com pelo menos um sinal e sem revisão, mais sinalizadas
          primeiro.
        </p>
        <CandidateList :candidates="candidates" />
      </section>
    </div>
  </v-main>
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

.main {
  min-height: 100dvh;
}

.page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 28px 20px 64px;
}

.tiles {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
  margin-bottom: 22px;
}

.panels {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 14px;
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

.queue__head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.queue__count {
  font-size: 0.78rem;
  opacity: 0.55;
  font-variant-numeric: tabular-nums;
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
</style>
