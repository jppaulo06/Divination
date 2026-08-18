import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      // Everything operator-facing shares one shell, so navigation lives
      // in the sidebar instead of each page linking to the next.
      path: '/admin',
      component: () => import('../components/admin/AdminLayout.vue'),
      children: [
        { path: '', redirect: { name: 'admin-monitoring' } },
        {
          path: 'monitoring',
          name: 'admin-monitoring',
          component: () => import('../views/MonitoringView.vue'),
        },
        { path: 'curation', redirect: { name: 'curation-sampling' } },
        {
          path: 'curation/sampling',
          name: 'curation-sampling',
          component: () => import('../views/CurationView.vue'),
        },
        {
          path: 'curation/defects',
          name: 'curation-defects',
          component: () => import('../views/DefectsView.vue'),
        },
      ],
    },
    // The admin pages lived at the top level first; keep those links
    // working rather than breaking bookmarks.
    { path: '/monitoring', redirect: { name: 'admin-monitoring' } },
    { path: '/curation', redirect: { name: 'curation-sampling' } },
    { path: '/defects', redirect: { name: 'curation-defects' } },
  ],
})

export default router
