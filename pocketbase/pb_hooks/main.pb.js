/// <reference path="../pb_data/types.d.ts" />

// Landing page na raiz (sem fallback SPA pq a landing é estática)
routerAdd("GET", "/{path...}", $apis.static("pb_public", false))

// Web app em /app/* com fallback SPA (index.html) pra sub-rotas do Vue Router
// tipo /app/dashboard. Sem isso, qualquer sub-rota retorna 404.
routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", true))

// =============================================================================
// Webhook forwarding: quando o FastAPI insere em `telegram_messages`,
// este hook distribui pros webhooks ativos da sessão, aplicando os filtros.
// Tudo roda DENTRO do PB — sem auth, sem HTTP hop extra pro FastAPI, sem
// problemas de propagação de token.
//
// GOTCHA PB 0.40+ JSVM (relembrando pq eu já quebrei isso 3x):
// - Funções helper top-level NÃO são visíveis dentro de handlers. Tudo
//   precisa estar inline (declarado dentro do corpo do hook) senão dá
//   "ReferenceError: X is not defined" no runtime.
// - $http.send retorna `res.statusCode` (NÃO `res.status` — esse campo
//   não existe, é silenciosamente undefined).
// - Hooks *AfterSuccess rodam DEPOIS do save. Se o hook lançar, o record
//   fica persistido mas a response pro cliente vira erro. NÃO chamar
//   e.next() (no-op ou erro em AfterSuccess).
// - $http.send bloqueia (síncrono). Timeout cobre socket I/O; DNS ruim
//   pode adicionar overhead antes.
// A skill `.agents/skills/pocketbase-jsvm/SKILL.md` tem mais detalhes.
// =============================================================================

onRecordAfterCreateSuccess((e) => {
  // O record JÁ foi salvo quando esse hook dispara.

  const msg = e.record
  const sessionRel = msg.getString("session")

  // 1) Acha a sessão
  let session
  try {
    session = $app.findRecordById("telegram_sessions", sessionRel)
  } catch (err) {
    console.log("telegram_messages hook: sessão não encontrada:", String(err))
    return
  }

  // 2) Lista webhooks ativos da sessão
  let webhooks
  try {
    webhooks = $app.findRecordsByFilter(
      "telegram_webhooks",
      "session={:sid} && enabled=true",
      "",
      500,
      0,
      { sid: sessionRel },
    )
  } catch (err) {
    console.log("telegram_messages hook: erro listando webhooks:", String(err))
    return
  }

  if (!webhooks || webhooks.length === 0) {
    return
  }

  // 3) Distribui pros webhooks que passam no filtro
  let delivered = 0
  let firstError = null
  for (let i = 0; i < webhooks.length; i++) {
    const wh = webhooks[i]
    if (!wh) continue

    // matchesFilters (inline — não pode ser helper top-level)
    let pass = true
    try {
      const dir = wh.getString("filter_direction") || "all"
      if (dir !== "all" && dir !== msg.getString("direction")) pass = false

      if (pass) {
        const ct = wh.getString("filter_chat_type") || "all"
        if (ct !== "all" && ct !== msg.getString("chat_type")) pass = false
      }

      if (pass) {
        const op = wh.getString("filter_text_match_operator") || "none"
        if (op !== "none") {
          const val = (wh.getString("filter_text_match_value") || "").trim()
          if (val) {
            const text = (msg.getString("text") || "").toLowerCase()
            const needle = val.toLowerCase()
            if (op === "equals") pass = (text === needle)
            else if (op === "contains") pass = (text.indexOf(needle) !== -1)
          }
        }
      }
    } catch (fErr) {
      console.log("telegram_messages hook: filter error:", String(fErr))
      continue
    }
    if (!pass) continue

    // URL é usada COMO ESTÁ — não fazemos rewrite. Se o usuário
    // configurou uma URL pública, é essa URL que vai ser chamada.
    // A investigação de por que dá certo esse container trava em
    // certos IPs (rota/firewall/DNS) tá em aberto — não é resolvida
    // com rewrite. Se for o caso, mover o forwarding pra outro
    // serviço que tenha egress OK (FastAPI/Telethon service).
    const targetUrl = wh.getString("url")

    // buildPayload (inline — não pode ser helper top-level)
    // TODO(schema): se o seu workflow n8n espera um shape específico tipo
    // {objeto: {prop, nume, sub: {name}}}, ajustar este objeto. O schema
    // atual funciona como genérico — webhook nodes n8n costumam aceitar
    // JSON arbitrário se não tiver validação estrita de schema.
    const payload = JSON.stringify({
      event: "telegram.message",
      webhook_id: wh.id,
      webhook_name: wh.getString("name"),
      session: {
        pb_id: session.id,
        session_id: session.getString("session_id"),
        phone: session.getString("phone"),
        name: session.getString("name") || "",
      },
      message: {
        id: msg.id,
        chat_id: msg.getNumber("chat_id"),
        chat_type: msg.getString("chat_type"),
        chat_title: msg.getString("chat_title") || "",
        direction: msg.getString("direction"),
        sender_id: msg.getNumber("sender_id"),
        sender_name: msg.getString("sender_name") || "",
        text: msg.getString("text") || "",
        timestamp: msg.getString("created"),
      },
    })

    // POST pro webhook. $http.send é síncrono, timeout em segundos, throws
    // em erro. Se a URL bater certinho (Traefik → seu n8n), retorna em
    // <500ms. Se timeout/dns/route falhar, throws em até 10s.
    try {
      const resp = $http.send({
        url: targetUrl,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        timeout: 10,
      })
      delivered++
      console.log(
        "telegram_messages hook: delivered msg=" + msg.id +
        " webhook=" + wh.id +
        " url=" + targetUrl +
        " status=" + resp.statusCode,
      )
    } catch (err) {
      if (!firstError) firstError = String(err).substring(0, 500)
      console.log(
        "telegram_messages hook: webhook FAILED msg=" + msg.id +
        " webhook=" + wh.id +
        " url=" + targetUrl +
        " err=" + String(err).substring(0, 200),
      )
    }
  }

  // 4) Log final. NÃO tentamos persistir delivered_count/delivery_error
  // porque $app.dao().saveRecord no AfterSuccess é descartado pela
  // transação (PB 0.40+).
  console.log(
    "telegram_messages hook: msg=" + msg.id +
    " session=" + sessionRel +
    " webhooks=" + webhooks.length +
    " delivered=" + delivered +
    (firstError ? " firstError=" + firstError : ""),
  )
}, "telegram_messages")