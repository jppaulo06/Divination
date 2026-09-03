import { computed, ref } from 'vue'

import {
  fetchCurationSample,
  submitReview,
  toErrorMessage,
} from '@/services/api'

export const VERDICT_DEFECT = 'defect'
export const VERDICT_NOISE = 'noise'

/**
 * Reviewing is sampling, not clearing a queue: a handful of judged
 * interactions estimates detector quality, and a session short enough to
 * finish in one sitting keeps that judgement careful.
 */
export const SAMPLE_SIZE = 6

const STORAGE_KEY = 'divination:curation-sample'

/**
 * The drawn sample is kept in the browser so returning to the page
 * continues the same one instead of drawing a fresh set. There are no
 * accounts, so the browser is the only thing that identifies a reviewer;
 * a new set is drawn only when one is explicitly asked for.
 */
function readStored() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null')
    if (!Array.isArray(parsed?.items) || !parsed.items.length) return null
    return {
      items: parsed.items,
      index: Number(parsed.index) || 0,
      reviewed: Number(parsed.reviewed) || 0,
    }
  } catch {
    // Corrupt or unreadable entry: fall back to drawing a new sample.
    return null
  }
}

export function useCuration() {
  const sample = ref([])
  const index = ref(0)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref('')
  const rationale = ref('')
  const reviewedCount = ref(0)

  const current = computed(() => sample.value[index.value] ?? null)
  const remaining = computed(() =>
    Math.max(sample.value.length - index.value, 0),
  )
  const hasSignals = computed(
    () => (current.value?.signals?.length ?? 0) > 0,
  )
  const isDone = computed(
    () => sample.value.length > 0 && index.value >= sample.value.length,
  )

  function persist() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          items: sample.value,
          index: index.value,
          reviewed: reviewedCount.value,
        }),
      )
    } catch {
      // Quota or private mode: the sample simply will not survive a
      // reload, which is a worse experience but not a broken one.
    }
  }

  /** Draws a new sample, replacing whatever was stored. */
  async function draw({ size = SAMPLE_SIZE, flaggedShare = 0.5 } = {}) {
    isLoading.value = true
    error.value = ''
    try {
      sample.value = await fetchCurationSample({ size, flaggedShare })
      index.value = 0
      reviewedCount.value = 0
      resetTurn()
      persist()
    } catch (failure) {
      error.value = toErrorMessage(failure)
      sample.value = []
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Continues the stored sample, drawing one only on a first visit.
   * Progress is restored too, so reviewed items are not offered again.
   */
  async function restore(options) {
    const stored = readStored()
    if (!stored) return draw(options)

    sample.value = stored.items
    index.value = Math.min(stored.index, stored.items.length)
    reviewedCount.value = stored.reviewed
    resetTurn()
  }

  function resetTurn() {
    rationale.value = ''
  }

  function skip() {
    if (!current.value) return
    index.value += 1
    resetTurn()
    persist()
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
      persist()
    } catch (failure) {
      error.value = toErrorMessage(failure)
    } finally {
      isSaving.value = false
    }
  }

  return {
    sample,
    index,
    current,
    remaining,
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
  }
}

/** Formats a 0-1 metric, or a dash when there is not enough data yet. */
export function asPercent(value) {
  if (value === null || value === undefined) return '—'
  return `${Math.round(value * 100)}%`
}
