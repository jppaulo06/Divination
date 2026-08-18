import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  asPercent,
  SAMPLE_SIZE,
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

async function loaded(items = [item('a'), item('b', 'unflagged')]) {
  api.fetchCurationSample.mockResolvedValue(items)
  const curation = useCuration()
  await curation.draw()
  return curation
}

describe('useCuration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

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

    await curation.draw()

    expect(curation.sample.value).toEqual([])
    expect(curation.error.value).toBeTruthy()
  })
})

describe('sample persistence', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('asks for six items by default', async () => {
    api.fetchCurationSample.mockResolvedValue([item('a')])
    await useCuration().draw()

    expect(api.fetchCurationSample).toHaveBeenCalledWith({
      size: SAMPLE_SIZE,
      flaggedShare: 0.5,
    })
    expect(SAMPLE_SIZE).toBe(6)
  })

  it('draws on a first visit, when nothing is stored', async () => {
    api.fetchCurationSample.mockResolvedValue([item('a')])
    await useCuration().restore()

    expect(api.fetchCurationSample).toHaveBeenCalledTimes(1)
  })

  it('reuses the stored sample on a later visit instead of drawing again', async () => {
    const items = [item('a'), item('b', 'unflagged')]
    api.fetchCurationSample.mockResolvedValue(items)
    await useCuration().draw()
    api.fetchCurationSample.mockClear()

    // A fresh composable stands in for reopening the page.
    const revisit = useCuration()
    await revisit.restore()

    expect(api.fetchCurationSample).not.toHaveBeenCalled()
    expect(revisit.sample.value.map((i) => i.interaction_id)).toEqual([
      'a',
      'b',
    ])
  })

  it('resumes where the reviewer left off, not at the start', async () => {
    api.fetchCurationSample.mockResolvedValue([item('a'), item('b')])
    api.submitReview.mockResolvedValue(1)
    const first = useCuration()
    await first.draw()
    await first.judge(VERDICT_DEFECT)

    const revisit = useCuration()
    await revisit.restore()

    expect(revisit.index.value).toBe(1)
    expect(revisit.reviewedCount.value).toBe(1)
    expect(revisit.current.value.interaction_id).toBe('b')
  })

  it('remembers a skip too, so a skipped item is not re-offered', async () => {
    api.fetchCurationSample.mockResolvedValue([item('a'), item('b')])
    const first = useCuration()
    await first.draw()
    first.skip()

    const revisit = useCuration()
    await revisit.restore()

    expect(revisit.index.value).toBe(1)
    expect(revisit.reviewedCount.value).toBe(0)
  })

  it('replaces the stored sample when a new one is asked for', async () => {
    api.fetchCurationSample.mockResolvedValue([item('a')])
    const curation = useCuration()
    await curation.draw()
    await curation.judge(VERDICT_NOISE)

    api.fetchCurationSample.mockResolvedValue([item('z')])
    await curation.draw()

    expect(curation.sample.value[0].interaction_id).toBe('z')
    expect(curation.index.value).toBe(0)
    expect(curation.reviewedCount.value).toBe(0)

    const revisit = useCuration()
    await revisit.restore()
    expect(revisit.sample.value[0].interaction_id).toBe('z')
  })

  it('draws a fresh sample when the stored entry is corrupt', async () => {
    localStorage.setItem('divination:curation-sample', 'not json')
    api.fetchCurationSample.mockResolvedValue([item('a')])
    await useCuration().restore()

    expect(api.fetchCurationSample).toHaveBeenCalledTimes(1)
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
