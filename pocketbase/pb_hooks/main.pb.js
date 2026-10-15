/// <reference path="../pb_data/types.d.ts" />

// Landing page na raiz (sem fallback SPA pq a landing é estática)
routerAdd("GET", "/{path...}", $apis.static("pb_public", false))

// Web app em /app/* com fallback SPA (index.html) pra sub-rotas do Vue Router
// tipo /app/dashboard. Sem isso, qualquer sub-rota retorna 404.
routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", true))

// =============================================================================
// Hook: telegram_messages — NO-OP
// =============================================================================
// O forwarding pros webhooks é responsabilidade do FastAPI/Telethon
// service (handle_new_message em backend/main.py). Razão: o container do
// PB não tem egress liberado pra certos IPs externos (Easypanel network
// ACL), então $http.send trava. O Telethon service JÁ tem egress OK
// (fala com Telegram API o tempo todo) e Python httpx com timeout.
//
// Este hook só loga que o record foi criado (audit). NÃO chama
// $http.send. Se quiser reativar o forwarding aqui no futuro, é só
// restaurar a lógica anterior — mas antes garanta que o container do
// PB tem egress pra todas as URLs externas que os webhooks usam.
// =============================================================================

onRecordAfterCreateSuccess((e) => {
  console.log(
    "telegram_messages hook: msg=" + e.record.id +
    " (audit-only — forwarding é feito pelo telegram-api service)"
  )
}, "telegram_messages")