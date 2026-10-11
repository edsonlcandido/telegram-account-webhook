---
name: vue-router-auth
description: Adicionar e proteger rotas Vue Router no padrão do template — `meta: { requiresAuth | requiresGuest }`, base path `/app/`, guard que chama `pb.collection('users').authRefresh()`. Use quando o usuário quiser criar nova página, painel protegido, fluxo de onboarding ou redirecionamento por papel/role.
---

# Vue Router — Padrão de Rotas com Auth

Configuração fica em `apps/web/src/router/index.ts`. Web app é montado em `/app/` (por causa do `base: '/app/'` do Vite + hook do PB).

## Rotas existentes

| Path         | Nome       | Meta                     |
|--------------|------------|--------------------------|
| `/`          | (redirect) | → `/dashboard`           |
| `/login`     | `login`    | `requiresGuest: true`    |
| `/dashboard` | `dashboard`| `requiresAuth: true`     |

## Adicionar uma rota nova (protegida)

Edite `apps/web/src/router/index.ts`:

```ts
import PostsView from '../views/PostsView.vue'

const router = createRouter({
  history: createWebHistory('/app/'),
  routes: [
    // ... existentes
    {
      path: '/posts',
      name: 'posts',
      component: PostsView,
      meta: { requiresAuth: true },
    },
    {
      path: '/posts/:id',
      name: 'post-detail',
      component: PostDetailView,
      meta: { requiresAuth: true },
      props: true,                  // injeta :id como prop
    },
  ],
})
```

## Rota para visitantes (login/registro/onboarding)

```ts
{
  path: '/onboarding',
  name: 'onboarding',
  component: OnboardingView,
  meta: { requiresGuest: true },
}
```

## Rota pública (sem checagem)

```ts
{
  path: '/about',
  name: 'about',
  component: AboutView,
  // sem meta -> passa direto
}
```

## Guard já configurado

```ts
router.beforeEach(async (to, _from, next) => {
  let isAuthenticated = pb.authStore.isValid && !!pb.authStore.model
  if (to.meta.requiresAuth && isAuthenticated) {
    try {
      await pb.collection('users').authRefresh()
    } catch {
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
```

> **Não duplicar esse guard.** Para lógica nova (ex: checar role), criar **beforeEach adicional** ou estender `to.meta` com checagem customizada (ver abaixo).

## Extendendo o guard pra checar papel/role

Padrão recomendado — adicionar helper sem quebrar o template:

```ts
// apps/web/src/router/index.ts (continuação)
router.beforeEach(async (to, _from) => {
  const required = to.meta.requiredRole as string | undefined
  if (!required) return true

  const user = pb.authStore.model
  if (!user) return { path: '/login' }
  // ajuste conforme o schema da sua collection users
  if ((user as any).role !== required) return { path: '/dashboard' }
})

// na rota:
{ path: '/admin', name: 'admin', component: AdminView, meta: { requiresAuth: true, requiredRole: 'admin' } }
```

## Navegação programática

```ts
import { useRouter } from 'vue-router'
const router = useRouter()
router.push('/dashboard')
router.push({ name: 'post-detail', params: { id: '123' } })
router.replace('/login')   // não empilha histórico
```

## Lazy loading (recomendado pra apps com >5 páginas)

```ts
{
  path: '/posts',
  name: 'posts',
  component: () => import('../views/PostsView.vue'),
  meta: { requiresAuth: true },
}
```

Mantém o bundle inicial leve — Vite cria chunks por rota automaticamente.

## Layouts aninhados (opcional)

```ts
{
  path: '/',
  component: () => import('../layouts/AuthLayout.vue'),
  meta: { requiresAuth: true },
  children: [
    { path: 'dashboard', name: 'dashboard', component: DashboardView },
    { path: 'posts',     name: 'posts',     component: () => import('../views/PostsView.vue') },
  ],
}
```

> ⚠️ Se usar nested routes, ajustar redirecionamento: `redirect: '/dashboard'` continua funcionando (vai pra `children[0]`).

## 404

```ts
{ path: '/:pathMatch(.*)*', name: 'not-found', component: NotFoundView }
```

## Checklist

- Path **sem** `/app/` — o base path cuida disso
- `meta.requiresAuth` em qualquer rota que toque dados do user
- `meta.requiresGuest` em login/registro
- Página nova dentro de `apps/web/src/views/`
- Carregamento lazy quando a view for grande (>50 linhas / múltiplos componentes)
- Testar logout: o guard deve redirecionar pra `/login` ao tentar entrar em rota protegida
