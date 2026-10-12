/// <reference path="../pb_data/types.d.ts" />

migrate((app) => {
  const collection = new Collection({
    name: "telegram_sessions",
    type: "base",
    listRule: "@request.auth.id != ''",
    viewRule: "@request.auth.id != ''",
    createRule: "@request.auth.id != ''",
    updateRule: "@request.auth.id != ''",
    deleteRule: "@request.auth.id != ''",
    fields: [
      {
        name: "phone",
        type: "text",
        required: true,
        min: 10,
        max: 20,
      },
      {
        name: "session_id",
        type: "text",
        required: true,
        min: 1,
        max: 255,
      },
      {
        name: "phone_code_hash",
        type: "text",
        max: 255,
      },
      {
        name: "webhook_url",
        type: "url",
        options: {
          exceptDomains: null,
          onlyDomains: null,
          preview: true,
        },
      },
      {
        name: "active",
        type: "bool",
      },
      {
        name: "api_id",
        type: "number",
        options: {
          noDecimals: true,
        },
      },
      {
        name: "api_hash",
        type: "text",
        max: 255,
      },
    ],
    indexes: [
      "CREATE UNIQUE INDEX idx_telegram_sessions_session_id ON telegram_sessions (session_id)",
      "CREATE UNIQUE INDEX idx_telegram_sessions_phone ON telegram_sessions (phone)",
    ],
  });

  app.save(collection);
}, (app) => {
  const collection = app.findCollectionByNameOrId("telegram_sessions");
  app.delete(collection);
});
