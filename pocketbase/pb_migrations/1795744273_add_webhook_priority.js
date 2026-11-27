/// <reference path="../pb_data/types.d.ts" />

migrate((app) => {
  const hooks = app.findCollectionByNameOrId("telegram_webhooks");
  let changed = false;

  if (!hooks.fields.getByName("priority")) {
    hooks.fields.add(
      new Field({
        name: "priority",
        type: "number",
        required: false,
        min: 0,
        max: 2147483647,
      })
    );
    changed = true;
  }

  if (!hooks.indexes.some((index) => index.includes("idx_telegram_webhooks_priority"))) {
    hooks.indexes.push(
      "CREATE INDEX IF NOT EXISTS idx_telegram_webhooks_priority ON telegram_webhooks (session, priority)"
    );
    changed = true;
  }

  if (changed) {
    app.save(hooks);
  }

  for (const webhook of app.findAllRecords("telegram_webhooks")) {
    if (webhook.get("priority") == null) {
      webhook.set("priority", 100);
      app.save(webhook);
    }
  }
}, (app) => {
  try {
    const hooks = app.findCollectionByNameOrId("telegram_webhooks");
    if (hooks.fields.getByName("priority")) {
      hooks.fields.removeByName("priority");
      app.save(hooks);
    }
  } catch (_) {}
});
