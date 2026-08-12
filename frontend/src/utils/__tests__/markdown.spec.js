import { describe, expect, it } from 'vitest'

import { renderMarkdown, toPlainText } from '@/utils/markdown'

describe('renderMarkdown', () => {
  it('renders common markdown structures', () => {
    const html = renderMarkdown('# Título\n\n- um\n- dois\n\n**forte**')

    expect(html).toContain('<h1>Título</h1>')
    expect(html).toContain('<li>um</li>')
    expect(html).toContain('<strong>forte</strong>')
  })

  it('renders tables, which rules answers use heavily', () => {
    const html = renderMarkdown('| Nível | Dano |\n| --- | --- |\n| 1 | 1d6 |')

    expect(html).toContain('<table>')
    expect(html).toContain('<th>Nível</th>')
    expect(html).toContain('<td>1d6</td>')
  })

  it('strips script tags', () => {
    const html = renderMarkdown('antes <script>alert(1)</script> depois')

    expect(html).not.toContain('<script')
    expect(html).not.toContain('alert(1)')
  })

  it('strips inline event handlers', () => {
    const html = renderMarkdown('<img src=x onerror="alert(1)">')

    expect(html).not.toContain('onerror')
  })

  it('drops javascript: URLs', () => {
    const html = renderMarkdown('[clique](javascript:alert(1))')

    expect(html).not.toContain('javascript:')
  })

  it('hardens external links against tabnabbing', () => {
    const html = renderMarkdown('[regras](https://example.com)')

    expect(html).toContain('rel="noopener noreferrer"')
    expect(html).toContain('target="_blank"')
  })

  it('returns an empty string for empty input', () => {
    expect(renderMarkdown('')).toBe('')
    expect(renderMarkdown(null)).toBe('')
    expect(renderMarkdown(undefined)).toBe('')
  })
})

describe('toPlainText', () => {
  it('flattens markdown to a single line', () => {
    expect(toPlainText('# Título\n\nUm **parágrafo**.')).toBe(
      'Título Um parágrafo.',
    )
  })

  it('removes markup entirely', () => {
    expect(toPlainText('<p>oi</p><script>alert(1)</script>')).toBe('oi')
  })

  it('decodes entities rather than leaking them into labels', () => {
    expect(toPlainText('Regras de D&amp;D')).toBe('Regras de D&D')
  })

  it('handles empty input', () => {
    expect(toPlainText('')).toBe('')
    expect(toPlainText(null)).toBe('')
  })
})
