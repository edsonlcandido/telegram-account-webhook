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
| `POST` | `/api/send-message` | sim | Envia mensagem via sessão. Aceita `text` (opcional se tem `image_url`), `parse_mode` (`plain`/`html`), `image_url` (URL pública validada contra SSRF), `reply_to_message_id`. Schema completo na seção "Enviar mensagem". |
| `POST` | `/api/integration-token` | sim | Gera um token do PB pro usuário logado (via endpoint `impersonate`), pra usar de fora. Ver "Token de integração". |
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
    "name": "Vendas",
    "user": {
      "id": 5511932055173,
      "first_name": "Edson",
      "last_name": "Cândido",
      "username": "edsonlcandido",
      "phone": "+5511932055173",
      "is_bot": false,
      "is_verified": false,
      "is_premium": true,
      "is_scam": false,
      "is_fake": false,
      "is_contact": false,
      "is_mutual_contact": false,
      "lang_code": "pt-br"
    }
  },
  "from": {
    "id": 7892418175,
    "first_name": "João",
    "last_name": "Silva",
    "username": "joaosilva",
    "phone": "",
    "is_bot": false,
    "is_verified": false,
    "is_premium": false,
    "is_scam": false,
    "is_fake": false,
    "is_contact": false,
    "is_mutual_contact": false,
    "lang_code": "pt-br"
  },
  "chat": {
    "id": 7892418175,
    "type": "private",
    "title": "João Silva",
    "username": "joaosilva",
    "is_verified": false,
    "is_creator": false,
    "participants_count": null,
    "about": "",
    "has_protected_content": false
  },
  "message": {
    "id": 51689,
    "chat_id": -1003350466807,
    "chat_type": "group",
    "chat_title": "Nome do grupo",
    "direction": "incoming",
    "sender_id": 987654321,
    "sender_name": "Fulano",
    "sender_username": "fulanotelegram",
    "text": "oi, tudo bem?",
    "timestamp": "2026-10-15T11:00:00+00:00",
    "reply_to_msg_id": null
  }
}
```

**Estrutura de alto nível:**

- **`event`**: `"telegram.message"` (reservado pra outros tipos no futuro).
- **`webhook_id` / `webhook_name`**: identificação do webhook que recebeu (útil quando há vários webhooks na mesma sessão).
- **`session`**: a conta Telegram que recebeu/mandou a mensagem. `session.user` é a própria conta (com `is_premium`, `username` etc).
- **`from`**: quem mandou a mensagem (User object completo do Telethon, com fallback via `get_entity` se o cache vier vazio). Vem `null` se for mensagem de canal (sender é o canal, não user). Pra outgoing messages, `from` = a própria conta (igual a `session.user`).
- **`chat`**: onde a mensagem foi mandada — User (privado), Group/Supergroup, ou Channel. `title` é resolvido polimorficamente (title de Chat/Channel OU `first_name + last_name` de User privado). `type` é `"private" | "group" | "supergroup" | "channel" | "unknown"`. Tem `username`, `participants_count` (grupos), `about` (descrição do grupo), `has_protected_content`, `is_verified`, `is_creator`.
- **`message`**: a mensagem em si. Mantém os campos legados (`chat_id`, `sender_id`, `sender_name`, etc) pra não quebrar consumers existentes; adiciona `reply_to_msg_id` no fim.

**Campos importantes:**

- `message.direction`: `"incoming"` (recebida) ou `"outgoing"` (enviada pela própria conta via Telegram app/desktop, Telegram Desktop, web.telegram.org, ou nosso `/api/send-message`). Detecção via OR de 2 sinais: `event.outgoing` do Telethon (True só quando o PRÓPRIO Telethon enviou) **OU** `from.id == session.user.id` (cobre o caso de mensagem enviada via outro client do mesmo user).
- `message.sender_username` / `from.username`: `@username` do sender no Telegram **sem o `@`** (ex: `fulanotelegram`). Vem string vazia se o sender não tiver username configurado, ou se for um canal. Mais útil que `sender_name` pra identificar users em mensagens privadas — `sender_name` pode mudar se o user editar o perfil, `@username` é estável.
- `from.is_premium` / `chat.is_verified`: badges do Telegram úteis pra ranking/filtros.
- `message.timestamp`: ISO 8601 UTC (data da mensagem no Telegram).
- `message.reply_to_msg_id`: id da mensagem à qual esta é uma reply (`null` se não for reply).
- `chat.participants_count`: count de membros do grupo/canal. `null` em chat privado.

**Anti-loop:** o handler suprime forwarding (mas NÃO o audit log em `telegram_messages`) pra mensagens que a própria API enviou via `/api/send-message` nos últimos 10s, evitando loop com o receptor do webhook (ex: n8n respondendo às nossas mensagens).

---

## Enviar mensagem (`POST /api/send-message`)

Envia uma mensagem (texto, foto, ou ambos) via uma sessão Telegram ativa. Esse é o endpoint que o consumidor do webhook (ex: n8n) chama pra responder o chat de origem.

**Auth:** `Authorization: Bearer <jwt-do-pocketbase>`.

> **Precisa de um token e está fora do painel?** Gere o seu em `/app/docs`, no card
> **"Token de integração"** (seção 2 da documentação da API). Ele vira o header
> `Authorization` pra qualquer sistema externo — n8n, Make, backend próprio.
> Detalhes em "Token de integração".

**Request body:**

```json
{
  "session_id": "account_5511932055173",
  "chat_id": 7892418175,
  "text": "Olá! Recebi sua mensagem.",
  "parse_mode": "plain",
  "image_url": "https://example.com/foto.jpg",
  "reply_to_message_id": 51689
}
```

| Campo | Tipo | Obrigatório | Descrição |
|---|---|---|---|
| `session_id` | `string` | sim | ID da sessão Telegram (vem do payload do webhook: `session.session_id`) |
| `chat_id` | `int` ou `string` | sim | ID numérico do chat **ou** `@username` (com `@`, ex: `"@fulanotelegram"`) |
| `text` | `string` | um dos | Texto da mensagem. **Obrigatório se não tem `image_url`**. Se combinado com `image_url`, vira a caption da foto. |
| `parse_mode` | `"plain"` \| `"html"` | não (default `"plain"`) | Subset HTML do Telegram Bot API. Tags permitidas: `b strong i em u s strike del code pre a`. Atributos permitidos: `a[href]`. Outros tags/attrs são rejeitados com `400`. |
| `image_url` | `string` (URL http/https) | um dos | URL pública da foto. **Validada contra SSRF** — esquema tem que ser `http`/`https`, host não pode resolver pra IP privado/loopback/link-local/multicast/reserved/unspecified. |
| `reply_to_message_id` | `int` | não | ID da mensagem à qual essa é uma reply (vem de `message.id` ou `message.reply_to_msg_id` no payload do webhook). |

**Comportamento:**

- Se tiver `text` E `image_url` → envia como foto com caption (text)
- Se tiver só `image_url` → envia foto sem caption
- Se tiver só `text` → envia mensagem de texto
- Se não tiver nenhum dos dois → `400 "Informe text ou image_url"`

**Response 200:**

```json
{
  "success": true,
  "message_id": 51690,
  "chat_id": 7892418175,
  "timestamp": "2026-10-15T12:00:00+00:00",
  "is_reply": true,
  "parse_mode": "plain",
  "has_media": false,
  "media_type": null
}
```

| Campo | Tipo | Descrição |
|---|---|---|
| `success` | `bool` | Sempre `true` em 200 |
| `message_id` | `int` | ID da mensagem enviada (usar pra reply/track) |
| `chat_id` | `int` | Chat resolvido (numérico, mesmo se você mandou `@username`) |
| `timestamp` | `string` (ISO 8601) | Data da mensagem no Telegram |
| `is_reply` | `bool` | `true` se foi enviada com `reply_to_message_id` |
| `parse_mode` | `string` \| `null` | O `parse_mode` que foi aplicado (sempre `null` se foi só foto sem caption) |
| `has_media` | `bool` | `true` se incluiu foto |
| `media_type` | `"photo"` \| `null` | Tipo da mídia enviada |

**Errors comuns:**

- `400 "Informe text ou image_url"` — nem text nem image_url foram passados
- `400 "HTML inválido: ..."` — text tem tag/attr fora do subset (mais clara que `MsgStyleParseError` do Telethon)
- `400 "image_url inválida: scheme inválido: ftp"` — URL não é http/https
- `400 "image_url inválida: host resolve para IP bloqueado: 10.0.0.5"` — host resolve pra IP privado/loopback
- `404 "Sessão não encontrada ou offline"` — `session_id` não tá em `active_clients` (Telethon não conectou ou sessão foi removida)
- `400 "FloodWaitError: ..."` (ou outros erros do Telethon) — rate limit, sem permissão pra escrever no chat, peer inválido, etc. A `detail` da response 400 tem a mensagem original do Telethon.

**Anti-loop automático:** a mensagem enviada é marcada no `_RECENTLY_SENT_IDS` por 10s. Quando o Telethon emite o evento `outgoing` dessa mensagem, o `handle_new_message` suprime o POST do webhook (mas o INSERT em `telegram_messages` audit log continua). Evita loop: webhook chega → n8n chama `/api/send-message` → webhook chega de novo → n8n chama de novo → ...

**Exemplo de fluxo completo (n8n):**

```text
1. Telegram msg chega → POST webhook pro n8n
2. n8n processa, decide responder
3. n8n: POST https://api-telegram.ehtudo.app/api/send-message
   body: {
     "session_id": "{{ $json.session.session_id }}",
     "chat_id": {{ $json.message.chat_id }},
     "text": "Recebido!",
     "reply_to_message_id": {{ $json.message.id }}
   }
