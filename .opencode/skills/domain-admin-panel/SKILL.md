---
name: domain-admin-panel
description: Como adicionar um painel admin completo no template — bootstrap do 1º super admin, UI de gerenciamento de usuários (CRUD), convite por email, reset de senha forçado, atribuição de roles e audit log. Use quando o usuário quiser criar SaaS multi-user, vender o template como produto, ou precisar de uma área administrativa que não dependa do PB admin UI `/_/`.
---

# Domínio — Admin Panel (gerenciamento de usuários)

Caso real: você vai vender um SaaS feito com este template. O cliente final **não pode ter acesso** ao `/_/` do PocketBase (é admin de infra, não de produto). Precisa de uma UI linda, dentro do app, pra:

- Criar usuários manualmente
- Convidar por email (com link de ativação)
- Resetar senha alheia
- Atribuir roles
- Ver audit log

Esta skill cobre **o gap** que o template original tem: tudo de auth/user CRUD hoje depende do admin PB nativo.

## Visão do domínio

```
users (existente)         invites                audit_log
───────────────         ────────                ─────────
... (campos base)        id                      id
role                     email                   actor_id → users
status (active/          token (random)          actor_email (snapshot)
         invited/        role                    action (user.create,
         suspended)      invited_by → users               user.role.change,
team (relation)          expires_at                       user.suspend,
created_by → users       accepted_at                       auth.login)
updated_by → users       status (pending/                target_id
                         accepted/expired)    target_email (snapshot)
                                              metadata (json)
                                              ip, user_agent
                                              created
```

## 1. Estender a collection `users`

### Migration

```js
// pocketbase/pb_migrations/1700000000_admin_panel.js
/// <reference path="../pb_data/types.d.ts" />

const users = $app.dao().findCollectionByNameOrId('users')

users.schema.add(new Field({ name: 'status', type: 'select', required: true,
  options: { maxSelect: 1, values: ['active', 'invited', 'suspended'] } }))
users.schema.add(new Field({ name: 'last_login_at', type: 'date' }))
users.schema.add(new Field({ name: 'last_login_ip', type: 'text', max: 64 }))
users.schema.add(new Field({ name: 'created_by', type: 'relation', collectionId: '_pb_users_auth_', maxSelect: 1 }))
users.schema.add(new Field({ name: 'updated_by', type: 'relation', collectionId: '_pb_users_auth_', maxSelect: 1 }))
users.schema.add(new Field({ name: 'team', type: 'relation', collectionId: 'teams', maxSelect: 1 }))

$app.dao().saveCollection(users)

// --- invites
Dao(db).saveCollection(new Collection({
  name: 'invites',
  type: 'base',
  schema: [
    { name: 'email', type: 'email', required: true },
    { name: 'role',  type: 'select', required: true,
      options: { maxSelect: 1, values: ['admin', 'manager', 'member', 'viewer'] } },
    { name: 'token', type: 'text', required: true, max: 64 },
    { name: 'invited_by', type: 'relation', collectionId: '_pb_users_auth_', maxSelect: 1, cascadeDelete: true },
    { name: 'expires_at', type: 'date' },
    { name: 'accepted_at', type: 'date' },
    { name: 'status', type: 'select', required: true,
      options: { maxSelect: 1, values: ['pending', 'accepted', 'expired', 'revoked'] } },
  ],
  indexes: [
    'CREATE UNIQUE INDEX idx_invite_token ON invites (token)',
    'CREATE INDEX idx_invite_email ON invites (email)',
  ],
}))

// --- audit_log
Dao(db).saveCollection(new Collection({
  name: 'audit_log',
  type: 'base',
  schema: [
    { name: 'actor',       type: 'relation', collectionId: '_pb_users_auth_', maxSelect: 1, cascadeDelete: false },
    { name: 'actor_email', type: 'text', max: 200 },
    { name: 'action',      type: 'text', required: true, max: 80 },
    { name: 'target_id',   type: 'text', max: 64 },
    { name: 'target_email',type: 'text', max: 200 },
    { name: 'metadata',    type: 'json' },
    { name: 'ip',          type: 'text', max: 64 },
    { name: 'user_agent',  type: 'text', max: 500 },
  ],
  indexes: ['CREATE INDEX idx_audit_created ON audit_log (created)'],
}))

// --- teams (multi-tenant opcional)
Dao(db).saveCollection(new Collection({
  name: 'teams',
  type: 'base',
  schema: [
    { name: 'name', type: 'text', required: true, max: 120 },
    { name: 'slug', type: 'text', required: true, max: 60, pattern: "^[a-z0-9-]+$" },
    { name: 'plan', type: 'select', options: { maxSelect: 1, values: ['free', 'pro', 'enterprise'] } },
  ],
  indexes: ['CREATE UNIQUE INDEX idx_team_slug ON teams (slug)'],
}))
```

