---
name: vite-env-config
description: Configurar variáveis de ambiente Vite (`VITE_*`), proxy para PocketBase (`/api`, `/_`, `/app`) e troca entre dev/prod. Cobre peculiaridade do monorepo: cada app tem `.env.*` próprio em `apps/<app>/`, NÃO no root. Use quando o usuário quiser apontar para outro servidor PB, rodar em Codespaces/GitPod, ou adicionar variável de ambiente nova.
---

# Vite — Envs & Proxy

Monorepo do template tem **2 Vites independentes** (`apps/landing` e `apps/web`). Cada um carrega seus próprios `.env.*` — o **root `package.json` é ignorado**.

## Arquivos de env por app

```
apps/
├── landing/
│   ├── .env.development   # commitado: config padrão dev
│   ├── .env.production    # commitado: config padrão prod
│   ├── .env.local         # gitignored: override pessoal
│   └── .env.example       # commitado: documentação
└── web/
    ├── .env.development
    ├── .env.production
    ├── .env.local
    └── .env.example
```

> ⚠️ Convenção `.env.*` do Vite: prefira `apps/web/.env.development` ao invés de criar `.env` na raiz. O Vite **só enxerga** arquivos dentro do `cwd` (que é `apps/web/` ao rodar `npm run dev:web`).

## Variáveis usadas pelo template

| App       | Variável                 | Dev (default)                | Prod                |
|-----------|--------------------------|------------------------------|---------------------|
| `web`     | `VITE_POCKETBASE_URL`    | `http://localhost:8090`      | `/`                 |
| `landing` | `VITE_POCKETBASE_URL`    | `http://localhost:8090`      | `/`                 |
| `landing` | `VITE_WEBAPP_URL`        | `http://localhost:5174`      | `/app/`             |

## Consumindo no código

```ts
// qualquer arquivo em apps/web/src
const url = import.meta.env.VITE_POCKETBASE_URL
```

> **Não** usar `process.env.NEXT_PUBLIC_*` (isso é Nuxt/Next). Vite usa `import.meta.env.*`.

## Adicionar env nova

```bash
# 1. Documentar
echo "VITE_SENTRY_DSN=" >> apps/web/.env.example

# 2. Setar dev
echo "VITE_SENTRY_DSN=https://abc@sentry.io/123" >> apps/web/.env.development

# 3. Setar prod
echo "VITE_SENTRY_DSN=" >> apps/web/.env.production   # vazia => desabilitado

# 4. Usar
console.log(import.meta.env.VITE_SENTRY_DSN)
```

## Codespaces / GitPod

`.env.local` **sobrescreve** qualquer outro arquivo e é gitignored:

```bash
cat > apps/web/.env.local << EOF
VITE_POCKETBASE_URL=https://obscure-engine-xxxxxx-8090.app.github.dev/
EOF

cat > apps/landing/.env.local << EOF
VITE_POCKETBASE_URL=https://obscure-engine-xxxxxx-8090.app.github.dev/
VITE_WEBAPP_URL=https://obscure-engine-xxxxxx-5174.app.github.dev/
EOF
```

## Proxy do Vite

Já configurado pra apontar pra `VITE_POCKETBASE_URL` em `apps/web/vite.config.ts`:

```ts
server: {
  proxy: {
    '/api': { target: pbUrl, changeOrigin: true },
    '/_':   { target: pbUrl, changeOrigin: true },
  },
}
```

A landing também tem proxy próprio (`apps/landing/vite.config.ts`) — proxy cruzado pra `/app` e pra PB (`/api`, `/_`).

### Adicionar nova rota de proxy

Exemplo: servir arquivos do PB storage em dev:

```ts
// apps/web/vite.config.ts
server: {
  proxy: {
    '/api':         { target: pbUrl, changeOrigin: true },
    '/_':           { target: pbUrl, changeOrigin: true },
    '/api/files':   { target: pbUrl, changeOrigin: true, rewrite: p => p.replace(/^\/api\/files/, '/api/files') },
  },
}
```

> **Detalhe sutil**: `changeOrigin: true` é obrigatório quando o destino tem host/porta diferentes do Vite (caso default com PB rodando em `:8090`).

## Carregamento dos envs

`vite.config.ts` do `web` usa `loadEnv(mode, __dirname, 'VITE_')` para acessar variáveis antes do boot:

```ts
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, 'VITE_')
  const pbUrl = env.VITE_POCKETBASE_URL || 'http://localhost:8090'
  // ...
})
```

> O `__dirname` aqui é resolvido via `fileURLToPath(import.meta.url)` pra ESM. Mudar isso vai quebrar o proxy em dev.

## Type-safety das envs

Vite expõe `import.meta.env` com tipos default. Pra ganhar autocomplete:

```ts
// apps/web/src/env.d.ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_POCKETBASE_URL: string
  readonly VITE_SENTRY_DSN?: string
  readonly VITE_ANALYTICS_ID?: string
}
interface ImportMeta { readonly env: ImportMetaEnv }
```

## Em produção (`npm run build`)

- Apenas variáveis prefixadas com `VITE_` são bundled.
- As `VITE_*` viram strings estáticas no JS final — **não ponha segredo aqui** (ex: API key de admin).
- Use PB server-side via hook pra qualquer coisa sensível.

## Boas práticas

| ✅ Fazer | ❌ Não fazer |
|---|---|
| Commitar `.env.development` e `.env.production` com **placeholders vazios** | Commitar `.env.local` ou segredos reais |
| Usar só `VITE_*` no front | Usar variável sem prefixo (vai ser `undefined`) |
| Configurar `env.d.ts` pra autocomplete | Acessar via `process.env` |
| `.env.local` pra override pessoal / Codespaces | Editar `.env.development` pra testar mudança local |
| Logs só em dev: `if (import.meta.env.DEV) console.log(...)` | Espalhar `console.log` de env em prod |

## Diagnóstico rápido

```bash
# ver o que o Vite enxergou:
cd apps/web && npx vite --debug
# ou temporariamente no main.ts:
console.table(import.meta.env)
```
