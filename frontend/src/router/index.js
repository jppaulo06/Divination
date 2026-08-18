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
      path: '/monitoring',
      name: 'monitoring',
      // Loaded on demand: the dashboard is an operator surface, and most
      // visits to the app never open it.
      component: () => import('../views/MonitoringView.vue'),
    },
  ],
})

export default router
