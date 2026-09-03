import { describe, expect, it } from 'vitest'

import { signalDetail, signalLabel } from '@/composables/useMonitoring'

const signal = (type, details) => ({ type, details })

describe('signalLabel', () => {
  it('translates a known signal type', () => {
    expect(signalLabel('weak_retrieval')).toBe('Retrieval fraco')
  })

  it('falls back to the raw type', () => {
    expect(signalLabel('brand_new_detector')).toBe('brand_new_detector')
  })
})

describe('signalDetail', () => {
  it('quotes the scores behind weak retrieval', () => {
    const text = signalDetail(
      signal('weak_retrieval', {
        top_score: 0.6315611,
        threshold: 0.7,
        chunk_count: 4,
      }),
    )

    expect(text).toBe('Melhor trecho 0.63, abaixo do limite 0.70 (4 trechos).')
  })

  it('reports retrieval that returned nothing', () => {
    const text = signalDetail(
      signal('weak_retrieval', { reason: 'no chunks retrieved', threshold: 0.7 }),
    )

    expect(text).toBe('Nenhum trecho recuperado.')
  })

  it('lists the exact values missing from context', () => {
    const text = signalDetail(
      signal('unsupported_claim', {
        unsupported_dice: ['2d6', '1d8'],
        unsupported_dcs: ['15'],
      }),
    )

    expect(text).toBe('Sem apoio no contexto: 2d6, 1d8, 15.')
  })

  it('quotes the hedging phrases', () => {
    const text = signalDetail(
      signal('refusal_or_hedge', {
        matches: ['contexto fornecido não', 'seria necessário consultar'],
      }),
    )

    expect(text).toContain('“contexto fornecido não”')
    expect(text).toContain('“seria necessário consultar”')
  })

  it('names the missing closing', () => {
    const text = signalDetail(
      signal('format_guardrail_violation', {
        required_closing: 'Free Rules (2024)',
        answer_tail: '...',
      }),
    )

    expect(text).toBe('Não termina com “Free Rules (2024)”.')
  })

  it('reports an empty answer', () => {
    expect(
      signalDetail(signal('format_guardrail_violation', { reason: 'empty answer' })),
    ).toBe('Resposta vazia.')
  })

  it('shows which earlier question was repeated', () => {
    const text = signalDetail(
      signal('repeated_question', {
        similarity: 0.833,
        threshold: 0.6,
        prior_question: 'Quanto dano causa bola de fogo?',
      }),
    )

    expect(text).toBe('83% semelhante a “Quanto dano causa bola de fogo?”.')
  })

  it('does not repeat the comment already shown as feedback', () => {
    const text = signalDetail(
      signal('user_negative_feedback', { rating: -1, comment: 'não cobriu' }),
    )

    expect(text).toBe('O usuário avaliou esta resposta como ruim.')
    expect(text).not.toContain('não cobriu')
  })

  it('returns nothing for a signal it cannot describe', () => {
    expect(signalDetail(signal('brand_new_detector', { x: 1 }))).toBe('')
    expect(signalDetail(signal('unsupported_claim', {}))).toBe('')
    expect(signalDetail(signal('refusal_or_hedge', {}))).toBe('')
  })

  it('survives a signal with no details at all', () => {
    expect(signalDetail({ type: 'refusal_or_hedge' })).toBe('')
    expect(signalDetail(undefined)).toBe('')
  })
})
