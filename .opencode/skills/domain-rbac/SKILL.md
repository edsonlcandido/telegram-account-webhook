---
name: domain-rbac
description: Como implementar RBAC (Role-Based Access Control) granular no template — roles, permissions por ação, gating no front + back, middleware, superadmin bootstrap. Use quando o usuário quiser múltiplos papéis (admin/editor/viewer), permissions por feature, multi-team com papéis diferentes, ou restringir acesso a áreas do app.
---

# Domínio — RBAC (Roles & Permissions)

PocketBase não tem RBAC pronto. Mas o template já tem `auth.ts` que suporta `user.role`. Esta skill monta o sistema inteiro.

## Modelo

```
users (1) ─── role (text: admin | manager | member)
teams (opcional)
team_members (N:N)
permissions (json array em user OU derivada de role)
```

Roles típicos:
- `admin` — tudo
- `manager` — gerencia o próprio time
- `member` — vê/edita só seus dados
- `viewer` — read-only

## 1. Adicionar `role` à collection `users`

```js
// pb_migrations/1700000000_user_role.js
/// <reference path="../pb_data/types.d.ts" />

const users = $app.dao().findCollectionByNameOrId('users')
users.schema.add(new Field({
  name: 'role', type: 'select', required: true,
  options: { maxSelect: 1, values: ['admin', 'manager', 'member', 'viewer'] },
}))
users.schema.add(new Field({
  name: 'team', type: 'relation', collectionId: 'teams', maxSelect: 1,
}))
$app.dao().saveCollection(users)
```

Hook garante que novos users são `member` por default e só admin pode criar admin:

```js
// pb_hooks/users.pb.js
onRecordBeforeCreateRequest((e) => {
  if (e.collection.name !== 'users') return
  const role = e.record.getString('role') || 'member'
  // só admin pode criar admin/manager
  if ((role === 'admin' || role === 'manager') && !e.auth?.isAdmin) {
    throw new BadRequestError('Permissão insuficiente pra criar com role ' + role)
  }
  e.record.set('role', role)
}, $app)

onRecordBeforeUpdateRequest((e) => {
  if (e.collection.name !== 'users') return
  // proteger admin original
  if (e.auth?.id === e.record.id) return  // pode editar próprio perfil
  if (!e.auth?.isAdmin) {
    // ninguém mais pode mexer em role
    e.record.set('role', e.record.original().getString('role'))
  }
}, $app)
```

## 2. Helper de permissão

### `apps/web/src/composables/usePermissions.ts`

```ts
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

export type Role = 'admin' | 'manager' | 'member' | 'viewer'
export type Action = 'view' | 'create' | 'update' | 'delete' | 'export' | 'admin'

// matriz simples
const MATRIX: Record<Role, Action[]> = {
  admin:   ['view', 'create', 'update', 'delete', 'export', 'admin'],
  manager: ['view', 'create', 'update', 'delete', 'export'],
  member:  ['view', 'create', 'update'],
  viewer:  ['view'],
}

export function usePermissions() {
  const auth = useAuthStore()
  const role = computed<Role>(() => (auth.user?.role as Role) || 'viewer')

  function can(action: Action, ctx?: { ownerId?: string }): boolean {
    const allowed = MATRIX[role.value] || []
    if (!allowed.includes(action)) return false

    // member: só age no próprio recurso
    if (role.value === 'member' && action !== 'view' && ctx?.ownerId && ctx.ownerId !== auth.user?.id) {
      return false
    }
    return true
  }

  // helper pra collections com owner field
  function canEditRecord(record: any): boolean {
    return can('update', { ownerId: record.owner })
  }

  function isAdmin()    { return role.value === 'admin' }
  function isManager()  { return role.value === 'admin' || role.value === 'manager' }
  function isMember()   { return !!auth.user && !isAdmin() }

  return { role, can, canEditRecord, isAdmin, isManager, isMember }
}
```

## 3. Uso em componentes

### Botão condicional

```vue
<script setup lang="ts">
import { usePermissions } from '@/composables/usePermissions'
const perm = usePermissions()
</script>

<template>
  <button v-if="perm.can('delete', { ownerId: lead.owner })"
    @click="deleteLead"
    class="px-4 py-2 bg-red-600 text-white rounded-lg">
    Excluir
  </button>
</template>
```

