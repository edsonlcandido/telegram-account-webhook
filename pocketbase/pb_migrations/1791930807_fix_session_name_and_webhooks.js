/// <reference path="../pb_data/types.d.ts" />

// FIX: migration 1791929716 falhou no deploy por erro de sintaxe nos fields
// (collectionId/values/options dentro de `options: {}` em vez de no field
// direto). Esta migration é defensiva e idempotente: cobre o caso da 1791929716
// ter falhado antes de completar, garantindo que:
//   1) `name` existe em `telegram_sessions`;
//   2) `telegram_webhooks` collection existe com todos os campos;
//   3) Webhooks legados (de `telegram_sessions.webhook_url` não-vazio) são
//      migrados pra `telegram_webhooks`.
//
// Regra do projeto: NUNCA editar uma migration depois de commitada.
// Se precisar mudar o schema, criar uma nova migration como esta.

migrate((app) => {
  // 1) Adiciona `name` em telegram_sessions (se não existir)
  const sessions = app.findCollectionByNameOrId("telegram_sessions")
  if (!sessions.fields.getByName("name")) {
    sessions.fields.add(
      new Field({ name: "name", type: "text", max: 60, required: false }),
    )
    app.save(sessions)
  }

  // 2) Cria telegram_webhooks (se não existir)
  let webhooks
  try {
    webhooks = app.findCollectionByNameOrId("telegram_webhooks")
  } catch (_) {
    webhooks = null
  }
  if (!webhooks) {
    webhooks = new Collection({
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
          collectionId: sessions.id,
          cascadeDelete: true,
          minSelect: 1,
          maxSelect: 1,
        },
        { name: "name", type: "text", max: 60, required: false },
        { name: "url", type: "url", required: true },
        { name: "enabled", type: "bool", required: false },
        {
          name: "filter_direction",
          type: "select",
          required: false,
          values: ["all", "incoming", "outgoing"],
          maxSelect: 1,
        },
        {
          name: "filter_chat_type",
          type: "select",
          required: false,
          values: ["all", "private", "group", "supergroup", "channel"],
          maxSelect: 1,
        },
        {
          name: "filter_text_match_operator",
          type: "select",
          required: false,
          values: ["none", "equals", "contains"],
          maxSelect: 1,
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
  }

  // 3) Migra webhooks legados (idempotente: pula se já existe)
  const legacyRecords = app.findAllRecords("telegram_sessions")
  for (const r of legacyRecords) {
    const url = r.getString("webhook_url")
    if (!url) continue
    const existing = app.findAllRecords("telegram_webhooks", {
      filter: `session = "${r.id}"`,
    })
    if (existing.length > 0) continue
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
  // down
  try {
    const webhooks = app.findCollectionByNameOrId("telegram_webhooks")
    app.delete(webhooks)
  } catch (_) {}
  try {
    const sessions = app.findCollectionByNameOrId("telegram_sessions")
    if (sessions.fields.getByName("name")) {
      sessions.fields.removeByName("name")
      app.save(sessions)
    }
  } catch (_) {}
})
