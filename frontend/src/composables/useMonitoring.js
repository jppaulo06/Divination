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

const round2 = (value) =>
  typeof value === 'number' ? value.toFixed(2) : String(value ?? '—')

const quoted = (values) => values.map((value) => `“${value}”`).join('; ')

/**
 * One line naming what a detector actually found, so a reviewer knows
 * where to look. Empty when the signal carries nothing locatable.
 */
export function signalDetail(signal) {
  const details = signal?.details ?? {}

  switch (signal?.type) {
    case 'weak_retrieval':
      if (details.reason) return 'Nenhum trecho recuperado.'
      return (
        `Melhor trecho ${round2(details.top_score)}, abaixo do limite ` +
        `${round2(details.threshold)} (${details.chunk_count ?? 0} trechos).`
      )

    case 'unsupported_claim': {
      const values = [
        ...(details.unsupported_dice ?? []),
        ...(details.unsupported_dcs ?? []),
      ]
      if (!values.length) return ''
      return `Sem apoio no contexto: ${values.join(', ')}.`
    }

    case 'refusal_or_hedge':
      if (!details.matches?.length) return ''
      return `Ressalvas na resposta: ${quoted(details.matches)}.`

    case 'format_guardrail_violation':
      if (details.reason) return 'Resposta vazia.'
      return `Não termina com “${details.required_closing}”.`

    case 'repeated_question': {
      const share = Math.round((details.similarity ?? 0) * 100)
      if (!details.prior_question) return ''
      return `${share}% semelhante a “${details.prior_question}”.`
    }

    case 'user_negative_feedback':
      return 'O usuário avaliou esta resposta como ruim.'

    default:
      return ''
  }
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