## 2. Hooks

### Bootstrap — 1º user vira super admin automaticamente

```js
// pocketbase/pb_hooks/admin_panel.pb.js
/// <reference path="../pb_data/types.d.ts" />

function audit(action, targetId, targetEmail, metadata) {
  $app.dao().saveRecord(new Record($app.findCollectionByNameOrId('audit_log'), {
    actor:       $app.auth()?.id,
    actor_email: $app.auth()?.email || 'system',
    action, target_id: targetId, target_email: targetEmail,
    metadata: metadata || {},
    ip: '', user_agent: '',
  }))
}

// 1) 1º user do sistema vira admin
onRecordAfterCreateRequest((e) => {
  if (e.collection.name !== 'users') return
  const total = $app.dao().findRecordsByFilter('_pb_users_auth_', '', '', 9999, 0).length
  if (total === 1) {
    e.record.set('role', 'admin')
    e.record.set('status', 'active')
    $app.dao().saveRecord(e.record)
    audit('user.bootstrap', e.record.id, e.record.email(), { first: true })
  }
}, $app)

// 2) Proteger role do 1º admin (não pode rebaixar)
onRecordBeforeUpdateRequest((e) => {
  if (e.collection.name !== 'users') return
  const orig = e.record.original()
  if (orig.getString('role') === 'admin' && e.record.getString('role') !== 'admin') {
    const admins = $app.dao().findRecordsByFilter('_pb_users_auth_',
      `role = "admin" && id != "${e.record.id}"`, '', 9999, 0)
    if (admins.length === 0) {
      throw new BadRequestError('Não é possível rebaixar o único admin do sistema')
    }
  }
}, $app)

// 3) Bloquear auto-edição maliciosa (user comum mudando própria role)
onRecordBeforeUpdateRequest((e) => {
  if (e.collection.name !== 'users') return
  const orig = e.record.original()
  const me = e.auth?.id
  if (me === e.record.id && orig.getString('role') !== e.record.getString('role')) {
    throw new BadRequestError('Você não pode alterar sua própria role')
  }
  if (me === e.record.id && e.record.getString('status') === 'suspended') {
    throw new BadRequestError('Você não pode se suspender')
  }
}, $app)

// 4) Logar login
onRecordAfterCreateRequest((e) => {
  // ... (PB não tem hook direto de login; usar rota custom abaixo)
}, $app)

// 5) Audit em mudanças de user
onRecordAfterUpdateRequest((e) => {
  if (e.collection.name !== 'users') return
  const orig = e.record.original()

  if (orig.getString('role') !== e.record.getString('role')) {
    audit('user.role.change', e.record.id, e.record.email(), {
      from: orig.getString('role'), to: e.record.getString('role'),
    })
  }
  if (orig.getString('status') !== e.record.getString('status')) {
    audit('user.status.change', e.record.id, e.record.email(), {
      from: orig.getString('status'), to: e.record.getString('status'),
    })
  }
}, $app)
```

### Convite por email

