---
name: domain-email-hooks
description: Como enviar emails transacionais no template — password reset, verificação, notificações de domínio, newsletters via hooks PocketBase. Cobre templates HTML, SMTP config, fila de envio, captura de bounces. Use quando o usuário quiser enviar email de boas-vindas, recuperar senha, notificar usuário sobre evento, ou disparar emails em hooks.
---

# Domínio — Emails transacionais via hooks PB

PocketBase tem **Mailer** nativo (`$app.newMailClient()`). Pra casos simples, dá pra enviar direto via SMTP. Pra produção, use um provider (Resend, SendGrid, Postmark) através de `$http`.

## Setup SMTP (dev/teste)

`pocketbase/pb_data/.env` (PB lê da env do processo):

```bash
# Linux/Mac (exportar antes de rodar o PB)
export PB_SMTP_ENABLED=true
export PB_SMTP_HOST=smtp.mailtrap.io
export PB_SMTP_PORT=587
export PB_SMTP_USERNAME=xxx
export PB_SMTP_PASSWORD=xxx
export PB_SMTP_FROM_NAME="Meu App"
export PB_SMTP_FROM_ADDRESS=noreply@meuapp.com
```

Ou via admin → Settings → Mail settings.

> Em prod, **recomendo**: Resend (mais simples) ou Postmark. Ver abaixo.

## Envio simples via hook

```js
// pb_hooks/welcome.pb.js
/// <reference path="../pb_data/types.d.ts" />

onRecordAfterCreateRequest((e) => {
  if (e.collection.name !== 'users') return

  const message = new MailerMessage({
    from:    { address: $app.settings().meta.senderAddress, name: $app.settings().meta.senderName },
    to:      [{ address: e.record.email }],
    subject: 'Bem-vindo ao MeuApp! 🎉',
    html: `
      <h1>Oi, ${e.record.getString('name') || 'amigo'}!</h1>
      <p>Sua conta foi criada. Acesse: <a href="${$app.settings().meta.publicUrl}/app/login">${$app.settings().meta.publicUrl}/app/login</a></p>
    `,
    // opcional:
    // attachments: [{ filename: 'welcome.pdf', content: pdfBuffer }],
  })
  $app.newMailClient().send(message)
}, $app)
```

## Template HTML reusável

### `pocketbase/pb_hooks/templates/email.html.js`

```js
function render({ title, body, ctaText, ctaUrl }) {
  return `
<!doctype html>
<html><head><meta charset="utf-8"><title>${title}</title></head>
<body style="margin:0;font-family:'Inter',Arial,sans-serif;background:#f3f4f6">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:40px 20px">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,.05)">
        <tr><td style="background:linear-gradient(135deg,#3b82f6,#8b5cf6);padding:32px;text-align:center">
          <h1 style="margin:0;color:#fff;font-size:24px">${title}</h1>
        </td></tr>
        <tr><td style="padding:32px;color:#374151;font-size:16px;line-height:1.6">${body}</td></tr>
        ${ctaUrl ? `<tr><td align="center" style="padding:0 32px 32px">
          <a href="${ctaUrl}" style="display:inline-block;background:#3b82f6;color:#fff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:600">${ctaText}</a>
        </td></tr>` : ''}
        <tr><td style="background:#f9fafb;padding:20px;text-align:center;color:#9ca3af;font-size:12px">
          © ${new Date().getFullYear()} MeuApp · <a href="${$app.settings().meta.publicUrl}/app/settings" style="color:#9ca3af">descadastrar</a>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>`
}

module.exports = { render }
```

### Uso

