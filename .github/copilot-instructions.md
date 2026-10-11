# Copilot Instructions - PocketBase + Vue + Tailwind CSS Template

## 🎯 Instruções para Copilot

**Stack**: PocketBase v0.36+ | Vue 3 + TypeScript | Vue Router + Pinia | Vite | Tailwind CSS  
**Arquitetura**: Monorepo (apps/landing + apps/web servidos via PocketBase)

## ⚠️ ALERTAS CRÍTICOS - PocketBase v0.23+ (LEIA ANTES DE GERAR CÓDIGO)

### 🔴 JSVM - `require()` e Node APIs NÃO FUNCIONAM

❌ **NUNCA** use em `pb_hooks/`:
```javascript
require('fs')           // ❌ ERRADO - vai falhar silenciosamente
require('path')         // ❌ ERRADO
import/export           // ❌ ERRADO - não funciona no JSVM
fs.readFile()           // ❌ ERRADO
```

✅ **USE SEMPRE** os helpers globais:
```javascript
$filesystem.fileContent(path)     // ✅ Lê arquivo
$apis.static(dir, true)            // ✅ Serve arquivo estático
$apis.requireAuth()                // ✅ Middleware de auth
$app.findRecordById(col, id)      // ✅ Query no banco
$http.send({ url, method, body }) // ✅ Request HTTP
```


### 🔴 Sintaxe `routerAdd()` Mudou em v0.23

❌ **Sintaxe Antiga (pré-v0.23) - ERRADA:**
```javascript
routerAdd("GET", "/app/*", (c) => c.file(200, "index.html"))
routerAdd("GET", "/api/test", (c) => c.json(200, { msg: "hi" }))
```

✅ **Sintaxe Nova (v0.23+) - CORRETA:**
```javascript
// Wildcards: use {path...} em vez de *
routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", true))

// Request handler usa (e), retorna e.json(), e.string(), etc.
routerAdd("GET", "/api/test", (e) => e.json(200, { msg: "hi" }))

// Middlewares são passados como argumentos opcionais
routerAdd("POST", "/api/admin", 
  (e) => e.json(200, { admin: true }),
  $apis.requireSuperuserAuth()
)
```

### 🔴 Migrations - Campos de Timestamp OBRIGATÓRIOS

❌ **ERRADO** - Criar collection sem `created` e `updated`:
```javascript
collection.createField(new Field({
  name: "name",
  type: "text",
}))
// ❌ PocketBase NÃO cria automaticamente via migrations!
```

✅ **CORRETO** - Sempre adicionar manualmente:
```javascript
collection.createField(new Field({
  name: "created",
  type: "autodate",
  onCreate: true,
}));

collection.createField(new Field({
  name: "updated",
  type: "autodate",
  onCreate: true,
  onUpdate: true,
}));

collection.createField(new Field({
  name: "name",
  type: "text",
}))
```

**⚠️ IMPORTANTE**: A UI do PocketBase cria esses campos automaticamente, mas **via migrations (JSVM) você DEVE criá-los manualmente**, senão a collection fica sem timestamps.


## 📌 Padrões de Código Esperados

### Apps Web/Landing - Vue + TypeScript

```typescript
// ✅ Sempre use composition API + script setup
<script setup lang="ts">
import { computed, ref } from 'vue'

const count = ref(0)
const doubled = computed(() => count.value * 2)
</script>

// ✅ Use type-safe Pinia stores
import { defineStore } from 'pinia'
export const useAuthStore = defineStore('auth', () => {
  const user = ref<UserRecord | null>(null)
  return { user }
})

// ✅ Sempre importe o PocketBase service
import pb from '@/services/pocketbase'
const user = await pb.collection('users').getOne(id)
```

### PocketBase Hooks - JavaScript (JSVM)

```javascript
// ✅ Sempre use helpers globais
routerAdd("GET", "/api/test", (e) => {
  return e.json(200, { message: "ok" })
})

// ✅ Use e.next() para cadeia de middlewares
routerAdd("POST", "/api/protected", 
  (e) => {
    // lógica aqui
    return e.next()
  },
  $apis.requireAuth()
)

// ✅ Hooks de registro
onRecordCreate((e) => {
  console.log("Novo registro:", e.record.id)
  return e.next()
})
```

## 🔐 Autenticação

**Sempre use `authRefresh()` em rotas protegidas** - o `authStore.isValid` não valida com o backend:

```typescript
// ✅ Vue Router guard
router.beforeEach(async (to) => {
  if (to.meta.requiresAuth && !pb.authStore.isValid) {
    return { name: 'login' }
  }
  // Valida com backend
  try {
    await pb.collection('users').authRefresh()
  } catch {
    pb.authStore.clear()
    return { name: 'login' }
  }
})

// ✅ Redirect após login com nextTick()
import { nextTick } from 'vue'
await pb.collection('users').authWithPassword(email, password)
await nextTick()
router.push({ name: 'dashboard' })
```

## 🌍 Variáveis de Ambiente

```env
# apps/web/.env.development
VITE_POCKETBASE_URL=http://localhost:8090

# apps/web/.env.production
VITE_POCKETBASE_URL=/

# apps/web/.env.local (gitignored - Codespaces)
VITE_POCKETBASE_URL=https://seu-codespace-8090.app.github.dev
```

Acesse no código com: `import.meta.env.VITE_POCKETBASE_URL`

## 🚨 Erros Comuns

| Erro | Causa | Solução |
|------|-------|---------|
| Hook falha silenciosamente | Usando `require()` ou Node APIs | Use `$apis.*` helpers |
| `/app/dashboard` retorna landing page | Falta hook ou `indexFallback=false` | Adicionar: `routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", true))` |
| Usuário deletado permanece logado | Não chama `authRefresh()` | Implementar no router guard |
| Login não redireciona | Sem `await nextTick()` | Adicionar entre auth e push |
| `npm ci` falha no Docker | `package-lock.json` no gitignore | Usar `npm install` ou desbloquear arquivo |
| Migration sem `created`/`updated` | Criar collections sem esses campos | Sempre adicionar manualmente em migrations (UI faz automático, JSVM não) |
