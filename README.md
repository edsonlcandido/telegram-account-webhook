# Telegram Account Webhook

Vincule contas Telegram e receba mensagens em tempo real via webhook.

## O que faz

- **Vincular conta Telegram**: phone_number + código de verificação
- **Receber mensagens**: webhook URL para cada conta
- **Gerenciar múltiplas contas**: painel unificado

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Easypanel VPS                                   │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Serviço 1: Application (Dockerfile.Application)                   │ │
│  │  ────────────────────────────────────────────────────────────────  │ │
│  │  • PocketBase (Database + Auth)         → :8090                  │ │
│  │  • Landing Page (Vue)                   → /                       │ │
│  │  • Web App (Vue)                        → /app/                   │ │
│  │                                                                   │ │
│  │  Variáveis de ambiente:                                          │ │
│  │  • TELEGRAM_API_URL=http://telegram-api:8000                    │ │
│  │                                                                   │ │
│  │  URL Pública: https://telegram-webhook.ehtudo.app/                │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                    │                                    │
│                                    │ HTTP (interno Docker)              │
│                                    ▼                                    │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Serviço 2: Telegram API (Dockerfile.Telegram)                   │ │
│  │  ────────────────────────────────────────────────────────────────  │ │
│  │  • FastAPI (REST API)                     → :8000                 │ │
│  │  • Telethon (Sessões Telegram)                                  │ │
│  │                                                                   │ │
│  │  URL Interna: http://telegram-api:8000                           │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Comunicação Interna Docker

O PocketBase (serviço Application) se comunica com o Telegram API via **rede Docker interna**:

```
Application → http://telegram-api:8000/api/...
```

**Importante:** A variável `TELEGRAM_API_URL` deve ser configurada no serviço Application.

---

## Estrutura do Projeto

```
telegram-account-webhook/
├── Dockerfile.Application          # PocketBase + Frontend Vue
├── Dockerfile.Telegram            # FastAPI + Telethon
├── backend/
│   ├── main.py                    # API FastAPI
│   ├── requirements.txt           # Deps Python
│   └── .env.example              # Template de variáveis
├── apps/
│   ├── landing/                   # Landing page Vue
│   └── web/                       # Web app Vue
├── pocketbase/
│   ├── pb_hooks/                 # Hooks customizados (SPA routing)
│   │   └── main.pb.js
│   └── pb_migrations/            # Migrations banco
├── .agents/
│   └── skills/
│       └── pocketbase-gotchas.md # Gotchas PocketBase 0.40.x
├── docker-compose.yml             # Desenvolvimento local
├── README.md
└── AGENTS.md
```

---

## Variáveis de Ambiente

### Serviço 1: Application (PocketBase)

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `TELEGRAM_API_URL` | URL do serviço Telegram API (rede interna) | `http://telegram-api:8000` |
| `VITE_POCKETBASE_URL` | URL pública do PocketBase (para o frontend) | `https://telegram-webhook.ehtudo.app` |

### Serviço 2: Telegram API

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `POCKETBASE_URL` | URL do PocketBase (rede interna) | `http://pocketbase:8090` |
| `TG_API_ID` | API ID do Telegram | `123456` |
| `TG_API_HASH` | API Hash do Telegram | `abc123...` |

---

## Tech Stack

| Camada | Tecnologia |
|--------|-----------|
| Frontend | Vue 3 + TypeScript + Tailwind CSS |
| Backend API | Python + FastAPI + Telethon |
| Database | PocketBase 0.40.5 |
| Deploy | Easypanel (2 serviços separados) |

---

## Desenvolvimento Local

```bash
# 1. Clone e entre no projeto
git clone https://github.com/edsonlcandido/telegram-account-webhook.git
cd telegram-account-webhook

# 2. Configure variáveis de ambiente
cp backend/.env.example backend/.env
# Edite backend/.env com suas credenciais Telegram

# 3. Suba tudo com Docker Compose
docker compose up -d

# 4. Acesse
# - Landing Page: http://localhost:5173
# - Web App: http://localhost:5174
# - PocketBase: http://localhost:8090
```

---

## Deploy no Easypanel

### Passo 1: Configurar GitHub Secrets

No repositório GitHub, adicione estes secrets:

| Secret | Valor |
|--------|-------|
| `GITHUB_TOKEN` | Automático (já vem com GitHub Actions) |
| `TG_API_ID` | Seu API ID do Telegram (my.telegram.org) |
| `TG_API_HASH` | Seu API Hash do Telegram |
| `EASYPANEL_APPLICATION_WEBHOOK` | Webhook URL do serviço Application |
| `EASYPANEL_TELEGRAM_WEBHOOK` | Webhook URL do serviço Telegram API |

### Passo 2: Criar os serviços no Easypanel

**Serviço 1 - Application:**
- Nome: `telegram-account-webhook`
- Imagem: `ghcr.io/edsonlcandido/telegram-account-webhook/application:latest`
- Porta: 8090
- Volume: `pb_data` → `/app/pb_data`
- **Variáveis de ambiente:**
  - `TELEGRAM_API_URL=http://telegram-api:8000`

**Serviço 2 - Telegram API:**
- Nome: `telegram-api`
- Imagem: `ghcr.io/edsonlcandido/telegram-account-webhook/telegram:latest`
- Porta: 8000
- Variáveis de ambiente:
  - `POCKETBASE_URL=http://pocketbase:8090`
  - `TG_API_ID=<seu_api_id>`
  - `TG_API_HASH=<seu_api_hash>`

### Passo 3: Push para deploy

```bash
git push origin main
```

O GitHub Actions vai:
1. Buildar e pushar a imagem `application` no ghcr.io
2. Buildar e pushar a imagem `telegram` no ghcr.io
3. Disparar os webhooks do Easypanel para cada serviço

---

## API Endpoints

### Telegram API (serviço interno)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/health` | Health check |
| POST | `/api/send-code` | Envia código de verificação |
| POST | `/api/verify-code` | Verifica código e cria sessão |
| POST | `/api/set-webhook` | Configura webhook para conta |
| DELETE | `/api/session` | Remove sessão |
| GET | `/api/sessions` | Lista sessões ativas |

### PocketBase (Admin)

- Admin UI: `https://telegram-webhook.ehtudo.app/_/`
- API: `https://telegram-webhook.ehtudo.app/api/`

---

## Coleções PocketBase

- `users`: Usuários (auth nativo)
- `telegram_sessions`: phone, session_id, name (alias opcional, editável)
  - `StringSession` (credencial) só em `/app/sessions/*.json` no container `telegram-api`.
- `telegram_webhooks`: name, enabled, url + filtros (direction, chat_type, text_match)
  - Relation com `telegram_sessions` (cascadeDelete). Vários webhooks por sessão.

---

## Status

⚠️ **Em desenvolvimento**

## License

MIT
