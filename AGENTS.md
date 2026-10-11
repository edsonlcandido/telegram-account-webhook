# Telegram Account Webhook

Sistema para conectar contas Telegram e enviar mensagens em tempo real via webhook.

## Arquitetura

```
Usuário → Landing Page → Web App → PocketBase (auth)
                                   ↓
                            Backend (VPS)
                              ↕ Telethon
                          Telegram API
                              ↓
                     Webhook → Cliente
```

## Stack

- **Landing**: Vue 3 + Vite
- **Web App**: Vue 3 + Tailwind + Pinia + Vue Router
- **Backend**: Python + FastAPI + Telethon
- **Database**: PocketBase (standalone)
- **Deploy**: Easypanel

## Estrutura

```
telegram-account-webhook/
├── apps/
│   ├── landing/           # Landing page
│   │   ├── index.html
│   │   └── src/
│   └── web/              # Aplicação web
│       ├── src/
│       │   ├── App.vue
│       │   ├── main.ts
│       │   ├── router/
│       │   ├── services/pocketbase.ts
│       │   ├── stores/auth.ts
│       │   └── views/
│       └── vite.config.ts
├── pocketbase/            # PocketBase binary + config
├── scripts/               # Scripts utilitários
├── Dockerfile
└── AGENTS.md
```

## Deploy

**Webhook para deploy automático:**
```
http://82.112.244.9:3000/api/deploy/d08148ad7475ab169bc6b4baac629cc1c0e18c900b11d525
```

Push para `main` = deploy automático via Easypanel.

## Variáveis de Ambiente

### PocketBase
```env
POCKETBASE_URL=http://localhost:8090
```

### Frontend
```env
VITE_POCKETBASE_URL=https://telegram-webhook.seu-dominio.com
```

## Coleções PocketBase

- `users`: Usuários (auth nativo)
- `telegram_accounts`: phone, api_id, api_hash, is_authorized
- `webhooks`: webhook_url, filter_tipo, account_id

## API Backend (futuro)

| Method | Endpoint | Descrição |
|--------|----------|-----------|
| POST | /api/auth/send-code | Envia código Telegram |
| POST | /api/auth/verify | Verifica código |
| POST | /api/webhook/configure | Configura webhook |
| GET | /health | Health check |

## Comandos

```bash
# Dev
npm run dev          # Roda tudo (PB + Landing + Web)

# Build
npm run build        # Builda landing + web

# Preview
npm run preview      # Preview do PocketBase
```

## Importante

- Deploy via Easypanel (VPS)
- Backend Python ainda não implementado (precisa criar)
- Landing page + Web app já existem
- PocketBase é standalone para este projeto
