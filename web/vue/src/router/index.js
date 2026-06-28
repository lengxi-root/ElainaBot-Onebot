import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { guest: true },
  },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    meta: { auth: true },
    children: [
      { path: '', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'logs', name: 'Logs', component: () => import('../views/Logs.vue') },
      { path: 'plugins', name: 'Plugins', component: () => import('../views/Plugins.vue') },
      { path: 'messages', name: 'Messages', component: () => import('../views/Messages.vue') },
      { path: 'statistics', name: 'Statistics', component: () => import('../views/Statistics.vue') },
      { path: 'market', name: 'Market', component: () => import('../views/Market.vue') },
      { path: 'update', name: 'Update', component: () => import('../views/Update.vue') },
      { path: 'database', name: 'Database', component: () => import('../views/Database.vue') },
      { path: 'config', name: 'Config', component: () => import('../views/Config.vue') },
      { path: 'custom/:key', name: 'CustomPage', component: () => import('../views/CustomPage.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory('/web/'),
  routes,
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  if (to.meta.auth && !auth.isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.meta.guest && auth.isLoggedIn) {
    next({ name: 'Dashboard' })
  } else {
    next()
  }
})

export default router
