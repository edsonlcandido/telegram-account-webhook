---
name: domain-saas-billing
description: Como adicionar SaaS billing completo no template — planos, assinaturas via Stripe, entitlements por feature, webhook handler, gating de features no front. Cobre collections, hooks PB, store Pinia e UI de planos. Use quando o usuário quiser monetizar o app com planos, free trial, paywall de features, ou implementar SaaS multi-tier.
---

# Domínio — SaaS Billing (Stripe + entitlements)

Caso real: app freemium/SaaS com planos Free/Pro/Enterprise, gating de features, gestão de assinatura via Stripe.

> **Stack típico**: Stripe Checkout (cliente) + Stripe Webhook (PB hook) + collection `subscriptions` (sincronizada via webhook).

## Visão do domínio

```
plans             subscriptions       entitlements       invoices
─────             ──────────────       ─────────────       ────────
id                id                   id                 id
name              user (relation)      user (relation)    user (relation)
slug              plan (relation)      feature_key        stripe_invoice_id
stripe_price_id   stripe_sub_id        plan (relation)    amount
features (json)   status (active/...   granted_at         currency
monthly_price     current_period_end   expires_at         paid
yearly_price      cancel_at            value (json)       invoice_pdf
is_active         canceled_at
trial_days        trial_end
```

## 1. Schema

```js
// pocketbase/pb_migrations/1700000000_create_billing.js
/// <reference path="../pb_data/types.d.ts" />

migrate((db) => {
  Dao(db).saveCollection(new Collection({
    name: 'plans',
    type: 'base',
    schema: [
      { name: 'name', type: 'text', required: true, max: 80 },
      { name: 'slug', type: 'text', required: true, max: 60, pattern: "^[a-z0-9-]+$" },
      { name: 'stripe_monthly_price_id', type: 'text' },
      { name: 'stripe_yearly_price_id',  type: 'text' },
      { name: 'monthly_price', type: 'number', required: true, min: 0 },
      { name: 'yearly_price',  type: 'number', min: 0 },
      { name: 'currency', type: 'text', max: 3 },
      { name: 'features', type: 'json' },        // ['unlimited_projects','priority_support',...]
      { name: 'limits',   type: 'json' },        // { projects: 5, seats: 1 }
      { name: 'trial_days', type: 'number', min: 0 },
      { name: 'is_active', type: 'bool' },
      { name: 'sort_order', type: 'number' },
    ],
    indexes: ['CREATE UNIQUE INDEX idx_plan_slug ON plans (slug)'],
  }))

  Dao(db).saveCollection(new Collection({
    name: 'subscriptions',
    type: 'base',
    schema: [
      { name: 'user', type: 'relation', collectionId: '_pb_users_auth_', required: true, maxSelect: 1, cascadeDelete: true },
      { name: 'plan', type: 'relation', collectionId: 'plans', required: true, maxSelect: 1 },
      { name: 'stripe_customer_id', type: 'text' },
      { name: 'stripe_subscription_id', type: 'text' },
      { name: 'status', type: 'select', required: true,
        options: { maxSelect: 1, values: ['trialing', 'active', 'past_due', 'canceled', 'incomplete', 'unpaid'] } },
      { name: 'current_period_start', type: 'date' },
      { name: 'current_period_end',   type: 'date' },
      { name: 'trial_end',            type: 'date' },
      { name: 'cancel_at',            type: 'date' },
      { name: 'canceled_at',          type: 'date' },
    ],
    indexes: [
      'CREATE UNIQUE INDEX idx_sub_user ON subscriptions (user)',
      'CREATE INDEX idx_sub_stripe ON subscriptions (stripe_subscription_id)',
    ],
  }))

  Dao(db).saveCollection(new Collection({
    name: 'invoices',
    type: 'base',
    schema: [
      { name: 'user', type: 'relation', collectionId: '_pb_users_auth_', required: true, maxSelect: 1, cascadeDelete: true },
      { name: 'stripe_invoice_id', type: 'text' },
      { name: 'amount', type: 'number', required: true },
      { name: 'currency', type: 'text', max: 3 },
      { name: 'status', type: 'select', required: true,
        options: { maxSelect: 1, values: ['draft', 'open', 'paid', 'void', 'uncollectible'] } },
      { name: 'invoice_pdf_url', type: 'url' },
      { name: 'paid_at', type: 'date' },
    ],
  }))
})
```

