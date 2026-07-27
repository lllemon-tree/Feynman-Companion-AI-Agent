import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/upload',
    name: 'Upload',
    component: () => import('@/views/UploadPage.vue')
  },
  {
    path: '/select',
    name: 'Select',
    component: () => import('@/views/SelectPage.vue')
  },
  {
    path: '/home',
    name: 'Chat',
    component: () => import('@/views/ChatView.vue')
  },
  {
    path: '/knowledge',
    name: 'Knowledge',
    component: () => import('@/views/KnowledgePage.vue')
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

export default router
