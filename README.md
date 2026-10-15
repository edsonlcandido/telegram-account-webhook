# Telegram Account Webhook

Vincule contas Telegram, receba mensagens em tempo real via webhook (com filtros) e responda pela mesma sessão — tudo pelo painel web.

## O que faz

- **Vincular conta Telegram**: phone + código de verificação, com **apelido opcional** (ex.: "Vendas", "Suporte") pra distinguir contas além do número.
- **Múltiplos webhooks por conta**: cada sessão Telegram pode ter N webhooks (ex.: um pro n8n, outro pro Slack, outro pro seu backend custom).
- **Filtros por webhook**: direção (`incoming`/`outgoing`/`all`), tipo de chat (`private`/`group`/`supergroup`/`channel`/`all`), match de texto (`equals`/`contains`).
- **Responder mensagens**: endpoint `POST /api/send-message` reusa a sessão Telegram pra responder o chat de origem (loop com n8n / Make / etc.).
- **Painel web único**: gerencia todas as contas, webhooks e apelidos.

## Arquitetura

Dois serviços no Easypanel, ambos construídos a partir deste repo (`build.type=dockerfile`). A rede Docker interna conecta eles; o proxy do Easypanel termina TLS e expõe só o serviço Application.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Easypanel VPS                                   │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Serviço 1: telegram-account-webhook                               │ │
│  │  Dockerfile.Application — uma única imagem servindo 3 coisas:     │ │
│  │    • PocketBase 0.40.5 (DB + Auth + Admin UI)   → :8090           │ │
│  │    • Landing page Vue (build estático)          → /                │ │
│  │    • Web app Vue (SPA)                          → /app/            │ │
│  │                                                                   │ │
│  │  Env vars:                                                        │ │
│  │    TELEGRAM_API_URL=http://telegram-api:8000    # hostname Docker │ │
│  │    ALLOWED_ORIGINS=https://telegram-webhook.ehtudo.app           │ │
│  │                                                                   │ │
│  │  Volume: pb_data → /app/pb_data                                   │ │
│  │  URL pública: https://telegram-webhook.ehtudo.app                 │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                    │                                    │
│                                    │ HTTP (rede Docker interna)         │
│                                    ▼                                    │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Serviço 2: telegram-account-webhook-telegram                     │ │
│  │  Dockerfile.Telegram                                              │ │
│  │    • FastAPI (REST API)                         → :8000           │ │
│  │    • Telethon (cliente Telegram)                                │ │
│  │                                                                   │ │
│  │  Env vars:                                                        │ │
│  │    POCKETBASE_URL=http://pocketbase:8090       # hostname Docker │ │
│  │    TG_API_ID=<my.telegram.org>                                   │ │
│  │    TG_API_HASH=<my.telegram.org>                                 │ │
│  │    ALLOWED_ORIGINS=https://telegram-webhook.ehtudo.app           │ │
│  │                                                                   │ │
│  │  Volume: session → /app/sessions/  (credenciais StringSession)   │ │
│  │  Sem URL pública — chamado só pela rede interna.                 │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Quem fala com quem:**

- O **frontend** (Vue) fala com **PocketBase** (mesma origem no proxy do Easypanel → sem CORS).
- O **PocketBase** (no serviço Application) faz proxy das chamadas de webhook/mensagens via FastAPI em `http://telegram-api:8000` (hostname Docker do serviço Telegram, configurado em `TELEGRAM_API_URL`).
- O **FastAPI** (serviço Telegram) é o **responsável pelo forwarding de webhooks**:
  1. Telethon recebe nova mensagem
  2. FastAPI consulta `telegram_webhooks` no PB (1 GET com filter)
  3. Aplica os filtros (direction, chat_type, text_match)
  4. POST em cada webhook ativo com `httpx` (timeout 10s, asyncio)
  5. Faz INSERT em `telegram_messages` (audit log; PB hook é no-op)