4. FastAPI envia via Telethon
5. Telethon emite outgoing event → handler INSERT em telegram_messages
   (audit), mas SUPRIME o POST pro n8n (já viu essa msg em < 10s)
```

---

## Token de integração (`POST /api/integration-token`)

Pra chamar o `/api/send-message` (ou qualquer outro endpoint) **de fora do
painel** — n8n, Make, backend próprio — você precisa de um token no header
`Authorization`. O JWT da sessão do navegador expira, então não serve pra
automação.

O painel gera um token sob demanda em **`/app/docs`**, no card **"Token de
integração"** (seção 2 da documentação da API). O botão chama o endpoint
`impersonate` do PocketBase, que é o mesmo mecanismo do **Impersonate** do Admin
UI.

**Request body (opcional):**

```json
{ "duration": 2592000 }
```

| Campo | Tipo | Default | Descrição |
|---|---|---|---|
| `duration` | `int` (segundos) | `2592000` (30 dias) | Validade do token. Clamp no servidor: mínimo `300` (5 min), máximo `31536000` (365 dias). |

**Response 200:**

```json
{
  "success": true,
  "token": "eyJhbGciOi...",
  "expires_at": 1792966160,
  "duration": 2592000,
  "user": { "id": "...", "email": "voce@exemplo.com" }
}
```

**Exemplo com curl:**

```bash
curl -X POST https://api-telegram.ehtudo.app/api/integration-token \
  -H "Content-Type: application/json" \
  -H "Authorization: <SEU_JWT_DO_PAINEL>" \
  -d '{"duration": 2592000}'