```js
// ainda em admin_panel.pb.js
routerAdd('POST', '/api/admin/invites', (c) => {
  if (!c.auth?.isAdmin) return c.json(403, { error: 'forbidden' })

  const body = JSON.parse(c.request.body())
  const { email, role } = body
  const token = $security.randomString(32)

  $app.dao().saveRecord(new Record($app.findCollectionByNameOrId('invites'), {
    email, role, token,
    invited_by: c.auth.id,
    expires_at: new Date(Date.now() + 7 * 24 * 3600 * 1000).toISOString(),
    status: 'pending',
  }))

  const acceptUrl = $app.settings().meta.publicUrl + '/app/accept-invite?token=' + token
  const html = tpl.render({
    title: 'Você foi convidado!',
    body: `<p>${c.auth.email()} te convidou para acessar <strong>${$app.settings().meta.appName}</strong> com a role <strong>${role}</strong>.</p>
           <p>O link expira em 7 dias.</p>`,
    ctaText: 'Aceitar convite', ctaUrl: acceptUrl,
  })

  $app.newMailClient().send(new MailerMessage({
    from: { address: $app.settings().meta.senderAddress, name: 'Admin' },
    to: [{ address: email }],
    subject: 'Convite para ' + $app.settings().meta.appName,
    html,
  }))

  audit('invite.create', null, email, { role })
  return c.json(200, { ok: true })
})

routerAdd('GET', '/api/invites/:token', (c) => {
  try {
    const inv = $app.dao().findFirstRecordByData('invites', 'token', c.request.pathValue('token'))
    if (inv.getString('status') !== 'pending') return c.json(410, { error: 'expired' })
    if (new Date(inv.getString('expires_at')) < new Date()) return c.json(410, { error: 'expired' })
    return c.json(200, { email: inv.getString('email'), role: inv.getString('role') })
  } catch {
    return c.json(404, { error: 'not found' })
  }
})
```

### Reset de senha forçado

```js
routerAdd('POST', '/api/admin/users/:id/reset-password', async (c) => {
  if (!c.auth?.isAdmin) return c.json(403, { error: 'forbidden' })

  const rec = $app.dao().findRecordById('_pb_users_auth_', c.request.pathValue('id'))
  const tempPass = $security.randomString(16)

  // PB não expõe setPassword via API pública — usar internal API
  rec.setPassword(tempPass)
  $app.dao().saveRecord(rec)

  // envia por email
  $app.newMailClient().send(new MailerMessage({
    from: { address: $app.settings().meta.senderAddress, name: 'Admin' },
    to: [{ address: rec.email() }],
    subject: 'Sua senha foi redefinida',
    html: tpl.render({
      title: 'Senha redefinida',
      body: `<p>Olá, ${rec.getString('name') || ''}. Sua senha foi redefinida por um administrador.</p>
             <p>Senha temporária: <code>${tempPass}</code></p>
             <p>Recomendamos que você troque após o login.</p>`,
      ctaText: 'Fazer login', ctaUrl: $app.settings().meta.publicUrl + '/app/login',
    }),
  }))

  audit('user.password.reset', rec.id, rec.email())
  return c.json(200, { ok: true })
})
```

### Impersonar user (pra suporte)

```js
routerAdd('POST', '/api/admin/users/:id/impersonate', (c) => {
  if (!c.auth?.isAdmin) return c.json(403, { error: 'forbidden' })
  const rec = $app.dao().findRecordById('_pb_users_auth_', c.request.pathValue('id'))
  const token = $app.newAuthToken()  // PB: gera token válido pro record
  audit('user.impersonate', rec.id, rec.email())
  return c.json(200, { token: token, record: rec.publicExport() })
})
```

> Front usa: `pb.authStore.save(token, record)` pra logar como o user. **Sempre auditar e mostrar banner claro na UI.**

## 3. Regras de acesso

| Collection   | ListRule                       | ViewRule          | CreateRule | UpdateRule                  | DeleteRule         |
|--------------|--------------------------------|-------------------|------------|-----------------------------|--------------------|
| `users`      | `id = @request.auth.id \|\| @request.auth.isAdmin` | mesmo | server-only | self (campos básicos) / admin (todos) | admin (exceto o último admin) |
| `invites`    | admin only                     | admin only        | admin only | admin only                  | admin only         |
| `audit_log`  | admin only                     | admin only        | server-only (hooks) | admin only         | never (append-only) |
| `teams`      | `""` (qualquer logado)          | mesmo             | admin      | admin                       | admin              |

## 4. Pinia store

`apps/web/src/stores/admin.ts`:

```ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import pb from '@/services/pocketbase'

export interface AdminUser {
  id: string
  email: string
  name?: string
  role: 'admin' | 'manager' | 'member' | 'viewer'
  status: 'active' | 'invited' | 'suspended'
  last_login_at?: string
  created: string
  expand?: { team?: any; created_by?: any }
}

export const useAdminStore = defineStore('admin', () => {
  const users = ref<AdminUser[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const query = ref('')
  const roleFilter = ref<'all' | AdminUser['role']>('all')

  const filtered = computed(() => {
    const q = query.value.toLowerCase().trim()
    return users.value.filter(u => {
      const matchesQ = !q || u.email.toLowerCase().includes(q) || (u.name?.toLowerCase().includes(q) ?? false)
      const matchesR = roleFilter.value === 'all' || u.role === roleFilter.value
      return matchesQ && matchesR
    })
  })

  async function fetchUsers() {
    loading.value = true
    try {
      const res = await pb.collection('users').getList<AdminUser>(1, 200, {
        sort: '-created', expand: 'team,created_by',
      })
      users.value = res.items
    } catch (e: any) { error.value = e?.message } finally { loading.value = false }
  }

  async function createUser(data: { email: string; name?: string; role: string; password?: string }) {
    const tempPass = data.password || Math.random().toString(36).slice(-12)
    const created = await pb.collection('users').create({
      email: data.email, name: data.name, role: data.role, status: 'active',
      password: tempPass, passwordConfirm: tempPass,
    })
    users.value.unshift(created)
    return { user: created, tempPassword: tempPass }
  }

  async function updateUser(id: string, data: Partial<AdminUser>) {
    const updated = await pb.collection('users').update(id, data)
    const i = users.value.findIndex(u => u.id === id)
    if (i >= 0) users.value[i] = updated
    return updated
  }

  async function suspend(id: string) {
    return updateUser(id, { status: 'suspended' })
  }
  async function reactivate(id: string) {
    return updateUser(id, { status: 'active' })
  }

  async function deleteUser(id: string) {
    await pb.collection('users').delete(id)
    users.value = users.value.filter(u => u.id !== id)
  }

  async function invite(data: { email: string; role: string }) {
    return pb.send('/api/admin/invites', { method: 'POST', body: JSON.stringify(data) })
  }

  async function resetPassword(id: string) {
    return pb.send('/api/admin/users/' + id + '/reset-password', { method: 'POST' })
  }

  async function fetchAuditLog(page = 1) {
    return pb.collection('audit_log').getList(1, 50, { sort: '-created', expand: 'actor' })
  }

  return {
    users, loading, error, query, roleFilter, filtered,
    fetchUsers, createUser, updateUser, suspend, reactivate, deleteUser,
    invite, resetPassword, fetchAuditLog,
  }
})
```

## 5. Router

```ts
{
  path: '/admin',
  component: () => import('../layouts/AdminLayout.vue'),
  meta: { requiresAuth: true, requiredRole: 'admin' },
  children: [
    { path: '', name: 'admin-dashboard',  component: () => import('../views/admin/DashboardView.vue') },
    { path: 'users', name: 'admin-users',  component: () => import('../views/admin/UsersView.vue') },
    { path: 'invites', name: 'admin-invites', component: () => import('../views/admin/InvitesView.vue') },
    { path: 'audit',  name: 'admin-audit',  component: () => import('../views/admin/AuditView.vue') },
    { path: 'settings', name: 'admin-settings', component: () => import('../views/admin/SettingsView.vue') },
  ],
}
```

## 6. Views

### Lista de usuários

`apps/web/src/views/admin/UsersView.vue`:

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAdminStore, type AdminUser } from '@/stores/admin'
import { useAuthStore } from '@/stores/auth'
import { MagnifyingGlassIcon, UserPlusIcon, KeyIcon, NoSymbolIcon, ArrowPathIcon } from '@heroicons/vue/24/outline'

const admin = useAdminStore()
const auth  = useAuthStore()
onMounted(() => admin.fetchUsers())

const showCreate = ref(false)
const newUser = ref({ email: '', name: '', role: 'member' as const, password: '' })
const createdResult = ref<{ user: any; tempPassword: string } | null>(null)

async function create() {
  createdResult.value = await admin.createUser(newUser.value)
  newUser.value = { email: '', name: '', role: 'member', password: '' }
  showCreate.value = false
}

async function changeRole(u: AdminUser, role: string) {
  if (confirm(`Mudar role de ${u.email} para ${role}?`)) await admin.updateUser(u.id, { role: role as any })
}
async function toggleSuspend(u: AdminUser) {
  if (u.status === 'suspended') await admin.reactivate(u.id)
  else await admin.suspend(u.id)
}
async function resetPwd(u: AdminUser) {
  if (!confirm(`Enviar nova senha temporária para ${u.email}?`)) return
  await admin.resetPassword(u.id)
  alert('Senha temporária enviada por email')
}
async function remove(u: AdminUser) {
  if (u.id === auth.user?.id) return alert('Você não pode excluir a si mesmo')
  if (!confirm(`Excluir ${u.email}? Esta ação é irreversível.`)) return
  await admin.deleteUser(u.id)
}
</script>

