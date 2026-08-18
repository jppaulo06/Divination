import { computed, ref } from 'vue'

import {
  fetchCurationSample,
  fetchCurationStats,
  submitReview,
  toErrorMessage,
} from '@/services/api'

export const VERDICT_DEFECT = 'defect'
export const VERDICT_NOISE = 'noise'

export function useCuration() {
  const sample = ref([])
  const stats = ref(null)
  const index = ref(0)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref('')
  const rationale = ref('')
  // Signals stay hidden until a verdict is in: seeing them first anchors
  // the reviewer, and an anchored judgement cannot measure the detectors.
  const signalsRevealed = ref(false)
  const reviewedCount = ref(0)

  const current = computed(() => sample.value[index.value] ?? null)
  const remaining = computed(() =>
    Math.max(sample.value.length - index.value, 0),
  )
  const isDone = computed(
    () => sample.value.length > 0 && index.value >= sample.value.length,
  )

  async function load({ size = 20, flaggedShare = 0.5 } = {}) {
    isLoading.value = true
    error.value = ''
    try {
      const [nextSample, nextStats] = await Promise.all([
        fetchCurationSample({ size, flaggedShare }),
        fetchCurationStats(),
      ])
      sample.value = nextSample
      stats.value = nextStats
      index.value = 0
      reviewedCount.value = 0
      resetTurn()
    } catch (failure) {
      error.value = toErrorMessage(failure)
      sample.value = []
    } finally {
      isLoading.value = false
    }
  }

  function resetTurn() {
    rationale.value = ''
    signalsRevealed.value = false
  }

  function revealSignals() {
    signalsRevealed.value = true
  }

  function skip() {
    if (!current.value) return
    index.value += 1
    resetTurn()
  }

  async function judge(verdict) {
    const item = current.value
    if (!item || isSaving.value) return

    isSaving.value = true
    error.value = ''
    try {
      await submitReview({
        interactionId: item.interaction_id,
        verdict,
        rationale: rationale.value.trim() || null,
      })
      reviewedCount.value += 1
      index.value += 1
      resetTurn()
      // Refreshed per verdict so precision and recall move as you work.
      stats.value = await fetchCurationStats()
    } catch (failure) {
      error.value = toErrorMessage(failure)
    } finally {
      isSaving.value = false
    }
  }

  return {
    sample,
    stats,
    index,
    current,
    remaining,
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
  }
}

/** Formats a 0-1 metric, or a dash when there is not enough data yet. */
export function asPercent(value) {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value * 100)}%`
}
