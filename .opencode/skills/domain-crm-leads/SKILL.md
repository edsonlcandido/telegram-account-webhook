---
name: domain-crm-leads
description: Como adicionar uma feature completa de CRM (leads + contatos + funil kanban + atividades) no template. Cobre schema, migrations, hooks, stores, views e dashboard. Use quando o usuário quiser construir um CRM, gerenciar pipeline de vendas, ou adicionar tracking de leads/contatos no app.
---

# Domínio — CRM (Leads, Contatos, Funil)

Caso real: você tá construindo um CRM. Aqui vai o passo a passo completo pra adicionar `leads`, `contacts`, `activities` + um funil kanban no template.

> Esta skill é **end-to-end**: modelagem → hooks → store → UI. Use em conjunto com `vue-pinia-store`, `vue-router-auth`, `tailwind-vue-component` pros detalhes de cada peça.

## Visão do domínio

```
leads         contacts        activities
─────────     ─────────       ────────────
id            id              id
name          name            type (call/email/meeting/note)
email         email           subject
phone         phone           body
company       company         lead_id → leads
position      position        contact_id → contacts
status        address         user_id → users
source        notes           due_at
estimated_value              completed_at
owner_id → users
notes
created, updated
```

### Status do lead (funil)

```
new → contacted → qualified → proposal → negotiation → won/lost
```

## 1. Schema — migrations

### `pocketbase/pb_migrations/1700000000_create_crm.js`

```js
/// <reference path="../pb_data/types.d.ts" />

migrate((db) => {
  // --- leads
  Dao(db).saveCollection(new Collection({
    name: 'leads',
    type: 'base',
    schema: [
      { name: 'name',  type: 'text', required: true, max: 120 },
      { name: 'email', type: 'email' },
      { name: 'phone', type: 'text', max: 32 },
      { name: 'company', type: 'text', max: 120 },
      { name: 'position', type: 'text', max: 120 },
      {
        name: 'status', type: 'select', required: true,
        options: {
          maxSelect: 1,
          values: ['new', 'contacted', 'qualified', 'proposal', 'negotiation', 'won', 'lost']
        }
      },
      { name: 'source', type: 'select', options: { maxSelect: 1, values: ['website', 'referral', 'social', 'ads', 'event', 'other'] } },
      { name: 'estimated_value', type: 'number', min: 0 },
      { name: 'notes', type: 'json' },           // array de { text, by, at }
      { name: 'owner', type: 'relation', collectionId: '_pb_users_auth_', maxSelect: 1, cascadeDelete: false },
    ],
    indexes: [
      'CREATE INDEX idx_leads_status ON leads (status)',
      'CREATE INDEX idx_leads_owner  ON leads (owner)',
    ],
  }))

  // --- contacts
  Dao(db).saveCollection(new Collection({
    name: 'contacts',
    type: 'base',
    schema: [
      { name: 'name',    type: 'text', required: true, max: 120 },
      { name: 'email',   type: 'email' },
      { name: 'phone',   type: 'text', max: 32 },
      { name: 'company', type: 'text', max: 120 },
      { name: 'position',type: 'text', max: 120 },
      { name: 'address', type: 'text' },
      { name: 'notes',   type: 'text' },
      { name: 'owner',   type: 'relation', collectionId: '_pb_users_auth_', maxSelect: 1 },
    ],
  }))

  // --- activities
  Dao(db).saveCollection(new Collection({
    name: 'activities',
    type: 'base',
    schema: [
      {
        name: 'type', type: 'select', required: true,
        options: { maxSelect: 1, values: ['call', 'email', 'meeting', 'note', 'task'] }
      },
      { name: 'subject', type: 'text', max: 200 },
      { name: 'body',    type: 'text' },
      { name: 'lead',    type: 'relation', collectionId: 'leads',    maxSelect: 1, cascadeDelete: true },
      { name: 'contact', type: 'relation', collectionId: 'contacts', maxSelect: 1, cascadeDelete: true },
      { name: 'user',    type: 'relation', collectionId: '_pb_users_auth_', maxSelect: 1, cascadeDelete: false },
      { name: 'due_at',      type: 'date' },
      { name: 'completed_at',type: 'date' },
    ],
  }))
})
```

### Regras de acesso (via admin UI `/_/`)

| Collection   | ListRule | ViewRule | CreateRule        | UpdateRule      | DeleteRule |
|--------------|----------|----------|-------------------|-----------------|------------|
| `leads`      | `owner = @request.auth.id` | mesmo | `@request.auth.id != ""` | `owner = @request.auth.id` | `owner = @request.auth.id` |
| `contacts`   | `owner = @request.auth.id` | mesmo | `@request.auth.id != ""` | `owner = @request.auth.id` | `owner = @request.auth.id` |
| `activities` | `user = @request.auth.id`  | mesmo | `user = @request.auth.id` | mesmo          | mesmo      |

> **Multi-user (team)**: troque `owner = @request.auth.id` por `team_id = @request.auth.team_id` — isso é multi-tenancy simples.