### Regras de acesso

| Collection       | ListRule | ViewRule            | CreateRule | UpdateRule | DeleteRule |
|------------------|----------|---------------------|------------|------------|------------|
| `plans`          | `""`     | `""`                | admin      | admin      | admin      |
| `subscriptions`  | `user = @request.auth.id` | mesmo | server-only | server-only | server-only |
| `invoices`       | `user = @request.auth.id` | mesmo | server-only | server-only | server-only |

> **Importante**: subscriptions/invoices só são mutáveis via hook (webhook Stripe), nunca direto pelo client. Configure `createRule/updateRule/deleteRule = ""` ou use um API token no servidor.

## 2. Hook Stripe — webhook

### Variáveis de ambiente (PB lê via `os.Getenv`)

```bash
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_BASIC_MONTHLY=price_xxx
STRIPE_PRICE_BASIC_YEARLY=price_xxx
STRIPE_PRICE_PRO_MONTHLY=price_xxx
STRIPE_PRICE_PRO_YEARLY=price_xxx
```

### `pocketbase/pb_hooks/billing.pb.js`

```js
/// <reference path="../pb_data/types.d.ts" />

const STRIPE_KEY = $os.getenv('STRIPE_SECRET_KEY')

async function stripe(method, path, body) {
  const res = await $http.send({
    url: 'https://api.stripe.com/v1' + path,
    method,
    headers: {
      'Authorization': 'Bearer ' + STRIPE_KEY,
      'Content-Type':  'application/x-www-form-urlencoded',
    },
    body: body || '',
  })
  return JSON.parse(res.raw)
}

function findUserByCustomer(customerId) {
  try {
    return $app.dao().findFirstRecordByData('subscriptions', 'stripe_customer_id', customerId)
  } catch { return null }
}

// --- criar checkout session
routerAdd('POST', '/api/billing/checkout', async (c) => {
  if (!c.auth) return c.json(401, { error: 'auth required' })
  const body = await c.request.body()
  const { priceId, planSlug } = JSON.parse(body)
  const user = c.auth

  // cria ou reusa customer
  const customers = $app.dao().findRecordsByFilter('subscriptions',
    `user = "${user.id}" && stripe_customer_id != ""`, '', 1, 0)
  let customerId = customers[0]?.getString('stripe_customer_id')

  if (!customerId) {
    const cust = await stripe('POST', '/customers', new URLSearchParams({
      email: user.email, 'metadata[user_id]': user.id,
    }).toString())
    customerId = cust.id
  }

  const session = await stripe('POST', '/checkout/sessions', new URLSearchParams({
    'mode':                'subscription',
    'customer':            customerId,
    'line_items[0][price]': priceId,
    'line_items[0][quantity]': '1',
    'success_url':         $os.getenv('PUBLIC_URL') + '/app/billing?status=success',
    'cancel_url':          $os.getenv('PUBLIC_URL') + '/app/billing?status=cancel',
    'metadata[user_id]':   user.id,
    'metadata[plan_slug]': planSlug,
  }).toString())

  return c.json(200, { url: session.url })
})

// --- webhook (Stripe -> PB)
routerAdd('POST', '/api/stripe/webhook', async (c) => {
  const sig = c.request.header.get('stripe-signature')
  const body = await c.request.body()
  const secret = $os.getenv('STRIPE_WEBHOOK_SECRET')

  // verificação manual da assinatura
  const parts = Object.fromEntries(sig.split(',').map(p => p.split('=')))
  const signedPayload = parts.t + '.' + body
  const expected = $security.hs256(signedPayload, secret)
  if (parts.v1 !== expected) return c.json(400, { error: 'bad signature' })

  const event = JSON.parse(body)
  const dao = $app.dao()

  switch (event.type) {
    case 'checkout.session.completed': {
      const s = event.data.object
      const userId = s.metadata.user_id
      const sub = await stripe('GET', '/subscriptions/' + s.subscription, '')
      const user = dao.findRecordById('_pb_users_auth_', userId)

      // upsert subscription
      let rec
      try {
        rec = dao.findFirstRecordByData('subscriptions', 'user', userId)
        rec.set('plan', dao.findFirstRecordByData('plans', 'slug', s.metadata.plan_slug).id)
        rec.set('stripe_subscription_id', sub.id)
        rec.set('stripe_customer_id', sub.customer)
        rec.set('status', sub.status)
        rec.set('current_period_start', new Date(sub.current_period_start * 1000).toISOString())
        rec.set('current_period_end',   new Date(sub.current_period_end   * 1000).toISOString())
        rec.set('trial_end', sub.trial_end ? new Date(sub.trial_end * 1000).toISOString() : null)
      } catch {
        rec = new Record(dao.findCollectionByNameOrId('subscriptions'), {
          user: userId,
          plan: dao.findFirstRecordByData('plans', 'slug', s.metadata.plan_slug).id,
          stripe_subscription_id: sub.id,
          stripe_customer_id:     sub.customer,
          status: sub.status,
          current_period_start: new Date(sub.current_period_start * 1000).toISOString(),
          current_period_end:   new Date(sub.current_period_end   * 1000).toISOString(),
          trial_end: sub.trial_end ? new Date(sub.trial_end * 1000).toISOString() : null,
        })
      }
      dao.saveRecord(rec)
      break
    }

    case 'invoice.paid': {
      const inv = event.data.object
      const sub = dao.findFirstRecordByData('subscriptions', 'stripe_subscription_id', inv.subscription)
      if (sub) {
        dao.saveRecord(new Record(dao.findCollectionByNameOrId('invoices'), {
          user: sub.getString('user'),
          stripe_invoice_id: inv.id,
          amount:   inv.amount_paid / 100,
          currency: inv.currency.toUpperCase(),
          status:   inv.status,
          invoice_pdf_url: inv.invoice_pdf,
          paid_at:  new Date().toISOString(),
        }))
      }
      break
    }

    case 'customer.subscription.updated':
    case 'customer.subscription.deleted': {
      const sub = event.data.object
      const rec = dao.findFirstRecordByData('subscriptions', 'stripe_subscription_id', sub.id)
      if (rec) {
        rec.set('status', sub.status)
        rec.set('current_period_end', new Date(sub.current_period_end * 1000).toISOString())
        if (sub.canceled_at) rec.set('canceled_at', new Date(sub.canceled_at * 1000).toISOString())
        dao.saveRecord(rec)
      }
      break
    }
  }
  return c.json(200, { received: true })
})

// --- portal do cliente (cancelar, atualizar cartão)
routerAdd('POST', '/api/billing/portal', async (c) => {
  if (!c.auth) return c.json(401, { error: 'auth required' })
  const rec = $app.dao().findFirstRecordByData('subscriptions', 'user', c.auth.id)
  if (!rec?.getString('stripe_customer_id')) return c.json(404, { error: 'no customer' })

  const portal = await stripe('POST', '/billing_portal/sessions', new URLSearchParams({
    customer: rec.getString('stripe_customer_id'),
    return_url: $os.getenv('PUBLIC_URL') + '/app/billing',
  }).toString())
  return c.json(200, { url: portal.url })
})
```

