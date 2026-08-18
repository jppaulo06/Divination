import { describe, expect, it } from 'vitest'

import router from '@/router'

/**
 * Redirects only resolve during navigation, not in router.resolve(), so
 * these push for real and read back where they landed.
 */
async function land(path) {
  await router.push(path)
  await router.isReady()
  return router.currentRoute.value
}

describe('admin routing', () => {
  it('nests every admin page under /admin', () => {
    expect(router.resolve('/admin/monitoring').name).toBe('admin-monitoring')
    expect(router.resolve('/admin/curation/sampling').name).toBe(
      'curation-sampling',
    )
    expect(router.resolve('/admin/curation/defects').name).toBe(
      'curation-defects',
    )
  })

  it('sends /admin to monitoring', async () => {
    expect((await land('/admin')).name).toBe('admin-monitoring')
  })

  it('sends the curation section to its sampling page', async () => {
    // "Curadoria" is a sidebar group rather than a page of its own.
    expect((await land('/admin/curation')).name).toBe('curation-sampling')
  })

  it.each([
    ['/monitoring', 'admin-monitoring'],
    ['/curation', 'curation-sampling'],
    ['/defects', 'curation-defects'],
  ])('keeps the old link %s working', async (path, name) => {
    expect((await land(path)).name).toBe(name)
  })

  it('renders admin pages inside the shared layout', () => {
    const matched = router.resolve('/admin/curation/defects').matched
    expect(matched).toHaveLength(2)
    expect(matched[0].path).toBe('/admin')
  })

  it('leaves the chat outside the admin shell', async () => {
    const route = await land('/')
    expect(route.name).toBe('home')
    expect(route.matched).toHaveLength(1)
  })
})