```

### O que você precisa saber antes de usar

- **O token é do usuário que está logado.** O endpoint não aceita `user_id` no
  body — o id vem do JWT verificado. Ninguém consegue pedir token de outra conta.
- **É estático: não renova.** O `impersonate` do PB gera um token com `exp` fixo.
  Quando vence, você gera outro.
- **Não tem revogação individual.** O PB é stateless e não tem endpoint de
  logout. Gerar outro token **não** invalida o anterior — os dois valem até o
  próprio prazo. Para invalidar de verdade, troque a senha do usuário no Admin UI
  do PB (isso rotaciona o `tokenKey` dele e derruba todos os tokens dele).
- **Escopo = usuário inteiro, não só `send-message`.** Quem tiver o token também
  pode criar/deletar webhooks e sessões. Trate como credencial sensível: variable
  de ambiente no sistema externo, nunca no git.
- **Não é persistido.** Nem no PB (é stateless), nem no navegador. O card mostra
  uma vez; se você sair da página sem copiar, perdeu.

**Erros:** `401` não autenticado · `404` usuário não encontrado no PB ·
`502` o PB recusou a geração · `503` superuser do PB não configurado (falta
`POCKETBASE_SERVICE_TOKEN` ou `POCKETBASE_ADMIN_EMAIL`+`PASSWORD` no serviço).

---

## Coleções PocketBase

- `users`: Auth nativo do PB (email/senha → JWT).
- `telegram_sessions`: `phone`, `session_id` (chave do arquivo de credencial), `name` (apelido opcional editável).
  - **`StringSession` (credencial) NÃO fica aqui** — só no `/app/sessions/*.json` no container `telegram-account-webhook-telegram`.
  - Credenciais do app Telegram (`api_id`/`api_hash`) ficam nos env vars do container, não no PB.
- `telegram_webhooks`: `name`, `enabled`, `url` + filtros (`direction`, `chat_type`, `text_match`).
  - Relation com `telegram_sessions` (`cascadeDelete`). Vários webhooks por sessão.
  - O PB é source of truth — o arquivo é só pra carregar o cliente Telethon de volta no boot.
- `telegram_messages`: `session` (relation), `chat_id`, `chat_type`, `chat_title`, `direction` (incoming|outgoing), `sender_id`, `sender_name`, `sender_username` (@username sem @, opcional), `text`, `created`. **Append-only** (updateRule e deleteRule = null). O FastAPI faz INSERT em toda mensagem (incoming + outgoing) que chega — é o audit log completo. O hook do PB é no-op (não faz forwarding).

Schema inicial em `pocketbase/pb_migrations/1791780600_create_telegram_sessions.js`. Mudanças posteriores (alias, webhooks, etc.) via migrations idempotentes (regra: nunca editar uma migration depois de commitada — sempre criar uma nova).

---

## Status

🚧 **Em desenvolvimento ativo.**

## License

MIT