## 2. Hooks

### `pocketbase/pb_hooks/leads.pb.js` — auto-atribui owner + validações

```js
/// <reference path="../pb_data/types.d.ts" />

onRecordBeforeCreateRequest((e) => {
  if (e.collection.name !== 'leads') return

  // garante owner = user atual
  e.record.set('owner', e.auth?.id)

  // status default
  if (!e.record.getString('status')) e.record.set('status', 'new')

  // estimated_value >= 0
  const v = e.record.getNumber('estimated_value')
  if (v !== null && v < 0) throw new BadRequestError('Valor estimado não pode ser negativo')
}, $app)

onRecordBeforeUpdateRequest((e) => {
  if (e.collection.name !== 'leads') return
  // impedir mudança de owner
  if (!e.auth?.isAdmin && e.record.getString('owner') !== e.record.original().getString('owner')) {
    throw new BadRequestError('Não é permitido transferir lead')
  }
}, $app)

onRecordAfterUpdateRequest((e) => {
  if (e.collection.name !== 'leads') return
  // se virou 'won' ou 'lost', criar atividade automática
  const status = e.record.getString('status')
  if (['won', 'lost'].includes(status)) {
    $app.dao().saveRecord(new Record($app.findCollectionByNameOrId('activities'), {
      type: 'note',
      subject: `Lead marcado como ${status}`,
      body: `Lead "${e.record.getString('name')}" → ${status}`,
      lead: e.record.id,
      user: e.auth?.id,
    }))
  }
}, $app)
```

## 3. Pinia Store

`apps/web/src/stores/leads.ts`:

```ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import pb from '@/services/pocketbase'

export type LeadStatus = 'new' | 'contacted' | 'qualified' | 'proposal' | 'negotiation' | 'won' | 'lost'
export interface Lead {
  id: string
  name: string
  email?: string
  phone?: string
  company?: string
  status: LeadStatus
  estimated_value?: number
  owner?: string
  // ... outros campos
}

export const useLeadsStore = defineStore('leads', () => {
  const items = ref<Lead[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const filter = ref<LeadStatus | 'all'>('all')

  const filtered = computed(() =>
    filter.value === 'all' ? items.value : items.value.filter(l => l.status === filter.value)
  )

  const byStatus = computed(() => {
    const groups: Record<LeadStatus, Lead[]> = {
      new: [], contacted: [], qualified: [], proposal: [], negotiation: [], won: [], lost: [],
    }
    for (const l of items.value) groups[l.status]?.push(l)
    return groups
  })

  async function fetchAll() {
    loading.value = true
    error.value = null
    try {
      const res = await pb.collection('leads').getList<Lead>(1, 200, {
        sort: '-created',
        expand: 'owner',
      })
      items.value = res.items
    } catch (e: any) {
      error.value = e?.message || 'Falha ao listar leads'
    } finally {
      loading.value = false
    }
  }

  async function create(data: Partial<Lead>) {
    const created = await pb.collection('leads').create(data)
    items.value.unshift(created)
    return created
  }

  async function update(id: string, data: Partial<Lead>) {
    const updated = await pb.collection('leads').update(id, data)
    const idx = items.value.findIndex(l => l.id === id)
    if (idx >= 0) items.value[idx] = updated
    return updated
  }

  async function moveTo(id: string, status: LeadStatus) {
    return update(id, { status })
  }

  async function remove(id: string) {
    await pb.collection('leads').delete(id)
    items.value = items.value.filter(l => l.id !== id)
  }

  // realtime: sincroniza mudanças vindas de outros users
  pb.collection('leads').subscribe('*', (e) => {
    if (e.action === 'create') items.value.unshift(e.record as Lead)
    else if (e.action === 'update') {
      const idx = items.value.findIndex(l => l.id === e.record.id)
      if (idx >= 0) items.value[idx] = e.record as Lead
    } else if (e.action === 'delete') {
      items.value = items.value.filter(l => l.id !== e.record.id)
    }
  })

  return { items, loading, error, filter, filtered, byStatus, fetchAll, create, update, moveTo, remove }
})
```

> ⚠️ `pb.collection('leads').subscribe('*')` é o hook realtime do PB — funciona com `domain-realtime` se quiser ir além.

## 4. Router

```ts
// apps/web/src/router/index.ts
{
  path: '/leads',
  name: 'leads',
  component: () => import('../views/LeadsView.vue'),
  meta: { requiresAuth: true },
},
{
  path: '/leads/:id',
  name: 'lead-detail',
  component: () => import('../views/LeadDetailView.vue'),
  meta: { requiresAuth: true },
  props: true,
},
```

## 5. Views

### `apps/web/src/views/LeadsView.vue` — Kanban

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { useLeadsStore, type LeadStatus } from '@/stores/leads'
import KanbanColumn from '@/components/kanban/KanbanColumn.vue'

const leads = useLeadsStore()
onMounted(() => leads.fetchAll())

