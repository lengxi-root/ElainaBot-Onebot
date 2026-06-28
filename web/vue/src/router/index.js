import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/web/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
  },
  {
    path: '/web/',
    component: () => import('../components/Layout.vue'),
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
      },
      {
        path: 'messages',
        name: 'Messages',
        component: () => import('../views/Messages.vue'),
      },
      {
        path: 'statistics',
        name: 'Statistics',
        component: () => import('../views/Statistics.vue'),
      },
      {
        path: 'plugins',
        name: 'Plugins',
        component: () => import('../views/Plugins.vue'),
      },
      {
        path: 'modules',
        name: 'Modules',
        component: () => import('../views/Modules.vue'),
      },
      {
        path: 'logs',
        name: 'Logs',
        component: () => import('../views/Logs.vue'),
      },
      {
        path: 'config',
        name: 'Config',
        component: () => import('../views/Config.vue'),
      },
      {
        path: 'database',
        name: 'Database',
        component: () => import('../views/Database.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('elaina_token')
  const urlToken = new URLSearchParams(window.location.search).get('token')
  if (urlToken) {
    localStorage.setItem('elaina_token', urlToken)
    next()
    return
  }
  if (to.name !== 'Login' && !token) {
    next({ name: 'Login' })
  } else {
    next()
  }
})

export default router
