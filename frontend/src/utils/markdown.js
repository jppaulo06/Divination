import DOMPurify from 'dompurify'
import { marked } from 'marked'

marked.setOptions({ gfm: true, breaks: true })

// Anything the model emits is untrusted input by the time it reaches the
// DOM, so parsed markdown is sanitised before it is ever bound with
// v-html. External links additionally get noopener to avoid tabnabbing.
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A' && node.getAttribute('href')) {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

const ALLOWED_TAGS = [
  'p', 'br', 'hr', 'strong', 'em', 'del', 'blockquote',
  'ul', 'ol', 'li', 'code', 'pre', 'a', 'span',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'table', 'thead', 'tbody', 'tr', 'th', 'td',
]

/** Renders assistant markdown into HTML that is safe to bind. */
export function renderMarkdown(source) {
  if (!source) return ''
  const html = marked.parse(String(source))
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR: ['href', 'title', 'target', 'rel', 'align'],
  })
}

/**
 * Flattens markdown to a single line of plain text, for places that need
 * a label rather than a document (sidebar previews, tooltips).
 */
export function toPlainText(source) {
  if (!source) return ''
  const stripped = DOMPurify.sanitize(marked.parse(String(source)), {
    ALLOWED_TAGS: [],
    ALLOWED_ATTR: [],
  })
  const decoded = new DOMParser().parseFromString(stripped, 'text/html')
  return (decoded.body.textContent || '').replace(/\s+/g, ' ').trim()
}
