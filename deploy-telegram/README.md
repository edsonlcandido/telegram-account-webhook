# Telegram Account Webhook - Deploy

Backend que conecta contas Telegram e encaminha mensagens para webhooks.

## Fluxo

```
Usuário → Página Web → Cria Conta → Parea Telegram
                                              ↓
                                Telegram API fica ouvindo
                                              ↓
                                Nova mensagem recebida
                                              ↓
                                POST para seu webhook (N8N)
```

## Pré-requisitos

1. Conta no [my.telegram.org](https://my.telegram.org)
2. VPS com Docker (Easypanel ou outro)

## Deploy no Easypanel

### Passo 1: Upload

1. Compacte esta pasta em `deploy-telegram.tar.gz`
2. No Easypanel, crie novo serviço
3. Upload do arquivo

### Passo 2: Configurar

| Campo | Valor |
|-------|-------|
| Nome | `telegram-api` |
| Build Type | Docker |
| Dockerfile | `Dockerfile.Telegram` |
| Porta | `8000` |

### Passo 3: Variáveis de Ambiente

| Variável | Descrição | Exemplo |
|----------|-----------|---------|
| `POCKETBASE_URL` | URL do PocketBase (Application) | `http://seu-servidor:8090` |
| `TG_API_ID` | API ID do Telegram | `123456` |
| `TG_API_HASH` | API Hash do Telegram | `abcdef123456...` |

### Passo 4: Build

Execute o build no painel.

## Variáveis de Ambiente (Easypanel)

```
POCKETBASE_URL=http://ip-do-seu-vps:8090
TG_API_ID=12345
TG_API_HASH=abcdef1234567890abcdef1234567890
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```
```json
{"status":"ok","active_sessions":2,"api_configured":true}
```

### Listar Sessões
```bash
curl http://localhost:8000/api/sessions
```

### Configurar Webhook
```bash
curl -X POST http://localhost:8000/api/set-webhook \
  -H "Content-Type: application/json" \
  -d '{"session_id":"account_5511999999999","webhook_url":"https://seu-n8n.com/webhook/telegram"}'
```

## Formato das Mensagens no Webhook

Quando uma nova mensagem chega, seu webhook recebe:

```json
{
  "session_id": "account_5511999999999",
  "chat_id": -1001234567890,
  "message_id": 123,
  "text": "Olá, tudo bem?",
  "sender_id": 987654321,
  "sender_name": "João Silva",
  "timestamp": "2026-10-11T20:00:00"
}
```

## Para Desenvolvedores

### Desenvolvimento Local

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Configurar variáveis
export TG_API_ID=12345
export TG_API_HASH=seu_hash
export POCKETBASE_URL=http://localhost:8090

# 3. Rodar
uvicorn main:app --reload --port 8000
```

### Testar Webhook

```bash
curl -X POST "http://localhost:8000/api/test-webhook?webhook_url=https://seu-webhook.com/test"
```

## Solução de Problemas

### "TG_API_ID ou TG_API_HASH não configurados"
- Verifique se as variáveis de ambiente estão setadas corretamente
- Reinicie o serviço após configurar

### Sessão não conecta
- Verifique se o número de telefone está correto (com código do país)
- Telegram pode bloquear números novos - aguarde alguns minutos

### Webhook não recebe mensagens
- Teste com `/api/test-webhook`
- Verifique se o webhook está acessível publicamente
- Logs: `docker logs telegram-api`
