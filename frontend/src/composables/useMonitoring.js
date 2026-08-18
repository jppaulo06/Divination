import { computed, ref } from 'vue'

import { fetchMonitoringSummary, toErrorMessage } from '@/services/api'

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
  const isLoading = ref(false)
  const error = ref('')

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
      summary.value = await fetchMonitoringSummary()
    } catch (failure) {
      error.value = toErrorMessage(failure)
    } finally {
      isLoading.value = false
    }
  }

  return {
    summary,
    isLoading,
    error,
    hasData,
    signalRows,
    sourceRows,
    flaggedShare,
    load,
  }
}