<template>
  <div class="p-6">
    <header class="flex justify-between items-center mb-6">
      <div>
        <h1 class="text-3xl font-bold">Usuários</h1>
        <p class="text-gray-500">{{ admin.users.length }} cadastrados</p>
      </div>
      <button @click="showCreate = true"
        class="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
        <UserPlusIcon class="w-5 h-5" /> Novo usuário
      </button>
    </header>

    <!-- Filtros -->
    <div class="flex gap-3 mb-4">
      <div class="relative flex-1">
        <MagnifyingGlassIcon class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input v-model="admin.query" placeholder="Buscar por email ou nome..."
          class="w-full pl-10 pr-4 py-2 border rounded-lg" />
      </div>
      <select v-model="admin.roleFilter" class="px-3 py-2 border rounded-lg">
        <option value="all">Todas roles</option>
        <option value="admin">Admin</option>
        <option value="manager">Manager</option>
        <option value="member">Member</option>
        <option value="viewer">Viewer</option>
      </select>
    </div>

    <!-- Tabela -->
    <div class="bg-white rounded-2xl shadow overflow-hidden">
      <table class="w-full">
        <thead class="bg-gray-50 text-left text-sm text-gray-500">
          <tr>
            <th class="p-3">Email</th><th class="p-3">Nome</th>
            <th class="p-3">Role</th><th class="p-3">Status</th>
            <th class="p-3">Último login</th><th class="p-3 text-right">Ações</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in admin.filtered" :key="u.id" class="border-t hover:bg-gray-50">
            <td class="p-3 font-medium">{{ u.email }}</td>
            <td class="p-3">{{ u.name || '—' }}</td>
            <td class="p-3">
              <select :value="u.role" @change="(e) => changeRole(u, (e.target as HTMLSelectElement).value)"
                class="border rounded px-2 py-1 text-sm">
                <option>admin</option><option>manager</option>
                <option>member</option><option>viewer</option>
              </select>
            </td>
            <td class="p-3">
              <span :class="['px-2 py-1 rounded-full text-xs font-medium',
                u.status === 'active' ? 'bg-green-100 text-green-700' :
                u.status === 'suspended' ? 'bg-red-100 text-red-700' :
                'bg-yellow-100 text-yellow-700']">
                {{ u.status }}
              </span>
            </td>
            <td class="p-3 text-sm text-gray-500">
              {{ u.last_login_at ? new Date(u.last_login_at).toLocaleString('pt-BR') : 'Nunca' }}
            </td>
            <td class="p-3 text-right">
              <div class="flex justify-end gap-1">
                <button @click="resetPwd(u)" title="Resetar senha" class="p-2 hover:bg-gray-100 rounded">
                  <KeyIcon class="w-4 h-4 text-gray-600" />
                </button>
                <button @click="toggleSuspend(u)" :title="u.status === 'suspended' ? 'Reativar' : 'Suspender'"
                  class="p-2 hover:bg-gray-100 rounded">
                  <NoSymbolIcon v-if="u.status === 'active'" class="w-4 h-4 text-orange-600" />
                  <ArrowPathIcon v-else class="w-4 h-4 text-green-600" />
                </button>
                <button @click="remove(u)" title="Excluir" class="p-2 hover:bg-red-100 rounded text-red-600">
                  ×
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal de criação -->
    <Teleport to="body">
      <div v-if="showCreate" @click.self="showCreate = false"
        class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <form @submit.prevent="create" class="bg-white rounded-2xl p-6 w-full max-w-md">
          <h2 class="text-2xl font-bold mb-4">Novo usuário</h2>
          <div class="space-y-3">
            <input v-model="newUser.email" required type="email" placeholder="email@empresa.com"
              class="w-full px-3 py-2 border rounded-lg" />
            <input v-model="newUser.name" placeholder="Nome (opcional)"
              class="w-full px-3 py-2 border rounded-lg" />
            <select v-model="newUser.role" class="w-full px-3 py-2 border rounded-lg">
              <option>member</option><option>manager</option><option>viewer</option>
              <option v-if="auth.isAdmin">admin</option>
            </select>
            <input v-model="newUser.password" placeholder="Senha temporária (vazio = gerar)"
              class="w-full px-3 py-2 border rounded-lg" />
            <p class="text-xs text-gray-500">Se vazia, gera automaticamente e mostra na próxima tela.</p>
          </div>
          <div class="flex justify-end gap-2 mt-6">
            <button type="button" @click="showCreate = false" class="px-4 py-2 text-gray-600">Cancelar</button>
            <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-lg">Criar</button>
          </div>
        </form>
      </div>
    </Teleport>

    <!-- Modal de senha temporária -->
    <Teleport to="body">
      <div v-if="createdResult" @click.self="createdResult = null"
        class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div class="bg-white rounded-2xl p-6 w-full max-w-md">
          <h2 class="text-2xl font-bold mb-2">Usuário criado</h2>
          <p class="text-gray-600 mb-4">{{ createdResult.user.email }}</p>
          <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p class="text-sm text-yellow-800 mb-2">Senha temporária (mostre ao usuário uma vez):</p>
            <code class="block bg-white p-2 rounded font-mono text-sm">{{ createdResult.tempPassword }}</code>
          </div>
          <button @click="createdResult = null" class="mt-4 w-full px-4 py-2 bg-blue-600 text-white rounded-lg">
            Copiei, fechar
          </button>
        </div>
      </div>
    </Teleport>
  </div>