- O **PocketBase** (serviço Application) só armazena dados — não faz forwarding. O hook `onRecordAfterCreateSuccess` em `pb_hooks/main.pb.js` é **no-op** (loga o INSERT mas não dispara HTTP). Razão: o container do PB no Easypanel pode ter egress restrito pra certos IPs externos (network ACL); o container do FastAPI/Telethon tem egress liberado (fala com Telegram API, PB, e IPs externos sem problema).
- O **FastAPI** autentica no PB via **service token** (POCKETBASE_SERVICE_TOKEN ou POCKETBASE_ADMIN_EMAIL+PASSWORD). Usado pra TODAS as chamadas internas — INSERT em audit, lookup de sessão, listagem de webhooks. User JWT normal só pros endpoints autenticados do frontend.

**Importante:** `TELEGRAM_API_URL` deve ser o **hostname Docker interno** (`telegram-api:8000`), não a URL pública. O hostname do serviço Telegram no docker-compose é `telegram-api`; no Easypanel é resolvido pela rede interna do projeto.

---

## Estrutura do Projeto

```
telegram-account-webhook/
├── Dockerfile.Application          # PocketBase + Landing + Web app
├── Dockerfile.Telegram             # FastAPI + Telethon
├── docker-compose.yml              # dev local (2 serviços)
├── backend/
│   ├── main.py                     # FastAPI: auth, webhooks, send-message
│   ├── requirements.txt
│   └── .env.example
├── apps/
│   ├── landing/                    # Landing page Vue (Vite)
│   └── web/                        # Web app Vue (Vite)
│       └── src/
│           ├── services/telegram.ts
│           ├── stores/telegram.ts
│           ├── views/
│           │   ├── DashboardView.vue
│           │   ├── AddTelegramView.vue
│           │   ├── WebhooksListView.vue
│           │   └── ApiDocsView.vue
│           └── router/
├── pocketbase/
│   ├── pb_hooks/                   # Hooks JS do PB
│   │   └── main.pb.js
│   ├── pb_migrations/              # Migrations JS (PB 0.40+)
│   ├── pb_data/                    # volume runtime (gitignored, exceto .gitkeep e types.d.ts)
│   └── pocketbase.exe              # binário PB 0.40.5 (gitignored)
├── scripts/
│   ├── pocketbase.js               # baixa + roda PB local
│   ├── copy-landing.js
│   └── copy-app.js
├── .agents/skills/                 # Skills específicas do projeto
│   ├── pocketbase-migrations/SKILL.md
│   ├── pocketbase-jsvm/SKILL.md
│   └── pocketbase-gotchas.md
├── AGENTS.md                       # contexto operacional pra agentes
└── README.md
```

---

## Variáveis de Ambiente

### Serviço `telegram-account-webhook` (Application)

| Variável | Obrigatória | Descrição | Exemplo prod |
|---|---|---|---|
| `TELEGRAM_API_URL` | sim | URL do FastAPI (hostname Docker interno) | `http://telegram-api:8000` |
| `ALLOWED_ORIGINS` | sim | Lista CSV de origens CORS permitidas | `https://telegram-webhook.ehtudo.app` |
| `VITE_POCKETBASE_URL` | não | Bake-time. Se vazio, frontend usa `window.location.origin` (mesma origem no Easypanel) | `https://telegram-webhook.ehtudo.app` |

### Serviço `telegram-account-webhook-telegram` (Telegram API)

