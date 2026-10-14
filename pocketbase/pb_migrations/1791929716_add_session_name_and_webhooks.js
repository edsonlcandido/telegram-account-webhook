/// <reference path="../pb_data/types.d.ts" />

// Adiciona campo `name` (alias) em telegram_sessions e cria a collection
// `telegram_webhooks` para suportar múltiplos webhooks por sessão com filtros
// (direction, chat_type, text_match).
//
// Também migra os webhooks legados: pra cada record em `telegram_sessions` com
// `webhook_url` não-vazio, cria 1 webhook correspondente em `telegram_webhooks`.
// O campo `webhook_url` é mantido por 1 release pra UI legada não quebrar;
// uma migration futura (release+1) remove.

migrate((app) => {
  // 1) Adiciona `name` em telegram_sessions
  const sessions = app.findCollectionByNameOrId("telegram_sessions")
  sessions.fields.add({ name: "name", type: "text", max: 60, required: false })
  app.save(sessions)

  // 2) Cria telegram_webhooks
  const webhooks = new Collection({
    name: "telegram_webhooks",
    type: "base",
    listRule: "@request.auth.id != ''",
    viewRule: "@request.auth.id != ''",
    createRule: "@request.auth.id != ''",
    updateRule: "@request.auth.id != ''",
    deleteRule: "@request.auth.id != ''",
    fields: [
      {
        name: "session",
        type: "relation",
        required: true,
        options: {
          collectionId: sessions.id,
          cascadeDelete: true,
          maxSelect: 1,
          minSelect: 1,
        },
      },
      {
        name: "name",
        type: "text",
        max: 60,
        required: false,
      },
      {
        name: "url",
        type: "url",
        required: true,
        options: {
          exceptDomains: null,
          onlyDomains: null,
          preview: true,
        },
      },
      {
        name: "enabled",
        type: "bool",
        required: false,
      },
      {
        name: "filter_direction",
        type: "select",
        required: false,
        options: {
          maxSelect: 1,
          values: ["all", "incoming", "outgoing"],
        },
      },
      {
        name: "filter_chat_type",
        type: "select",
        required: false,
        options: {
          maxSelect: 1,
          values: ["all", "private", "group", "supergroup", "channel"],
        },
      },
      {
        name: "filter_text_match_operator",
        type: "select",
        required: false,
        options: {
          maxSelect: 1,
          values: ["none", "equals", "contains"],
        },
      },
      {
        name: "filter_text_match_value",
        type: "text",
        max: 200,
        required: false,
      },
    ],
    indexes: [
      "CREATE INDEX idx_telegram_webhooks_session ON telegram_webhooks (session)",
    ],
  })
  app.save(webhooks)

  // 3) Migra webhooks legados: pra cada telegram_sessions com webhook_url
  //    não-vazio, cria 1 telegram_webhooks correspondente.
  const legacyRecords = app.findAllRecords("telegram_sessions")
  for (const r of legacyRecords) {
    const url = r.getString("webhook_url")
    if (!url) continue
    const wh = new Record(webhooks, {
      session: r.id,
      name: "Webhook legado",
      url: url,
      enabled: true,
      filter_direction: "all",
      filter_chat_type: "all",
      filter_text_match_operator: "none",
      filter_text_match_value: "",
    })
    app.save(wh)
  }
}, (app) => {
  // down: remove collection webhooks (perde os webhooks migrados — documentado)
  try {
    const webhooks = app.findCollectionByNameOrId("telegram_webhooks")
    app.delete(webhooks)
  } catch (_) {
    // collection pode não existir se migration rodou parcial
  }
  // Remove o campo `name` de telegram_sessions
  try {
    const sessions = app.findCollectionByNameOrId("telegram_sessions")
    sessions.fields.removeByName("name")
    app.save(sessions)
  } catch (_) {
    // collection pode não existir
  }
})
