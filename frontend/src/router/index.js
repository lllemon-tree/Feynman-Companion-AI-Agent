import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/AuthPage.vue'),
    meta: { public: true }
  },
  {
    path: '/upload',
    name: 'Upload',
    component: () => import('@/views/UploadPage.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/select',
    name: 'Select',
    component: () => import('@/views/SelectPage.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/home',
    name: 'Chat',
    component: () => import('@/views/ChatView.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('@/views/KnowledgePage.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/views/ProfilePage.vue'),
    meta: { requiresAuth: true }
  },
  {
    path: '/',
    redirect: '/upload'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  if (to.meta.public) {
    return next()
  }

  const token = localStorage.getItem('feynman_token')
  const userStr = localStorage.getItem('feynman_user')
  const isLoggedIn = token && userStr

  if (isLoggedIn) {
    return next()
  }

  const isGuest = localStorage.getItem('feynman_guest') === 'true'
  if (isGuest) {
    return next()
  }

  next({ path: '/login', query: { redirect: to.fullPath } })
})

export default router
