import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  asPercent,
  useCuration,
  VERDICT_DEFECT,
  VERDICT_NOISE,
} from '@/composables/useCuration'
import * as api from '@/services/api'

vi.mock('@/services/api', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    fetchCurationSample: vi.fn(),
    fetchCurationStats: vi.fn(),
    submitReview: vi.fn(),
  }
})

const item = (id, stratum = 'flagged') => ({
  interaction_id: id,
  stratum,
  question: 'q',
  answer: 'a',
  signals: [],
  feedback: [],
  retrieval_context: [],
  thread: [],
  top_score: 0.6,
  latency_ms: 100,
})

const stats = (overrides = {}) => ({
  flagged: { pool: 4, reviewed: 1, defects: 1 },
  unflagged: { pool: 8, reviewed: 1, defects: 0 },
  precision: 1,
  estimated_recall: 1,
  ...overrides,
})

async function loaded(items = [item('a'), item('b', 'unflagged')]) {
  api.fetchCurationSample.mockResolvedValue(items)
  api.fetchCurationStats.mockResolvedValue(stats())
  const curation = useCuration()
  await curation.load()
  return curation
}

describe('useCuration', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads a sample and starts on the first item', async () => {
    const curation = await loaded()

    expect(curation.current.value.interaction_id).toBe('a')
    expect(curation.sample.value).toHaveLength(2)
  })

  it('hides signals until the reviewer asks', async () => {
    const curation = await loaded()

    expect(curation.signalsRevealed.value).toBe(false)
    curation.revealSignals()
    expect(curation.signalsRevealed.value).toBe(true)
  })

  it('records a verdict and advances', async () => {
    api.submitReview.mockResolvedValue(1)
    const curation = await loaded()

    await curation.judge(VERDICT_DEFECT)

    expect(api.submitReview).toHaveBeenCalledWith({
      interactionId: 'a',
      verdict: VERDICT_DEFECT,
      rationale: null,
    })
    expect(curation.current.value.interaction_id).toBe('b')
    expect(curation.reviewedCount.value).toBe(1)
  })

  it('sends a rationale when one was typed', async () => {
    api.submitReview.mockResolvedValue(1)
    const curation = await loaded()
    curation.rationale.value = '  inventou o dano  '

    await curation.judge(VERDICT_NOISE)

    expect(api.submitReview).toHaveBeenCalledWith({
      interactionId: 'a',
      verdict: VERDICT_NOISE,
      rationale: 'inventou o dano',
    })
  })

  it('clears the rationale and re-hides signals between items', async () => {
    api.submitReview.mockResolvedValue(1)
    const curation = await loaded()
    curation.rationale.value = 'algo'
    curation.revealSignals()

    await curation.judge(VERDICT_NOISE)

    expect(curation.rationale.value).toBe('')
    expect(curation.signalsRevealed.value).toBe(false)
  })

  it('refreshes the metrics after each verdict', async () => {
    api.submitReview.mockResolvedValue(1)
    const curation = await loaded()
    api.fetchCurationStats.mockResolvedValue(stats({ precision: 0.5 }))

    await curation.judge(VERDICT_DEFECT)

    expect(curation.stats.value.precision).toBe(0.5)
  })

  it('stays on the item when saving fails', async () => {
    api.submitReview.mockRejectedValue(new Error('down'))
    const curation = await loaded()

    await curation.judge(VERDICT_DEFECT)

    expect(curation.current.value.interaction_id).toBe('a')
    expect(curation.error.value).toBeTruthy()
    expect(curation.reviewedCount.value).toBe(0)
  })

  it('skips without recording anything', async () => {
    const curation = await loaded()

    curation.skip()

    expect(api.submitReview).not.toHaveBeenCalled()
    expect(curation.current.value.interaction_id).toBe('b')
  })

  it('reports the sample as done at the end', async () => {
    const curation = await loaded([item('only')])

    curation.skip()

    expect(curation.isDone.value).toBe(true)
    expect(curation.current.value).toBeNull()
  })

  it('surfaces a load failure and leaves no sample', async () => {
    api.fetchCurationSample.mockRejectedValue(new Error('boom'))
    const curation = useCuration()

    await curation.load()

    expect(curation.sample.value).toEqual([])
    expect(curation.error.value).toBeTruthy()
  })
})

describe('asPercent', () => {
  it('renders a fraction as a percentage', () => {
    expect(asPercent(0.75)).toBe('75%')
  })

  it('renders a dash when the metric is not computable yet', () => {
    // Recall stays null until both strata have been reviewed.
    expect(asPercent(null)).toBe('—')
    expect(asPercent(undefined)).toBe('—')
  })
})