```js
const tpl = require('./templates/email.html.js')

onRecordAfterCreateRequest((e) => {
  if (e.collection.name !== 'leads') return

  const html = tpl.render({
    title: 'Novo lead atribuído',
    body: `<p>Você recebeu o lead <strong>${e.record.getString('name')}</strong> da empresa ${e.record.getString('company')}.</p>`,
    ctaText: 'Abrir lead',
    ctaUrl: `${$app.settings().meta.publicUrl}/app/leads/${e.record.id}`,
  })

  const ownerId = e.record.getString('owner')
  const owner = $app.dao().findRecordById('_pb_users_auth_', ownerId)

  $app.newMailClient().send(new MailerMessage({
    from: { address: $app.settings().meta.senderAddress, name: 'CRM' },
    to:   [{ address: owner.email() }],
    subject: '🎯 Novo lead: ' + e.record.getString('name'),
    html,
  }))
}, $app)
```

## Password reset

PocketBase já tem fluxo nativo. Mas se quiser customizar o template:

```js
// pb_hooks/auth.pb.js
onRecordEnrich((e) => {
  if (e.request.path.startsWith('/api/collections/users/') && e.request.method === 'POST') {
    // não customizar — apenas exemplo
  }
}, $app)

// Customizar email de reset (PocketBase chama MailerMessage em verifyEmail / passwordReset)
onMailerSend((e) => {
  if (e.message.template?.name === 'passwordReset') {
    e.message.html = `
      <h1>Redefinir sua senha</h1>
      <p>Use o token abaixo ou clique no link:</p>
      <p><code>${e.message.template.data.token}</code></p>
      <p><a href="${$app.settings().meta.publicUrl}/app/reset-password?token=${e.message.template.data.token}">Redefinir senha</a></p>
    `
  }
}, $app)
```

## Provider externo (Resend)

```js
// pb_hooks/resend.pb.js
/// <reference path="../pb_data/types.d.ts" />

async function sendViaResend({ to, subject, html }) {
  const res = await $http.send({
    url: 'https://api.resend.com/emails',
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + $os.getenv('RESEND_API_KEY'),
      'Content-Type':  'application/json',
    },
    body: JSON.stringify({
      from: 'MeuApp <noreply@meuapp.com>',
      to: Array.isArray(to) ? to : [to],
      subject, html,
    }),
  })
  return JSON.parse(res.raw)
}

// re-exportar pro use nas outras hooks:
$app.runInTransaction(() => {}) // no-op só pra registrar
module.exports = { sendViaResend }
```

Helper pra chamar em outros hooks:

```js
const { sendViaResend } = require('./resend.pb.js')

onRecordAfterCreateRequest((e) => {
  if (e.collection.name !== 'orders') return
  sendViaResend({
    to: e.record.getString('customer_email'),
    subject: 'Pedido #' + e.record.id + ' confirmado',
    html: tpl.render({ title: 'Pedido confirmado', body: '...' }),
  }).catch(err => console.error('email fail:', err))
}, $app)
```

## Fila assíncrona (pra não bloquear hook)

Em volume alto, hooks demoram. Use collection `email_queue`:

```js
// pb_migrations/1700000000_email_queue.js
migrate((db) => {
  Dao(db).saveCollection(new Collection({
    name: 'email_queue',
    type: 'base',
    schema: [
      { name: 'to', type: 'email', required: true },
      { name: 'subject', type: 'text', required: true },
      { name: 'html', type: 'text', required: true },
      { name: 'status', type: 'select', required: true,
        options: { maxSelect: 1, values: ['pending', 'sent', 'failed', 'bounced'] } },
      { name: 'attempts', type: 'number' },
      { name: 'last_error', type: 'text' },
      { name: 'sent_at', type: 'date' },
      { name: 'metadata', type: 'json' },
    ],
    indexes: ['CREATE INDEX idx_eq_status ON email_queue (status, created)'],
  }))
})
```

Hook enfileira:

```js
onRecordAfterCreateRequest((e) => {
  if (e.collection.name !== 'leads') return
  $app.dao().saveRecord(new Record($app.findCollectionByNameOrId('email_queue'), {
    to: 'sales@meuapp.com',
    subject: 'Novo lead',
    html: '...',
    status: 'pending',
    attempts: 0,
  }))
}, $app)
```

