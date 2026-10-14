/// <reference path="../pb_data/types.d.ts" />

// Cria a collection `telegram_messages` — buffer centralizado de mensagens
// recebidas do Telethon, processado pelo hook `onRecordAfterCreate`
// em pb_hooks/main.pb.js. Cada mensagem vira 1 record, e o hook
// distribui pros webhooks ativos da sessão, aplicando os filtros
// configurados em `telegram_webhooks` (direction, chat_type, text_match).
//
// Por que centralizar no PB: o handler do Telethon (FastAPI) roda em
// background sem request HTTP, então não tem token de user disponível
// pra listar webhooks. Antes, isso era contornado com cache em memória
// (_SESSION_OWNER, _USER_TOKENS) que falhava em vários cenários. Agora
// o FastAPI só faz INSERT (autenticado) e o hook do PB faz o resto
// (roda DENTRO do PB, sem precisar de auth).
//
// createRule: "@request.auth.id != ''" — qualquer user autenticado pode
// inserir. Os dados não são sensíveis (são mensagens que o webhook
// também vai receber), e o FastAPI insere com o user token do dono
// da sessão (cacheado). Permissivo pra evitar ter que armazenar
// admin/superuser token no FastAPI.

migrate(
  (app) => {
    let messages
    try {
      messages = app.findCollectionByNameOrId("telegram_messages")
    } catch {
      messages = null
    }
    if (messages) return // idempotente

    const sessions = app.findCollectionByNameOrId("telegram_sessions")

    messages = new Collection({
      name: "telegram_messages",
      type: "base",
      listRule: "@request.auth.id != ''",
      viewRule: "@request.auth.id != ''",
      createRule: "@request.auth.id != ''",
      // Append-only — mensagens não são editáveis/deletáveis pelo user.
      // O hook pode atualizar campos auxiliares (delivered, error) usando
      // o superuser, mas o user normal não pode mutar.
      updateRule: null,
      deleteRule: null,
      fields: [
        {
          name: "session",
          type: "relation",
          required: true,
          collectionId: sessions.id,
          cascadeDelete: true,
          minSelect: 1,
          maxSelect: 1,
        },
        // Identificação do chat no Telegram
        { name: "chat_id", type: "number", required: true },
        { name: "chat_type", type: "select", required: false,
          values: ["private", "group", "supergroup", "channel", "unknown"],
          maxSelect: 1 },
        { name: "chat_title", type: "text", max: 200, required: false },

        // Direção (incoming = recebida, outgoing = enviada pelo user)
        { name: "direction", type: "select", required: true,
          values: ["incoming", "outgoing"],
          maxSelect: 1 },

        // Sender (pode ser null em canais)
        { name: "sender_id", type: "number", required: false },
        { name: "sender_name", type: "text", max: 200, required: false },

        // Conteúdo
        { name: "text", type: "text", max: 5000, required: false },
        // Payload cru do Telethon (debug / filtros avançados)
        { name: "raw", type: "json", required: false },

        // Auditoria do hook
        { name: "delivered_count", type: "number", required: false },
        { name: "delivery_error", type: "text", max: 500, required: false },
      ],
      indexes: [
        "CREATE INDEX idx_telegram_messages_session ON telegram_messages (session)",
        "CREATE INDEX idx_telegram_messages_chat ON telegram_messages (chat_id)",
      ],
    })
    app.save(messages)
  },
  (app) => {
    // down — best-effort
    try {
      app.delete(app.findCollectionByNameOrId("telegram_messages"))
    } catch {}
  },
)
