---
name: pocketbase-collections
description: Criar, migrar e estender collections/hooks do PocketBase no template — incluindo geração de tipos TS, regras de acesso e hooks JS/JSDoc. Use quando o usuário quiser adicionar uma collection nova, ajustar permissões, criar uma migration ou escrever um hook de evento.
---

# PocketBase — Collections, Migrations e Hooks

PocketBase é o backend do template. Tudo passa pelo admin (`/_/`) + JS hooks em `pocketbase/pb_hooks/`.

## Localização dos arquivos

```
pocketbase/
├── pb_data/
│   ├── data.db             # SQLite principal
│   └── types.d.ts          # ⚡ gerado pelo PB em runtime (NÃO editar)
├── pb_migrations/          # SQL/JS de migração — versionadas no git
├── pb_hooks/
│   └── main.pb.js          # hook já existente: SPA routing em /app/{path...}
└── pb_public/              # arquivos estáticos servidos (vite build output)
```

> **Regra de ouro**: sempre que criar/alterar collections, gere uma migration em `pb_migrations/` (`*.js` exportando `migrate()`). Cole no git.

## Criar uma collection (workflow)

1. **Admin visual**: abra `http://localhost:8090/_/`, crie a collection, configure campos/permissions.
2. **Migration JS**: baixe os JSONs de schema via `pb_migrations/` snapshot do admin (botão "Save as migration") ou escreva manualmente:

```js
// pocketbase/pb_migrations/1700000000_create_posts.js
/// <reference path="../pb_data/types.d.ts" />

migrate((db) => {
  const collection = new Collection({
    name: 'posts',
    type: 'base',
    schema: [
      { name: 'title', type: 'text', required: true, max: 200 },
      { name: 'body',  type: 'editor' },
      { name: 'author', type: 'relation', collectionId: '_pb_users_auth_', maxSelect: 1, cascadeDelete: false },
      { name: 'published', type: 'bool' },
    ],
    indexes: ['CREATE INDEX idx_posts_author ON posts (author)'],
  })
  return Dao(db).saveCollection(collection)
}, (db) => {
  return Dao(db).deleteCollection('posts')
})
```

3. **Tipos TS**: o PB gera `pb_data/types.d.ts` em runtime. Pra forçar: rode `npm run dev:pb` por 1-2s e olhe o arquivo.

## Regras de acesso (recomendado pra esse template)

| Collection | List | View | Create | Update | Delete |
|------------|------|------|--------|--------|--------|
| `posts`    | ✓ auth | ✓ auth | author = @request.auth.id | author = @request.auth.id | author = @request.auth.id |
| `users`    | self only | self only | admin | self | self |

Use a UI do admin ou na migration, campo `listRule`, `viewRule`, etc:

```js
listRule:   "author = @request.auth.id",
viewRule:   "author = @request.auth.id",
createRule: "@request.auth.id != ''",
updateRule: "author = @request.auth.id",
deleteRule: "author = @request.auth.id",
```

## Hooks

Já existe um hook crítico em `pb_hooks/main.pb.js`:

```js
routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", true))
```

> ⚠️ O `true` ativa `indexFallback` — obrigatório pra SPA routing do Vue Router. **Não remover.**

### Criar novo hook

```js
// pocketbase/pb_hooks/posts.pb.js
/// <reference path="../pb_data/types.d.ts" />

onRecordAfterCreateRequest((e) => {
  if (e.collection.name !== 'posts') return
  console.log('📝 novo post:', e.record.getString('title'))
  // ex: mandar email, invalidar cache, chamar webhook externo
}, $app)
```

Tipos comuns de hook:
- `onRecordBeforeCreateRequest` — bloquear/alterar antes de gravar
- `onRecordAfterCreateRequest` — efeito colateral depois
- `onRecordBeforeUpdateRequest` — validar update
- `onRecordEnrich` — adicionar campos virtuais
- `onMailerSend` — interceptar envio de email

> Hooks são recarregados automaticamente pelo PB quando você salva o arquivo. Não precisa reiniciar.

## Consumindo no Vue (TS tipado)

```ts
// apps/web/src/stores/posts.ts
import pb from '@/services/pocketbase'
import type { PostsRecord } from '../../../pocketbase/pb_data/types'

export async function listPosts() {
  return pb.collection('posts').getList<PostsRecord>(1, 20)
}

export async function createPost(data: { title: string; body: string }) {
  return pb.collection('posts').create(data)
}
```

> ⚠️ o caminho relativo `../../../pocketbase/pb_data/types` é frágil — alternativa: configurar `paths` no `tsconfig.json` com `@pb-types/*` apontando pra `pocketbase/pb_data/types.d.ts`.

## Deploy com collections/migrações

- `pb_migrations/*.js` vai pro git → em produção o PB aplica automaticamente na startup.
- Dados seed: criar collection `settings` ou usar `pb_hooks/main.pb.js` com `onBootstrap`.

## Dicas

- Debug: `console.log` em hooks aparece no terminal do `npm run dev:pb`.
- Performance: crie índices SQL em `indexes` da migration pra campos filtrados.
- Backup: `pb_data/data.db` é o estado inteiro — versionar `pb_migrations/` é o suficiente pra reconstruir.
- Auth: a collection `users` existe por padrão; **não duplicar**. Pra campos extras, é melhor uma collection `profiles` linkada por `relation`.
