# Telegram Account Webhook

Sistema para conectar contas Telegram e enviar mensagens em tempo real via webhook.

## Arquitetura

```
Usuário → Frontend (Vue) → Backend (FastAPI) → Telegram API (Telethon)
                          ↓                          ↓
                    PocketBase (auth + dados)  Webhook → Cliente
```

## Stack

- **Frontend**: Vue 3 + TypeScript + Vite
- **Backend**: Python + FastAPI + Telethon
- **Database**: PocketBase (instância separada deste projeto)
- **Auth**: JWT tokens

## Estrutura

```
telegram-account-webhook/
├── src/                          # Frontend Vue
│   ├── main.ts
│   ├── App.vue                   # Landing page + Dashboard
│   ├── views/
│   │   ├── LandingView.vue       # Landing page
│   │   └── DashboardView.vue    # Painel do usuário
│   ├── components/
│   │   ├── AccountForm.vue      # Vincular conta Telegram
│   │   ├── SessionList.vue      # Lista de contas
│   │   └── WebhookConfig.vue    # Configurar webhook
│   ├── api/
│   │   └── index.ts             # API client
│   ├── types/
│   │   └── index.ts
│   └── composables/
│       └── useTelegram.ts
├── backend/
│   ├── main.py                  # FastAPI app
│   ├── telethon_manager.py      # Gerencia sessões Telethon
│   ├── webhook_sender.py        # Envia mensagens para webhook
│   └── auth.py                  # JWT + integração PocketBase
├── pocketbase/                   # PocketBase standalone
│   └── pb_data/                 # Dados do banco
├── Dockerfile
└── AGENTS.md
```

## Funcionalidades

- ✅ Landing page para apresentar o serviço
- ✅ Cadastro/login de usuários (via PocketBase)
- ✅ Vincular conta Telegram via phone + api_id/api_hash
- ✅ Verificação em 2 fatores (código SMS/Telegram)
- ✅ Configurar URL de webhook por conta
- ✅ Filtrar por tipo: pessoal, grupo, canal, todos
- ✅ Testar se webhook está respondendo
- ✅ Múltiplas contas por usuário

## Coleções PocketBase

- `users`: Usuários do sistema (auth)
- `telegram_accounts`: Contas vinculadas
  - user_id, phone, api_id, api_hash, is_authorized
- `webhooks`: Configurações de webhook
  - account_id, webhook_url, filter_tipo, active

## Fluxo de Uso

1. Usuário acessa landing page
2. Faz cadastro/login
3. Vincula conta Telegram
4. Recebe código no Telegram/SMS
5. Configura URL do webhook
6. Sistema começa a enviar mensagens em tempo real

## API Endpoints (Backend)

| Method | Endpoint | Descrição |
|--------|----------|-----------|
| POST | /api/auth/register | Cadastro |
| POST | /api/auth/login | Login (retorna JWT) |
| POST | /api/telegram/send-code | Envia código Telegram |
| POST | /api/telegram/verify | Verifica código |
| GET | /api/telegram/accounts | Lista contas |
| DELETE | /api/telegram/accounts/:id | Remove conta |
| POST | /api/webhook/configure | Configura webhook |
| POST | /api/webhook/test | Testa webhook |
| GET | /health | Health check |

## Payload Enviado ao Webhook

```json
{
  "event": "new_message",
  "account_id": "acc_123",
  "chat_id": -100123456,
  "chat_name": "Nome do Grupo",
  "chat_type": "grupo",
  "message_id": 123,
  "from_name": "João Silva",
  "from_id": 999,
  "text": "Olá!",
  "date": "2024-01-15T10:30:00Z",
  "has_media": false
}
```

## Variáveis de Ambiente

### Backend (.env)
```env
POCKETBASE_URL=https://telegram-webhook.seu-dominio.com
POCKETBASE_TOKEN=***
JWT_SECRET=your-secret-key
SESSION_DIR=/app/sessions
```

### Frontend (.env)
```env
VITE_API_URL=http://localhost:8000
VITE_PB_URL=https://telegram-webhook.seu-dominio.com
```

## Desenvolvimento

```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend
npm install
npm run dev

# PocketBase
./pocketbase serve
```

## Deploy

### Docker (tudo junto)
```bash
docker build -t telegram-webhook .
docker run -p 8000:8000 -p 8090:8090 -v ./data:/pb_data -v ./sessions:/app/sessions telegram-webhook
```

## Importante

- PocketBase é standalone para este projeto
- Sessões Telethon persistidas em `/app/sessions/`
- JWT para autenticação backend ↔ frontend
- Webhook é only-envio (não recebe comandos)