| Variável | Obrigatória | Descrição | Exemplo prod |
|---|---|---|---|
| `POCKETBASE_URL` | sim | URL do PocketBase (hostname Docker interno) | `http://pocketbase:8090` |
| `TG_API_ID` | sim | API ID do app Telegram (my.telegram.org) | `37377307` |
| `TG_API_HASH` | sim | API Hash do app Telegram | `a700ecef...` |
| `ALLOWED_ORIGINS` | sim | Lista CSV de origens CORS | `https://telegram-webhook.ehtudo.app` |
| `POCKETBASE_SERVICE_TOKEN` | **uma das duas** | JWT de superuser (já pronto) — login manual no admin UI do PB, copia token, cola aqui. Token default 14 dias (admin pode estender). | `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `POCKETBASE_ADMIN_EMAIL` | **uma das duas** | Email do superuser (login automático no startup). Usado SÓ se `POCKETBASE_SERVICE_TOKEN` não estiver setado. | `service@eh-tudo.app` |
| `POCKETBASE_ADMIN_PASSWORD` | **complemento** | Senha do superuser (login automático). | `...` |

> **Service token** é o que permite o FastAPI fazer INSERT em `telegram_messages` (audit) e consultar `telegram_webhooks` em background. Sem ele, **toda mensagem é dropada com warning** (handler do Telethon não tem request HTTP no contexto, não tem user JWT pra repassar). Use **Opção A** (service token pronto) pra produção — não deixa senha em env. Use **Opção B** (login auto) só pra dev/simplicidade. Auto-refresh: o FastAPI re-autentica sozinho quando o token estiver a 5min de expirar (só funciona com Opção B).

### Arquivo `backend/.env.example`

Espelha as vars acima pra dev local. Copie pra `backend/.env` e preencha.

---

## Tech Stack

| Camada | Tecnologia |
|---|---|
| Frontend | Vue 3 + TypeScript + Vite + Tailwind CSS |
| Backend API | Python 3 + FastAPI + Telethon |
| Database / Auth | PocketBase 0.40.5 (SQLite + Go) |
| Deploy | Easypanel (2 serviços no mesmo projeto, build from source) |

---

## Desenvolvimento Local

```bash
# 1. Clone
git clone https://github.com/edsonlcandido/telegram-account-webhook.git
cd telegram-account-webhook

# 2. Configure variáveis do backend
cp backend/.env.example backend/.env
# Edite backend/.env: TG_API_ID, TG_API_HASH (obtenha em my.telegram.org)

# 3. Suba PB + Telegram API com docker-compose
docker compose up -d
# PB em http://localhost:8090  |  API em http://localhost:8000

# 4. (Opcional) Rode o frontend em modo dev
cd apps/web && npm install && npm run dev   # http://localhost:5174
cd ../landing && npm install && npm run dev # http://localhost:5173

# Alternativa: rode só o PB local (sem Docker) pra mexer nas migrations
node scripts/pocketbase.js                  # baixa + serve em :8090
```

O `docker-compose.yml` define dois serviços (`pocketbase` na porta 8090, `telegram-api` na 8000). Os frontends Vue sobem separados via `npm run dev` e o Vite faz proxy pro PB.

---

## Deploy no Easypanel

**Pré-requisito:** os dois serviços já existem no Easypanel, ambos com `build.type=dockerfile` apontando pro Dockerfile certo, e volumes `pb_data` (Application) e `session` (Telegram) já criados.

> **Não tem GitHub Actions nesse projeto.** Os serviços no Easypanel estão com `autoDeploy: false` — push pro `main` sozinho **não rebuilda nada**.

Para rebuildar e fazer deploy:

```powershell
# Application (webapp + PB)
$body = '{}'
Invoke-WebRequest -Method POST `
  -Uri '<easypanel-host>/api/deploy/<token-do-servico-application>' `
  -ContentType 'application/json' -Body $body -UseBasicParsing

# Telegram API (backend)
Invoke-WebRequest -Method POST `
  -Uri '<easypanel-host>/api/deploy/<token-do-servico-telegram>' `
  -ContentType 'application/json' -Body $body -UseBasicParsing
```

Os tokens ficam nas configs de cada serviço no painel do Easypanel. Alternativa via MCP: `deployAppService` com `projectName=eh-tudo` e `serviceName=telegram-account-webhook` (e `telegram-account-webhook-telegram` pro backend).

### Após o deploy

1. Confirmar que o PB aplicou as migrations novas no boot (ver log de startup do serviço Application).
2. O backend não precisa de restart se você só mexeu em migrations ou front — só reinicie se o `main.py` mudou.

---

## API Endpoints (Telegram API — `https://api-telegram.ehtudo.app`)

