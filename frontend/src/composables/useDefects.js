import { computed, ref } from 'vue'

import { fetchDefects, toErrorMessage } from '@/services/api'

export function useDefects() {
  const defects = ref([])
  const summary = ref(null)
  const isLoading = ref(false)
  const error = ref('')
  const signatureFilter = ref(null)

  /** Signature groups, largest first — the biggest one is the work item. */
  const groups = computed(() => {
    const counts = summary.value?.by_signature ?? {}
    return Object.entries(counts)
      .map(([key, value]) => ({ key, label: key, value }))
      .sort((a, b) => b.value - a.value)
  })

  const visible = computed(() =>
    signatureFilter.value
      ? defects.value.filter((d) => d.signature === signatureFilter.value)
      : defects.value,
  )

  const blindSpotShare = computed(() => {
    const total = summary.value?.total ?? 0
    if (!total) return 0
    return Math.round(((summary.value?.missed_by_detectors ?? 0) / total) * 100)
  })

  async function load() {
    isLoading.value = true
    error.value = ''
    try {
      const payload = await fetchDefects()
      defects.value = payload.defects
      summary.value = payload.summary
    } catch (failure) {
      error.value = toErrorMessage(failure)
      defects.value = []
      summary.value = null
    } finally {
      isLoading.value = false
    }
  }

  function filterBy(signature) {
    signatureFilter.value =
      signatureFilter.value === signature ? null : signature
  }

  return {
    defects,
    summary,
    visible,
    groups,
    blindSpotShare,
    signatureFilter,
    isLoading,
    error,
    load,
    filterBy,
  }
}
