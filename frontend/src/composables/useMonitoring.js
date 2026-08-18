import { computed, ref } from 'vue'

import {
  fetchCandidates,
  fetchMonitoringSummary,
  toErrorMessage,
} from '@/services/api'

/** Human labels for the signal types the detectors emit. */
const SIGNAL_LABELS = {
  weak_retrieval: 'Retrieval fraco',
  unsupported_claim: 'Número sem suporte',
  refusal_or_hedge: 'Recusa / ressalva',
  format_guardrail_violation: 'Formato fora do padrão',
  repeated_question: 'Pergunta repetida',
  user_negative_feedback: 'Avaliação negativa',
}

export function signalLabel(type) {
  return SIGNAL_LABELS[type] ?? type
}

export function useMonitoring() {
  const summary = ref(null)
  const candidates = ref([])
  const isLoading = ref(false)
  const error = ref('')
  const signalFilter = ref(null)

  const hasData = computed(() => (summary.value?.interactions ?? 0) > 0)

  /** Signal counts as chart rows, largest first. */
  const signalRows = computed(() => {
    const counts = summary.value?.signals_by_type ?? {}
    return Object.entries(counts)
      .map(([type, value]) => ({ key: type, label: signalLabel(type), value }))
      .sort((a, b) => b.value - a.value)
  })

  const sourceRows = computed(() => {
    const counts = summary.value?.interactions_by_source ?? {}
    return Object.entries(counts)
      .map(([source, value]) => ({ key: source, label: source, value }))
      .sort((a, b) => b.value - a.value)
  })

  /** Share of interactions carrying at least one signal. */
  const flaggedShare = computed(() => {
    const total = summary.value?.interactions ?? 0
    if (!total) return 0
    return Math.round(((summary.value?.flagged_interactions ?? 0) / total) * 100)
  })

  async function load() {
    isLoading.value = true
    error.value = ''
    try {
      const [nextSummary, nextCandidates] = await Promise.all([
        fetchMonitoringSummary(),
        fetchCandidates({ signalType: signalFilter.value }),
      ])
      summary.value = nextSummary
      candidates.value = nextCandidates
    } catch (failure) {
      error.value = toErrorMessage(failure)
    } finally {
      isLoading.value = false
    }
  }

  async function filterBy(type) {
    // Clicking the active filter clears it, so the chart doubles as a
    // toggle rather than needing a separate reset control.
    signalFilter.value = signalFilter.value === type ? null : type
    await load()
  }

  return {
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
  }
}