const columns: { status: LeadStatus; title: string; color: string }[] = [
  { status: 'new',         title: 'Novo',          color: 'bg-blue-100' },
  { status: 'contacted',   title: 'Em contato',    color: 'bg-yellow-100' },
  { status: 'qualified',   title: 'Qualificado',   color: 'bg-purple-100' },
  { status: 'proposal',    title: 'Proposta',      color: 'bg-indigo-100' },
  { status: 'negotiation', title: 'Negociação',    color: 'bg-pink-100' },
  { status: 'won',         title: 'Ganho',         color: 'bg-green-100' },
  { status: 'lost',        title: 'Perdido',       color: 'bg-red-100' },
]
</script>

<template>
  <div class="p-6">
    <header class="flex justify-between items-center mb-6">
      <h1 class="text-3xl font-bold">Pipeline</h1>
      <button @click="$router.push('/leads/new')"
        class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
        + Novo Lead
      </button>
    </header>

    <div class="flex gap-4 overflow-x-auto pb-4">
      <KanbanColumn
        v-for="col in columns"
        :key="col.status"
        :title="col.title"
        :color="col.color"
        :leads="leads.byStatus[col.status]"
        @drop="(leadId: string) => leads.moveTo(leadId, col.status)"
      />
    </div>
  </div>
</template>
```

### `apps/web/src/components/kanban/KanbanColumn.vue`

```vue
<script setup lang="ts">
import type { Lead, LeadStatus } from '@/stores/leads'

defineProps<{ title: string; color: string; leads: Lead[] }>()
const emit = defineEmits<{ drop: [leadId: string] }>()

function onDragOver(e: DragEvent) { e.preventDefault() }
function onDrop(e: DragEvent) {
  const id = e.dataTransfer?.getData('text/plain')
  if (id) emit('drop', id)
}
</script>

<template>
  <div :class="['rounded-xl p-3 w-72 flex-s-col shrink-0', color]" @dragover="onDragOver" @drop="onDrop">
    <h2 class="font-bold mb-3 text-sm uppercase tracking-wide">
      {{ title }} <span class="text-gray-500">({{ leads.length }})</span>
    </h2>
    <div class="space-y-2">
      <article
        v-for="lead in leads"
        :key="lead.id"
        draggable="true"
        @dragstart="(e) => e.dataTransfer?.setData('text/plain', lead.id)"
        class="bg-white rounded-lg p-3 shadow hover:shadow-md cursor-grab active:cursor-grabbing"
      >
        <h3 class="font-medium">{{ lead.name }}</h3>
        <p v-if="lead.company" class="text-sm text-gray-500">{{ lead.company }}</p>
        <p v-if="lead.estimated_value" class="text-sm text-green-600 font-semibold mt-1">
          R$ {{ lead.estimated_value.toLocaleString('pt-BR') }}
        </p>
      </article>
    </div>
  </div>
</template>
```

### `apps/web/src/views/LeadDetailView.vue`

Mostra dados do lead + timeline de activities + form pra adicionar atividade nova. Use `domain-realtime` se quiser que outro user veja atualizações ao vivo.

## 6. Dashboard com métricas

```vue
<script setup lang="ts">
import { computed } from 'vue'
import { useLeadsStore } from '@/stores/leads'

const leads = useLeadsStore()

const metrics = computed(() => {
  const open = leads.items.filter(l => !['won', 'lost'].includes(l.status))
  const won  = leads.items.filter(l => l.status === 'won')
  const pipeline = open.reduce((s, l) => s + (l.estimated_value || 0), 0)
  const revenue  = won.reduce((s, l) => s + (l.estimated_value || 0), 0)
  return {
    total: leads.items.length,
    open: open.length,
    won: won.length,
    pipeline,
    revenue,
  }
})
</script>

<template>
  <div class="grid md:grid-cols-3 gap-4 p-6">
    <div class="bg-white rounded-2xl shadow p-5">
      <p class="text-sm text-gray-500">Pipeline aberto</p>
      <p class="text-3xl font-bold">R$ {{ metrics.pipeline.toLocaleString('pt-BR') }}</p>
    </div>
    <div class="bg-white rounded-2xl shadow p-5">
      <p class="text-sm text-gray-500">Receita ganha</p>
      <p class="text-3xl font-bold text-green-600">R$ {{ metrics.revenue.toLocaleString('pt-BR') }}</p>
    </div>
    <div class="bg-white rounded-2xl shadow p-5">
      <p class="text-sm text-gray-500">Taxa de conversão</p>
      <p class="text-3xl font-bold">
        {{ metrics.total ? Math.round(metrics.won / metrics.total * 100) : 0 }}%
      </p>
    </div>
  </div>
</template>
```

## Próximos passos

- **Histórico de mudanças**: hook `onRecordAfterUpdate` em `leads` que insere em `lead_history`
- **Atividades no calendário**: collection separada `events` com start/end
- **Importação em massa**: view de upload CSV → hook `onRecordAfterCreate` cria leads
- **Integração com WhatsApp**: webhook → cria lead via API do PB
- **Permissões granulares**: skill `domain-rbac` (admin vê tudo, vendedor vê só seus)