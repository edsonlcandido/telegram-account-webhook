---
name: pocketbase-template-scaffold
description: Bootstrap completo do template pocketbase-vue-tailwind-template — clone, install, dev, build e troubleshooting de portas/Hooks/proxy. Use quando o usuário quiser começar um projeto a partir do template, rodar o ambiente pela primeira vez, ou resetar o setup local.
---

# PocketBase Vue Tailwind — Scaffold

Template monorepo com **3 serviços** rodando em paralelo:

| Serviço       | Porta | Comando raiz         |
|---------------|-------|----------------------|
| PocketBase    | 8090  | `npm run dev:pb`     |
| Landing Page  | 5173  | `npm run dev:landing`|
| Web App       | 5174  | `npm run dev:web`    |

Tudo: `npm run dev` (usa `concurrently` com cores blue/green/magenta).

## Quando usar

- Clonar o template e rodar pela primeira vez
- Adicionar `.env.local` para Codespaces/GitPod
- Buildar pra produção (gera `pb_public/` com landing + app)
- Resetar o binário do PocketBase ou os dados

## Pré-requisitos

- Node.js **>= 20.19.0** (`node -v`)
- npm **>= 10.x** (`npm -v`)
- `unzip` no PATH (necessário pro script do PocketBase em Linux)

## Bootstrap rápido

```bash
git clone https://github.com/edsonlcandido/pocketbase-vue-tailwind-template.git meu-app
cd meu-app
npm install              # instala root + workspaces (landing, web)
npm run dev              # sobe tudo
```

Acesse:
- Landing → http://localhost:5173
- App → http://localhost:5174/app/dashboard
- Admin PB → http://localhost:8090/_/

## Configuração de ambiente

Cada app carrega `.env.development` / `.env.production` / `.env.local` separadamente. O **root é ignorado**.

Arquivos chave (criar à mão se não existirem):

```bash
# apps/web/.env.development
VITE_POCKETBASE_URL=http://localhost:8090
```

```bash
# apps/web/.env.production
VITE_POCKETBASE_URL=/
```

```bash
# apps/landing/.env.development
VITE_POCKETBASE_URL=http://localhost:8090
VITE_WEBAPP_URL=http://localhost:5174
```

> ⚠️ **`.env.local` sobrescreve tudo e é gitignored** — usar pra Codespaces/GitPod.

## Build de produção

```bash
npm run build
# = build:landing + copy:landing + build:web + copy:app
```

Resultado:
- Landing em `pocketbase/pb_public/`
- Web app em `pocketbase/pb_public/app/`

Depois rode `npm run preview` (sobe PB servindo os builds).

## Troubleshooting comum

| Sintoma | Causa | Fix |
|---------|-------|-----|
| `EADDRINUSE 8090` | PB já rodando | `lsof -ti:8090 | xargs kill` |
| Landing/app não acha PB | URL errada no `.env.*` | Verificar `VITE_POCKETBASE_URL` |
| Vite proxy falha | CWD errado | Vite carrega `.env` de `apps/<web\|landing>/`, **não** do root |
| `vue-tsc` falha no build do `web` | Tipos do PB não sincronizados | `npm run dev:pb` uma vez pra gerar `pb_data/types.d.ts` |
| Hook `main.pb.js` não é carregado | Variável `VITE_*` não reescreve | Convenção: editar direto em `pocketbase/pb_hooks/` e reiniciar PB |
| Linux sem `unzip` | pacote faltando | `sudo apt install unzip` |

## Resetar PocketBase

```bash
rm -rf pocketbase/pocketbase pocketbase/pb_data/*    # ⚠️ apaga DB
rm pocketbase/pocketbase.zip 2>/dev/null
npm run dev:pb              # baixa e descompacta de novo
```

O script `scripts/pocketbase.js` baixa a versão **0.36.2** automaticamente. Para fixar outra versão, edite a constante `version` no topo do arquivo.

## Estrutura que ele gera

```
meu-app/
├── apps/
│   ├── landing/         # Vite vanilla (sem Vue runtime, HTML+TS)
│   └── web/             # Vue 3 + Pinia + Router (SPA em /app/)
├── pocketbase/          # Backend + pb_public/ (vite build output)
├── scripts/             # pocketbase.js, copy-landing.js, copy-app.js
├── Dockerfile           # multi-stage (landing-builder → web-builder → alpine/pb)
├── docker-compose.yaml  # expõe 8090 e persiste pb_data
└── package.json         # workspaces ["apps/*"] + concurrently
```

## Dicas de progresso incremental

- **Primeira feature**: criar collection `posts` no admin PB, adicionar store `posts.ts` em `apps/web/src/stores/`, view `PostsView.vue` em `apps/web/src/views/`, rota em `apps/web/src/router/index.ts`. Padrão completo coberto pelas outras skills.
- **Antes de mexer**: sempre `npm run dev:pb` em um terminal e `npm run dev:web` em outro — proxy do Vite depende do PB online.