## 3. Entitlements — gating de features

### `apps/web/src/composables/useEntitlements.ts`

```ts
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import pb from '@/services/pocketbase'

export interface Entitlements {
  plan: string | null
  features: Set<string>
  limits: Record<string, number>
  isPro: boolean
  can: (feature: string) => boolean
  limitReached: (key: string, current: number) => boolean
}

export function useEntitlements(): Entitlements {
  const auth = useAuthStore()

  // cache simples — pode usar Pinia store
  const sub = ref<any>(null)
  onMounted(async () => {
    if (!auth.user) return
    try {
      sub.value = await pb.collection('subscriptions').getFirstListItem(`user = "${auth.user.id}"`)
    } catch { /* sem subscription = free tier */ }
  })

  const features = computed(() => new Set(sub.value?.expand?.plan?.features ?? []))
  const limits   = computed(() => sub.value?.expand?.plan?.limits ?? {})

  return {
    plan: sub.value?.expand?.plan?.slug ?? null,
    features: features.value,
    limits:   limits.value,
    isPro: features.value.has('pro') || features.value.has('enterprise'),
    can:     (f: string) => features.value.has(f),
    limitReached: (k: string, current: number) => {
      const limit = limits.value[k]
      return typeof limit === 'number' && limit !== -1 && current >= limit
    },
  }
}
```