</template>
```

### Audit log view

```vue
<!-- views/admin/AuditView.vue -->
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAdminStore } from '@/stores/admin'
const admin = useAdminStore()
const entries = ref<any[]>([])
onMounted(async () => { entries.value = (await admin.fetchAuditLog()).items })

const icon = (a: string) => ({
  'user.create': '👤+', 'user.role.change': '🔑', 'user.status.change': '🚫',
  'invite.create': '✉️', 'user.password.reset': '🔓', 'user.impersonate': '🎭',
}[a] || '📝')
</script>

<template>
  <div class="p-6">
    <h1 class="text-3xl font-bold mb-6">Audit log</h1>
    <div class="bg-white rounded-2xl shadow divide-y">
      <div v-for="e in entries" :key="e.id" class="p-4 flex items-center gap-3">
        <span class="text-2xl">{{ icon(e.action) }}</span>
        <div class="flex-1">
          <p class="font-medium">{{ e.action }} <span class="text-gray-500">— {{ e.target_email || e.actor_email }}</span></p>
          <p class="text-xs text-gray-500">{{ new Date(e.created).toLocaleString('pt-BR') }} · {{ e.actor_email }}</p>
        </div>
        <code v-if="e.metadata && Object.keys(e.metadata).length"
          class="text-xs bg-gray-100 px-2 py-1 rounded">
          {{ JSON.stringify(e.metadata) }}
        </code>
      </div>
    </div>
  </div>
</template>
```

### Settings view (config geral do app)

```vue
<!-- views/admin/SettingsView.vue -->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import pb from '@/services/pocketbase'

const settings = ref({ appName: '', supportEmail: '', allowSignup: false })

onMounted(async () => {
  try {
    const rec = await pb.collection('app_settings').getFirstListItem('singleton = true')
    settings.value = rec
  } catch {}
})

async function save() {
  await pb.collection('app_settings').update(settings.value.id || (await create()), settings.value)
}

async function create() {
  const rec = await pb.collection('app_settings').create({ ...settings.value, singleton: true })
  return rec.id
}
</script>

<template>
  <div class="p-6 max-w-2xl">
    <h1 class="text-3xl font-bold mb-6">Configurações</h1>
    <div class="bg-white rounded-2xl shadow p-6 space-y-4">
      <div>
        <label class="block text-sm font-medium mb-1">Nome do app</label>
        <input v-model="settings.appName" class="w-full px-3 py-2 border rounded-lg" />
      </div>
      <div>
        <label class="block text-sm font-medium mb-1">Email de suporte</label>
        <input v-model="settings.supportEmail" type="email" class="w-full px-3 py-2 border rounded-lg" />
      </div>
      <label class="flex items-center gap-2">
        <input v-model="settings.allowSignup" type="checkbox" />
        Permitir auto-cadastro (desabilite pra SaaS fechado)
      </label>
      <button @click="save" class="px-4 py-2 bg-blue-600 text-white rounded-lg">Salvar</button>
    </div>
  </div>
