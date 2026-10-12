import { createRouter, createWebHistory } from 'vue-router'
import pb from '../services/pocketbase'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import AddTelegramView from '../views/AddTelegramView.vue'
import WebhookConfigView from '../views/WebhookConfigView.vue'

const router = createRouter({
  history: createWebHistory('/app/'),
  routes: [
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { requiresGuest: true },
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardView,
      meta: { requiresAuth: true },
    },
    {
      path: '/add-telegram',
      name: 'add-telegram',
      component: AddTelegramView,
      meta: { requiresAuth: true },
    },
    {
      path: '/webhook/:sessionId',
      name: 'webhook-config',
      component: WebhookConfigView,
      meta: { requiresAuth: true },
      props: true,
    },
  ],
})

// Navigation guard - verifica a autenticação com o servidor
router.beforeEach(async (to, _from, next) => {
  let isAuthenticated = pb.authStore.isValid && !!pb.authStore.model

  // Para rotas que requerem autenticação, verifica com o servidor
  if (to.meta.requiresAuth && isAuthenticated) {
    try {
      await pb.collection('users').authRefresh()
    } catch (error) {
      // Token inválido ou usuário não existe mais
      pb.authStore.clear()
      isAuthenticated = false
    }
  }

  if (to.meta.requiresAuth && !isAuthenticated) {
    next('/login')
  } else if (to.meta.requiresGuest && isAuthenticated) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
