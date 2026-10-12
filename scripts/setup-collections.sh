#!/bin/bash
# Script para criar collections no PocketBase via Admin API

POCKETBASE_URL="${POCKETBASE_URL:-http://localhost:8090}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin123456}"

# Login como admin
echo "🔐 Fazendo login no PocketBase..."
TOKEN=$(curl -s -X POST "$POCKETBASE_URL/api/admins/auth-with-password" \
  -H "Content-Type: application/json" \
  -d "{\"identity\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
  | jq -r '.token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
  echo "❌ Erro ao fazer login. Verifique as credenciais."
  exit 1
fi

echo "✅ Login realizado com sucesso!"

# Criar collection telegram_sessions
echo "📦 Criando collection telegram_sessions..."
curl -s -X POST "$POCKETBASE_URL/api/collections" \
  -H "Content-Type: application/json" \
  -H "Authorization: $TOKEN" \
  -d @collections/telegram_sessions.json

echo ""
echo "✅ Collections criadas com sucesso!"