Worker processa (cron ou hook onBootstrap):

```js
// cron job — chamado a cada 1 min
$app.cronAdd('email-drain', '*/1 * * * *', () => {
  const pending = $app.dao().findRecordsByFilter('email_queue',
    `status = "pending" && attempts < 5`, '', 10, 0)
  for (const job of pending) {
    try {
      $app.newMailClient().send(new MailerMessage({
        from: { address: $app.settings().meta.senderAddress, name: 'CRM' },
        to: [{ address: job.getString('to') }],
        subject: job.getString('subject'),
        html: job.getString('html'),
      }))
      job.set('status', 'sent'); job.set('sent_at', new Date().toISOString())
    } catch (err) {
      job.set('attempts', (job.getNumber('attempts') ?? 0) + 1)
      job.set('last_error', err.message)
      if ((job.getNumber('attempts') ?? 0) >= 5) job.set('status', 'failed')
    }
    $app.dao().saveRecord(job)
  }
})
```

## Bounces & descadastro

`onMailerSend` permite checar:

```js
// collection email_suppressions
{ name: 'email', type: 'email' }
```

```js
onMailerSend((e) => {
  const to = e.message.to?.[0]?.address
  if (!to) return
  try {
    if ($app.dao().findFirstRecordByData('email_suppressions', 'email', to)) {
      throw new BadRequestError('Endereço suprimido')
    }
  } catch (err) {
    if (!(err instanceof RecordNotFoundError)) throw err
  }
}, $app)

// Webhook do provider pra registrar bounce:
routerAdd('POST', '/api/email/bounce', (c) => {
  const body = JSON.parse(c.request.body())
  $app.dao().saveRecord(new Record($app.findCollectionByNameOrId('email_suppressions'), {
    email: body.email,
  }))
  return c.json(200, { ok: true })
})
```

## Newsletter / marketing

Não use o mailer transacional pra marketing. Mas pra **notificações digest** (ex: "5 novos leads essa semana"):

```js
// cron diário 9h da manhã BRT
$app.cronAdd('digest', '0 12 * * *', () => {
  const users = $app.dao().findRecordsByFilter('_pb_users_auth_`, '', '', 1000, 0)
  for (const u of users) {
    const leads = $app.dao().findRecordsByFilter('leads',
      `owner = "${u.id}" && created > "now-7d"`, '', 100, 0)
    if (leads.length === 0) continue

    $app.dao().saveRecord(new Record($app.findCollectionByNameOrId('email_queue'), {
      to: u.email(),
      subject: `📊 Seu resumo semanal — ${leads.length} novos leads`,
      html: tpl.render({
        title: 'Seu resumo da semana',
        body: leads.map(l => `<p>• ${l.getString('name')} — ${l.getString('company')}</p>`).join(''),
        ctaText: 'Ver pipeline', ctaUrl: `${$app.settings().meta.publicUrl}/app/leads`,
      }),
      status: 'pending', attempts: 0,
    }))
  }
})
```

## Front — settings de notificação

```vue
<!-- app/settings/notifications.vue -->
<script setup lang="ts">
const prefs = ref({
  email_new_lead: true,
  email_weekly_digest: true,
  email_mentions: true,
})

async function save() {
  await pb.collection('notification_prefs').update(prefs.value.id, prefs.value)
}
</script>
```

> Persistir em collection `notification_prefs` (1-1 com user).

## Checklist

- [ ] Provider configurado (SMTP em dev, Resend/Postmark em prod)
- [ ] SPF/DKIM/DMARC no domínio (não é opcional — vai pro spam)
- [ ] `from` configurado em Settings → Mail
- [ ] Template HTML responsivo (mobile-first)
- [ ] Footer com link de descadastro
- [ ] Queue + retry pra envios não-críticos
- [ ] Webhook de bounce configurado
- [ ] Rate-limit (max ~50 emails/seg do provider)