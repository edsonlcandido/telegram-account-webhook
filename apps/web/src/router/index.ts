import { createRouter, createWebHistory } from 'vue-router'
import pb from '../services/pocketbase'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import AddTelegramView from '../views/AddTelegramView.vue'
import WebhooksListView from '../views/WebhooksListView.vue'
import ApiDocsView from '../views/ApiDocsView.vue'
import MessagesView from '../views/MessagesView.vue'

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
      meta: { requiresGuest: true, title: 'Login' },
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: DashboardView,
      meta: { requiresAuth: true, title: 'Dashboard' },
    },
    {
      path: '/add-telegram',
      name: 'add-telegram',
      component: AddTelegramView,
      meta: { requiresAuth: true, title: 'Adicionar Conta' },
    },
    {
      // Legacy: /webhook/:sessionId → redireciona pra /webhooks/:sessionId
      path: '/webhook/:sessionId',
      redirect: (to) => `/webhooks/${to.params.sessionId}`,
    },
    {
      path: '/webhooks/:sessionId',
      name: 'webhooks-list',
      component: WebhooksListView,
      meta: { requiresAuth: true, title: 'Webhooks' },
      props: true,
    },
    {
      path: '/docs',
      name: 'api-docs',
      component: ApiDocsView,
      meta: { requiresAuth: true, title: 'Documentação da API' },
    },
    {
      // Lista de mensagens estilo Telegram Web. `sessionId` é opcional —
      // sem ele, a view mostra um seletor de conta no header.
      path: '/messages/:sessionId?',
      name: 'messages',
      component: MessagesView,
      meta: { requiresAuth: true, title: 'Mensagens' },
      props: true,
    },
  ],
})

// Título do app (aba do navegador). O index.html usa o mesmo nome.
const APP_TITLE = 'Telegram Webhook'

router.afterEach((to) => {
  const pageTitle = typeof to.meta.title === 'string' ? to.meta.title : ''
  document.title = pageTitle ? `${pageTitle} · ${APP_TITLE}` : APP_TITLE
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
