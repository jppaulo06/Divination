import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDefects } from '@/composables/useDefects'
import * as api from '@/services/api'

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, fetchDefects: vi.fn() }
})

const defect = (id, signature, signals = []) => ({
  interaction_id: id,
  question: `q${id}`,
  answer: 'a',
  signature,
  signals,
  feedback: [],
  retrieval_context: [],
  missed_by_detectors: signals.length === 0,
  rationale: null,
  template_name: 'default',
  corpus_version: 'abc-383',
  model: 'sabia-4',
  top_score: 0.6,
  promoted_golden: null,
})

const payload = {
  summary: {
    total: 3,
    missed_by_detectors: 1,
    promoted: 0,
    by_signature: {
      weak_retrieval: 2,
      '(nenhum sinal)': 1,
    },
    by_template: { default: 3 },
    by_corpus: { 'abc-383': 3 },
  },
  defects: [
    defect('1', 'weak_retrieval', [{ type: 'weak_retrieval' }]),
    defect('2', 'weak_retrieval', [{ type: 'weak_retrieval' }]),
    defect('3', '(nenhum sinal)'),
  ],
}

describe('useDefects', () => {
  beforeEach(() => vi.clearAllMocks())

  async function loaded() {
    api.fetchDefects.mockResolvedValue(payload)
    const defects = useDefects()
    await defects.load()
    return defects
  }

  it('loads defects and their summary', async () => {
    const d = await loaded()

    expect(d.defects.value).toHaveLength(3)
    expect(d.summary.value.total).toBe(3)
  })

  it('orders signature groups by size, biggest work item first', async () => {
    const d = await loaded()

    expect(d.groups.value.map((g) => g.key)).toEqual([
      'weak_retrieval',
      '(nenhum sinal)',
    ])
  })

  it('reports the share of defects no detector caught', async () => {
    const d = await loaded()

    expect(d.blindSpotShare.value).toBe(33)
  })

  it('filters the list by signature and toggles off again', async () => {
    const d = await loaded()

    d.filterBy('weak_retrieval')
    expect(d.visible.value).toHaveLength(2)

    d.filterBy('weak_retrieval')
    expect(d.visible.value).toHaveLength(3)
  })

  it('shows everything when no filter is set', async () => {
    const d = await loaded()

    expect(d.visible.value).toHaveLength(3)
  })

  it('reports zero blind-spot share with no defects', async () => {
    api.fetchDefects.mockResolvedValue({
      summary: { total: 0, missed_by_detectors: 0, promoted: 0, by_signature: {} },
      defects: [],
    })
    const d = useDefects()
    await d.load()

    expect(d.blindSpotShare.value).toBe(0)
    expect(d.groups.value).toEqual([])
  })

  it('surfaces a failure and clears stale data', async () => {
    api.fetchDefects.mockRejectedValue(new Error('down'))
    const d = useDefects()
    await d.load()

    expect(d.error.value).toBeTruthy()
    expect(d.defects.value).toEqual([])
    expect(d.summary.value).toBeNull()
  })
})