| Método | Endpoint | Auth | Descrição |
|---|---|---|---|
| `GET` | `/health` | — | Health check (`active_sessions`, `saved_sessions`) |
| `POST` | `/api/send-code` | sim | Inicia login: envia SMS/código pro `phone_number` |
| `POST` | `/api/verify-code` | sim | Verifica código + 2FA (se houver), cria sessão, aceita `name` (apelido opcional) |
| `GET` | `/api/sessions` | sim | Lista sessões (com `name` e `webhook_count`) |
| `DELETE` | `/api/session/{session_id}` | sim | Remove sessão (desconecta + apaga arquivo) |
| `PATCH` | `/api/sessions/{session_id}` | sim | Renomeia sessão (`name`) |
| `GET` | `/api/sessions/{session_id}/webhooks` | sim | Lista webhooks da sessão |
| `POST` | `/api/sessions/{session_id}/webhooks` | sim | Cria webhook (com filtros) |
| `PATCH` | `/api/webhooks/{webhook_id}` | sim | Edita webhook (URL, filtros, enabled) |
| `DELETE` | `/api/webhooks/{webhook_id}` | sim | Remove webhook |
| `POST` | `/api/webhooks/{webhook_id}/toggle` | sim | Liga/desliga sem deletar |
| `POST` | `/api/webhooks/{webhook_id}/test` | sim | Dispara evento de teste (payload completo) |
| `POST` | `/api/send-message` | sim | Envia mensagem via sessão (`chat_id` + `text` + `reply_to_message_id` opcional) |
| `GET` | `/api/admin/sessions` | sim | Lista arquivos em `/app/sessions/*.json` (debug) |

**Auth:** `Authorization: Bearer <jwt-do-pocketbase>`. O middleware `verify_pb_auth` valida contra o PB.

### Webhook payload (POST recebido pelo seu endpoint)

Schema atual (gerado pelo FastAPI no `handle_new_message`):

```json
{
  "event": "telegram.message",
  "webhook_id": "m9fck2xji5cghno",
  "webhook_name": "ativa-plugin",
  "session": {
    "pb_id": "4ihcmc6a621sdij",
    "session_id": "account_5511932055173",
    "phone": "+5511932055173",
    "name": "Vendas"
  },
  "message": {
    "id": 51689,
    "chat_id": -1003350466807,
    "chat_type": "group",
    "chat_title": "Nome do grupo",
    "direction": "incoming",
    "sender_id": 987654321,
    "sender_name": "Fulano",
    "text": "oi, tudo bem?",
    "timestamp": "2026-10-15T11:00:00+00:00"
  }
}
```

**Campos importantes:**

- `message.direction`: `"incoming"` (recebida) ou `"outgoing"` (enviada pela própria conta via Telegram app/desktop ou via nosso `/api/send-message`).
- `message.timestamp`: ISO 8601 UTC (data da mensagem no Telegram).
- `webhook_id` e `webhook_name`: identificação do webhook que recebeu o POST (útil quando o user tem vários webhooks na mesma sessão).

**Anti-loop:** o handler suprime forwarding (mas NÃO o audit log em `telegram_messages`) pra mensagens que a própria API enviou via `/api/send-message` nos últimos 10s, evitando loop com o receptor do webhook (ex: n8n respondendo às nossas mensagens).

---

## Coleções PocketBase

- `users`: Auth nativo do PB (email/senha → JWT).
- `telegram_sessions`: `phone`, `session_id` (chave do arquivo de credencial), `name` (apelido opcional editável).
  - **`StringSession` (credencial) NÃO fica aqui** — só no `/app/sessions/*.json` no container `telegram-account-webhook-telegram`.
  - Credenciais do app Telegram (`api_id`/`api_hash`) ficam nos env vars do container, não no PB.
- `telegram_webhooks`: `name`, `enabled`, `url` + filtros (`direction`, `chat_type`, `text_match`).
  - Relation com `telegram_sessions` (`cascadeDelete`). Vários webhooks por sessão.
  - O PB é source of truth — o arquivo é só pra carregar o cliente Telethon de volta no boot.
- `telegram_messages`: `session` (relation), `chat_id`, `chat_type`, `chat_title`, `direction` (incoming|outgoing), `sender_id`, `sender_name`, `text`, `created`. **Append-only** (updateRule e deleteRule = null). O FastAPI faz INSERT em toda mensagem (incoming + outgoing) que chega — é o audit log completo. O hook do PB é no-op (não faz forwarding).

Schema inicial em `pocketbase/pb_migrations/1791780600_create_telegram_sessions.js`. Mudanças posteriores (alias, webhooks, etc.) via migrations idempotentes (regra: nunca editar uma migration depois de commitada — sempre criar uma nova).

---

## Status

🚧 **Em desenvolvimento ativo.**

## License

MIT
