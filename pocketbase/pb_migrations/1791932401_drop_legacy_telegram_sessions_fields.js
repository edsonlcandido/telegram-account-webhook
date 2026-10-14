/// <reference path="../pb_data/types.d.ts" />

// FIX: schema legado de `telegram_sessions` depois que a abordagem mudou.
//
// Antes (model antigo, single-webhook por sessão):
//   - `webhook_url` (url)             → substituído por relation com `telegram_webhooks`
//                                       (a migration 1791930807 já migrou os dados
//                                        pra "Webhook legado").
//   - `phone_code_hash` (text)        → guardamos isso em `active_clients[f"{sid}_hash"]`
//                                       (in-memory), PB nunca foi consultado.
//   - `active` (bool)                 → write-only: lido de `active_clients` em
//                                       memória, nunca da collection.
//   - `api_id` (number)               → sempre igual ao env var `TG_API_ID` do
//                                       container Telegram API. Nunca lido.
//   - `api_hash` (text)               → mesmo motivo. Service é single-app.
//
// Esta migration remove as 5 colunas. Idempotente (check-then-drop).
//
// Regra: NUNCA editar uma migration depois de commitada.
// Se precisar ajustar, criar uma nova com timestamp BRT-as-UTC maior.

migrate((app) => {
  const sessions = app.findCollectionByNameOrId("telegram_sessions")

  const dead = ["webhook_url", "phone_code_hash", "active", "api_id", "api_hash"]
  let changed = false
  for (const name of dead) {
    if (sessions.fields.getByName(name)) {
      sessions.fields.removeByName(name)
      changed = true
    }
  }
  if (changed) app.save(sessions)
}, (app) => {
  // down: recria as colunas removidas (simétrico, opcional).
  const sessions = app.findCollectionByNameOrId("telegram_sessions")

  if (!sessions.fields.getByName("webhook_url")) {
    sessions.fields.add(
      new Field({
        name: "webhook_url",
        type: "url",
        required: false,
        options: { exceptDomains: null, onlyDomains: null, preview: true },
      }),
    )
  }
  if (!sessions.fields.getByName("phone_code_hash")) {
    sessions.fields.add(
      new Field({ name: "phone_code_hash", type: "text", max: 255, required: false }),
    )
  }
  if (!sessions.fields.getByName("active")) {
    sessions.fields.add(new Field({ name: "active", type: "bool", required: false }))
  }
  if (!sessions.fields.getByName("api_id")) {
    sessions.fields.add(
      new Field({
        name: "api_id",
        type: "number",
        required: false,
        options: { noDecimals: true },
      }),
    )
  }
  if (!sessions.fields.getByName("api_hash")) {
    sessions.fields.add(
      new Field({ name: "api_hash", type: "text", max: 255, required: false }),
    )
  }
  app.save(sessions)
})