### Uso num componente

```vue
<script setup lang="ts">
import { useEntitlements } from '@/composables/useEntitlements'
const ent = useEntitlements()
</script>

<template>
  <button v-if="ent.can('export_csv')" class="px-4 py-2 bg-blue-600 text-white rounded-lg">
    Exportar CSV
  </button>
  <button v-else class="px-4 py-2 bg-gray-200 text-gray-500 rounded-lg" disabled
    title="Recurso Pro">
    🔒 Exportar CSV
  </button>
</template>
```

## 4. UI de planos

`apps/web/src/views/billing/PricingView.vue`:

```vue
<script setup lang="ts">
import { onMounted, ref } from 'vue'
import pb from '@/services/pocketbase'
import { useAuthStore } from '@/stores/auth'

const plans = ref<any[]>([])
const billing = ref<'monthly' | 'yearly'>('monthly')
const auth = useAuthStore()

onMounted(async () => {
  const res = await pb.collection('plans').getList(1, 50, {
    filter: 'is_active = true', sort: 'sort_order',
  })
  plans.value = res.items
})

async function subscribe(plan: any) {
  if (!auth.isLoggedIn) { auth.$router?.push('/app/login'); return }
  const priceId = billing.value === 'monthly'
    ? plan.stripe_monthly_price_id
    : plan.stripe_yearly_price_id

  const { url } = await pb.send('/api/billing/checkout', {
    method: 'POST',
    body: JSON.stringify({ priceId, planSlug: plan.slug }),
  })
  window.location.href = url
}
</script>

<template>
  <div class="max-w-6xl mx-auto p-6">
    <div class="flex justify-center gap-2 mb-8">
      <button @click="billing = 'monthly'"
        :class="['px-4 py-2 rounded-lg', billing === 'monthly' ? 'bg-blue-600 text-white' : 'bg-gray-100']">
        Mensal
      </button>
      <button @click="billing = 'yearly'"
        :class="['px-4 py-2 rounded-lg', billing === 'yearly' ? 'bg-blue-600 text-white' : 'bg-gray-100']">
        Anual <span class="text-xs">(-20%)</span>
      </button>
    </div>

    <div class="grid md:grid-cols-3 gap-6">
      <div v-for="plan in plans" :key="plan.id"
        class="bg-white rounded-2xl shadow-lg p-6 flex flex-col">
        <h3 class="text-2xl font-bold">{{ plan.name }}</h3>
        <p class="text-4xl font-extrabold mt-3">
          R$ {{ billing === 'monthly' ? plan.monthly_price : (plan.yearly_price / 12).toFixed(0) }}
          <span class="text-sm text-gray-500 font-normal">/mês</span>
        </p>
        <ul class="mt-4 space-y-2 text-sm flex-1">
          <li v-for="f in plan.features" :key="f" class="flex items-center gap-2">
            <span class="text-green-500">✓</span> {{ f }}
          </li>
        </ul>
        <button @click="subscribe(plan)"
          class="mt-6 w-full py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg font-medium hover:opacity-90">
          Assinar
        </button>
      </div>
    </div>
  </div>
</template>
```

## Próximos passos

- **Trial abuse prevention**: hook em `onRecordBeforeCreateRequest` em `users` checa IP/email
- **Dunning**: rota custom envia email quando invoice falha (`invoice.payment_failed`)
- **Multi-currency**: campo `currency` em planos + seletor de moeda no checkout
- **Coupons**: integração com Stripe Coupons via metadata
- **Plan changes (upgrade/downgrade)**: rota custom `/api/billing/change-plan` que chama `stripe.subscriptions.update`
- **Quota tracking**: collection `usage` com `(user_id, feature_key, count, period)` pra aplicar limits