---
name: vue-pinia-store
description: Criar Pinia stores no padrão do template pocketbase-vue-tailwind — Setup/Composition API style com `defineStore('name', () => {...})`, integração com `pb.authStore.onChange` e tipagem de Records. Use quando o usuário quiser adicionar gerenciamento de estado (ex: store de posts, produtos, UI) seguindo as convenções do projeto.
---

# Vue 3 + Pinia — Store Pattern

O template usa **Composition API stores** (não Options API) com tipagem vinda do PocketBase. Veja `apps/web/src/stores/auth.ts` como referência canônica.

## Estrutura canônica

```ts
// apps/web/src/stores/<nome>.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import pb from '../services/pocketbase'
import type { RecordModel } from 'pocketbase' // ou tipo gerado do PB

export const usePostsStore = defineStore('posts', () => {
  // ---- state (refs)
  const items = ref<RecordModel[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // ---- getters
  const count = computed(() => items.value.length)

  // ---- actions
  async function fetchAll() {
    loading.value = true
    error.value = null
    try {
      const res = await pb.collection('posts').getList(1, 50, { sort: '-created' })
      items.value = res.items
    } catch (e: any) {
      error.value = e?.message || 'Falha ao buscar posts'
    } finally {
      loading.value = false
    }
  }

  async function create(data: { title: string; body: string }) {
    return pb.collection('posts').create(data)
  }

  return { items, loading, error, count, fetchAll, create }
})
```

Regras do template:
1. ✅ Usar `ref` + `computed` + funções nomeadas
2. ✅ Retornar **tudo** explicitamente no final (o template espera desestruturação)
3. ✅ Importar pb de `@/services/pocketbase`
4. ❌ Não usar `state: () => ({})` (sintaxe antiga do Pinia)
5. ❌ Não mutar `pb.authStore.model` direto — usar `pb.authStore.onChange`

## Padrão reativo com authStore (estilo do template)

Se sua store depende do usuário atual, sincronize com `pb.authStore.onChange`:

```ts
pb.authStore.onChange((_token, model) => {
  currentUserId.value = model?.id ?? null
})
```

> ⚠️ `pb.authStore.onChange` é chamado **sempre** que o token/user muda (login/logout/refresh). Não usar pra carregar dados — usar `pb.collection('users').authRefresh()` no router guard (já configurado).

## Tipagem com PB gerado

Edite `apps/web/tsconfig.json` pra apontar o alias:

```json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"],
      "@pb-types/*": ["../../pocketbase/pb_data/types.d.ts"]
    }
  }
}
```

Depois:

```ts
import type { PostsRecord } from '@pb-types'
```

Re-rodar `npm run dev:web` (ou `npm run dev:pb` em outro terminal) regenera `types.d.ts`.

## Consumindo em um componente

```vue
<script setup lang="ts">
import { usePostsStore } from '@/stores/posts'
import { onMounted } from 'vue'

const posts = usePostsStore()
onMounted(() => posts.fetchAll())
</script>

<template>
  <div v-if="posts.loading">Carregando...</div>
  <ul v-else>
    <li v-for="p in posts.items" :key="p.id">{{ p.title }}</li>
  </ul>
</template>
```

## Cache & invalidação

O template **não usa cache** por padrão. Padrões úteis:

```ts
async function fetchAll(force = false) {
  if (!force && items.value.length && lastFetch.value && Date.now() - lastFetch.value < 30_000) return
  // ... fetch real ...
  lastFetch.value = Date.now()
}

// refresh depois de mutations
async function create(data) {
  const created = await pb.collection('posts').create(data)
  await fetchAll(true)
  return created
}
```

## Checklist pra adicionar uma store nova

1. Criar `apps/web/src/stores/<nome>.ts`
2. Exportar `use<Nome>Store`
3. Usar tipos do PB (não `any`)
4. Tratar `loading` + `error` em **toda** ação async
5. Não chamar `pb.collection().authRefresh()` na store — isso é responsabilidade do router

## Anti-padrões

| ❌ Não fazer | ✅ Fazer |
|---|---|
| `state: () => ({ items: [] })` | `const items = ref<...>([])` |
| `this.items` | `items.value` |
| Mutação direta de `pb.authStore` | Chamar `auth.login()` ou `auth.logout()` |
| `any` no payload/retorno | Tipo do PB ou interface local |
| `watchEffect` sincronizando auth | `pb.authStore.onChange` |