</template>
```

## 7. Aceitar convite (front)

`apps/web/src/views/AcceptInviteView.vue`:

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import pb from '@/services/pocketbase'

const route  = useRoute()
const router = useRouter()
const token  = route.query.token as string
const info   = ref<{ email: string; role: string } | null>(null)
const pass   = ref('')
const name   = ref('')
const error  = ref('')

onMounted(async () => {
  try {
    info.value = await pb.send('/api/invites/' + token)
  } catch { error.value = 'Convite inválido ou expirado' }
})

async function accept() {
  if (!info.value) return
  try {
    await pb.collection('users').create({
      email: info.value.email, password: pass.value, passwordConfirm: pass.value,
      name: name.value, role: info.value.role, status: 'active',
    })
    await pb.collection('users').authWithPassword(info.value.email, pass.value)
    router.push('/app/dashboard')
  } catch (e: any) { error.value = e?.message || 'Erro ao aceitar convite' }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50 p-6">
    <form @submit.prevent="accept" v-if="info" class="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
      <h2 class="text-2xl font-bold mb-2">Aceitar convite</h2>
      <p class="text-gray-600 mb-6">Você foi convidado como <strong>{{ info.role }}</strong> para o email <strong>{{ info.email }}</strong></p>
      <input v-model="name" required placeholder="Seu nome" class="w-full mb-3 px-3 py-2 border rounded-lg" />
      <input v-model="pass" required type="password" placeholder="Defina sua senha" minlength="8"
        class="w-full mb-4 px-3 py-2 border rounded-lg" />
      <button class="w-full py-3 bg-blue-600 text-white rounded-lg font-medium">Criar conta</button>
    </form>
    <p v-else-if="error" class="text-red-600">{{ error }}</p>
  </div>
</template>
```

## 8. Banner de impersonação

```vue
<!-- layouts/AdminLayout.vue (top bar) -->
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import pb from '@/services/pocketbase'

const router = useRouter()
const impersonating = ref<any>(null)

onMounted(() => {
  const stored = localStorage.getItem('impersonating')
  if (stored) impersonating.value = JSON.parse(stored)
})

async function stopImpersonating() {
  const orig = JSON.parse(localStorage.getItem('original_admin') || '{}')
  pb.authStore.save(orig.token, orig.record)
  localStorage.removeItem('impersonating')
  localStorage.removeItem('original_admin')
  router.push('/app/admin/users')
}
</script>

<template>
  <div>
    <div v-if="impersonating" class="bg-yellow-400 text-yellow-900 px-4 py-2 text-sm flex justify-between items-center">
      <span>🎭 Você está impersonando <strong>{{ impersonating.email }}</strong></span>
      <button @click="stopImpersonating" class="px-3 py-1 bg-yellow-900 text-white rounded">
        Voltar para admin
      </button>
    </div>
    <slot />
  </div>
</template>
```

```ts
// stores/admin.ts — ao chamar impersonate:
async function impersonate(id: string) {
  const original = { token: pb.authStore.token, record: pb.authStore.model }
  localStorage.setItem('original_admin', JSON.stringify(original))
  const { token, record } = await pb.send('/api/admin/users/' + id + '/impersonate', { method: 'POST' })
  pb.authStore.save(token, record)
  localStorage.setItem('impersonating', JSON.stringify({ email: record.email }))
  location.href = '/app/dashboard'
}
```

## 9. Checklist de venda do template

Quando for vender o template com essa skill incluída:

- [ ] `npm install` + `npm run dev` funciona 100%
- [ ] Documentação da skill em `skills/domain-admin-panel/`
- [ ] Vídeo de 5 min mostrando: criar 1º admin, criar 2º user, suspender, audit log
- [ ] Variáveis de ambiente documentadas (SMTP, branding)
- [ ] Demo online publicada (Vercel + fly.io pra PB)
- [ ] `LICENSE.md` (escolher: MIT pra tudo / comercial pra partes premium)
- [ ] Preço: R$ 197 (template) ou R$ 397 (template + 1h de setup call)

## Próximas skills que destravam mais apps

| Próxima skill | Desbloqueia |
|---|---|
| `domain-saas-billing` (já existe) | Cobrança mensal/anual |
| `domain-rbac` (já existe) | Permissões por feature |
| `domain-email-hooks` (já existe) | Onboarding transacional |
| `domain-realtime` (já existe) | Notificações ao vivo no admin |

Quer que eu atualize o PR com essa skill nova? Se você mergear o PR atual primeiro, eu abro outro. Ou prefere que eu force-push na mesma branch (adiciona commit)?