### Diretiva custom `v-can`

```ts
// directives/can.ts
import type { Directive } from 'vue'
import { useAuthStore } from '@/stores/auth'

export const vCan: Directive<HTMLElement, { action: string; ownerId?: string }> = {
  mounted(el, binding) {
    const auth = useAuthStore()
    const role = auth.user?.role || 'viewer'
    // reutilize a matriz aqui
    const allowed = {
      admin:   ['view','create','update','delete','export','admin'],
      manager: ['view','create','update','delete','export'],
      member:  ['view','create','update'],
      viewer:  ['view'],
    }[role] || []

    const ok = allowed.includes(binding.value.action)
      && !(role === 'member' && binding.value.ownerId && binding.value.ownerId !== auth.user?.id)

    if (!ok) el.style.display = 'none'
  },
}
```

```ts
// main.ts
app.directive('can', vCan)
```

```vue
<button v-can="{ action: 'delete', ownerId: lead.owner }">Excluir</button>
```

## 4. Router guard com role

```ts
// apps/web/src/router/index.ts
import pb from '../services/pocketbase'
import { useAuthStore } from '../stores/auth'

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  const user = auth.user || pb.authStore.model

  const requiredRole = to.meta.requiredRole as string | undefined
  if (requiredRole && user) {
    const hierarchy = ['viewer', 'member', 'manager', 'admin']
    const userLevel  = hierarchy.indexOf(user.role)
    const needed     = hierarchy.indexOf(requiredRole)
    if (userLevel < needed) return next({ name: 'forbidden' })
  }

  // guard padrão do template (requiresAuth/requiresGuest) ...
  next()
})

// rota
{
  path: '/admin',
  name: 'admin',
  component: AdminView,
  meta: { requiresAuth: true, requiredRole: 'admin' },
}
{
  path: '/403',
  name: 'forbidden',
  component: ForbiddenView,
}
```

## 5. Pinia store admin de users

```ts
// stores/admin-users.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import pb from '@/services/pocketbase'

export const useAdminUsersStore = defineStore('admin-users', () => {
  const items = ref<any[]>([])
  const loading = ref(false)

  async function fetchAll() {
    loading.value = true
    try {
      items.value = (await pb.collection('users').getList(1, 200, { sort: 'email' })).items
    } finally { loading.value = false }
  }

  async function changeRole(id: string, role: string) {
    await pb.collection('users').update(id, { role })
    await fetchAll()
  }

  async function remove(id: string) {
    await pb.collection('users').delete(id)
    items.value = items.value.filter(u => u.id !== id)
  }

  return { items, loading, fetchAll, changeRole, remove }
})
```

## 6. Backend — regras de acesso por collection

No admin `/_/`, defina regras dinâmicas que consultam `@request.auth.role`:

```
leads:
  listRule:   "@request.auth.role = 'admin' || owner = @request.auth.id"
  viewRule:   "@request.auth.role = 'admin' || owner = @request.auth.id"
  createRule: "@request.auth.role != '' && @request.auth.role != 'viewer'"
  updateRule: "@request.auth.role = 'admin' || owner = @request.auth.id"
  deleteRule: "@request.auth.role = 'admin' || owner = @request.auth.id"
```

> ⚠️ Admin PB (`isAdmin`) é **separado** do role. O `isAdmin` é setado direto no DB. Use-o para superadons.

## 7. Multi-team (avançado)

### Schema

```js
// teams
{ name: 'name', type: 'text' }

// team_members
{
  name: 'team', type: 'relation', collectionId: 'teams', maxSelect: 1 },
  name: 'user', type: 'relation', collectionId: '_pb_users_auth_', maxSelect: 1 },
  name: 'role', type: 'select', options: { maxSelect: 1, values: ['owner', 'admin', 'member'] },
}
```

### Regras pra multi-team

```
leads.listRule: "@request.auth.id != '' && team = @request.auth.team"
```

(set `team` em `users` no signup)

### Helper

```ts
function isTeamAdmin(): boolean {
  const me = pb.authStore.model
  if (!me?.team) return false
  try {
    const tm = pb.collection('team_members').getFirstListItem(
      `team = "${me.team}" && user = "${me.id}"`
    )
    return ['owner', 'admin'].includes(tm.role)
  } catch { return false }
}
```

## 8. Superadmin bootstrap (1º usuário)

```js
// pb_hooks/bootstrap.pb.js
onBootstrap((e) => {
  const count = $app.dao().findRecordsByFilter('_pb_users_auth_', '', '', 1, 0).length
  if (count === 0) {
    console.log('🚀 primeiro start — nenhum user ainda. Crie seu admin em /_/')
  }
}, $app)

// alternativa: hook que promove o primeiro user a admin
onRecordAfterCreateRequest((e) => {
  if (e.collection.name !== 'users') return
  const total = $app.dao().findRecordsByFilter('_pb_users_auth_', '', '', 9999, 0).length
  if (total === 1) {
    const rec = $app.dao().findRecordById('_pb_users_auth_', e.record.id)
    $app.dao().saveRecord(rec.set('role', 'admin'))
  }
}, $app)
```

## 9. View admin de users

```vue
<!-- views/admin/AdminUsersView.vue -->
<script setup lang="ts">
import { onMounted } from 'vue'
import { useAdminUsersStore } from '@/stores/admin-users'
import { usePermissions } from '@/composables/usePermissions'

const admin = useAdminUsersStore()
const perm = usePermissions()
onMounted(() => admin.fetchAll())

async function setRole(u: any, role: string) {
  if (!perm.isAdmin()) { alert('Sem permissão'); return }
  if (confirm(`Mudar role de ${u.email} pra ${role}?`)) await admin.changeRole(u.id, role)
}
</script>

<template>
  <div class="p-6">
    <h1 class="text-3xl font-bold mb-6">Usuários</h1>
    <table class="w-full bg-white rounded-2xl shadow-lg overflow-hidden">
      <thead class="bg-gray-50">
        <tr>
          <th class="text-left p-3">Email</th>
          <th class="text-left p-3">Nome</th>
          <th class="text-left p-3">Role</th>
          <th class="text-right p-3">Ações</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in admin.items" :key="u.id" class="border-t">
          <td class="p-3">{{ u.email }}</td>
          <td class="p-3">{{ u.name }}</td>
          <td class="p-3">
            <select :value="u.role" @change="(e) => setRole(u, (e.target as HTMLSelectElement).value)"
              class="border rounded px-2 py-1">
              <option>admin</option><option>manager</option>
              <option>member</option><option>viewer</option>
            </select>
          </td>
          <td class="p-3 text-right">
            <button v-if="perm.isAdmin() && u.id !== auth.user?.id"
              @click="admin.remove(u.id)"
              class="text-red-600 hover:underline">Excluir</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
```

## Auditoria (opcional)

```js
// collection audit_log
{
  name: 'user', type: 'relation', collectionId: '_pb_users_auth_' },
  name: 'action', type: 'text' },     // 'lead.create', 'role.change'
  name: 'target_id', type: 'text' },
  name: 'metadata', type: 'json' },
  name: 'ip', type: 'text' },
  name: 'at', type: 'date' },
}
```

```js
// helper
function audit(action, targetId, metadata = {}) {
  $app.dao().saveRecord(new Record($app.findCollectionByNameOrId('audit_log'), {
    user: $app.authStore().model()?.id,
    action, target_id: targetId, metadata,
    ip: '', // ver request info via hook param
    at: new Date().toISOString(),
  }))
}

// chamar de qualquer hook
onRecordAfterUpdateRequest((e) => {
  if (e.collection.name !== 'users') return
  if (e.record.getString('role') !== e.record.original().getString('role')) {
    audit('user.role.change', e.record.id, {
      from: e.record.original().getString('role'),
      to:   e.record.getString('role'),
    })
  }
}, $app)
```

## Checklist

- [ ] Migration adicionando `role` em `users`
- [ ] Hook de bootstrap (admin ganha role no 1º user)
- [ ] `usePermissions` composable + matriz
- [ ] Diretiva `v-can` (opcional)
- [ ] Router guard `requiredRole`
- [ ] Regras de acesso por collection considerando role
- [ ] View admin `/admin/users` com `isAdmin` check
- [ ] Audit log de mudanças sensíveis
- [ ] Plano B se frontend for burlado: **nunca confie só no front** — regras no PB são a fonte da verdade