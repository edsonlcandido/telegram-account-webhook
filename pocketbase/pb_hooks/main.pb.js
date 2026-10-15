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
// GOTCHA: o PB 0.40+ JSVM não enxerga funções helper top-level dentro
// de handlers. `matchesFilters` e `buildPayload` PRECISAM estar inline
// (declaradas dentro do corpo do hook), senão dá "ReferenceError: X is
// not defined" no runtime. A skill pocketbase-jsvm tem mais detalhes.
// =============================================================================

onRecordAfterCreateSuccess((e) => {
  // O record JÁ foi salvo quando esse hook dispara (é "AfterSuccess").
  // Fazemos o trabalho de distribuir pros webhooks. Se o save inicial
  // falhar, esse hook não é chamado.

  console.log("[hook] X START record.id=" + e.record.id)
  const msg = e.record
  const sessionRel = msg.getString("session")
  console.log("[hook] X sessionRel=" + sessionRel)

  // 1) Acha a sessão
  let session
  try {
    session = $app.findRecordById("telegram_sessions", sessionRel)
    console.log("[hook] X session found")
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
    console.log("[hook] X webhooks found count=" + (webhooks ? webhooks.length : -1))
  } catch (err) {
    console.log("telegram_messages hook: erro listando webhooks:", String(err))
    return
  }

  if (!webhooks || webhooks.length === 0) {
    console.log("telegram_messages hook: nenhum webhook ativo pra sessão", sessionRel)
    return
  }

  // 3) Distribui pros webhooks que passam no filtro
  let delivered = 0
  let firstError = null
  for (let i = 0; i < webhooks.length; i++) {
    const wh = webhooks[i]
    if (!wh) continue

    // === INLINE: matchesFilters (não pode ser helper top-level) ===
    let pass = true
    try {
      const dir = wh.getString("filter_direction") || "all"
      console.log("[hook] X dir=" + dir)
      if (dir !== "all" && dir !== msg.getString("direction")) pass = false

      if (pass) {
        const ct = wh.getString("filter_chat_type") || "all"
        console.log("[hook] X ct=" + ct)
        if (ct !== "all" && ct !== msg.getString("chat_type")) pass = false
      }

      if (pass) {
        const op = wh.getString("filter_text_match_operator") || "none"
        console.log("[hook] X op=" + op)
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
      console.log("[hook] X pass=" + pass)
    } catch (fErr) {
      console.log("telegram_messages hook: filter error:", String(fErr))
      continue
    }
    if (!pass) continue

    console.log("[hook] X calling $http.send to " + wh.getString("url"))

    // === INLINE: buildPayload (não pode ser helper top-level) ===
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

    // 4) POST pro webhook receptor
    // PB 0.40+ JSVM: $http.send é SÍNCRONO. Se o container não conseguir
    // resolver DNS ou conectar, trava até o timeout. O timeout: 10 (s)
    // é pra leitura/escrita do socket, NÃO pra resolução DNS.
    let resp
    try {
      resp = $http.send({
        url: wh.getString("url"),
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
        timeout: 10,
      })
      console.log("[hook] X send returned status=" + resp.status)
      delivered++
      console.log(
        "telegram_messages hook: delivered msg=" + msg.id +
        " webhook=" + wh.id +
        " status=" + resp.status,
      )
    } catch (err) {
      if (!firstError) firstError = String(err).substring(0, 500)
      console.log(
        "telegram_messages hook: webhook FAILED msg=" + msg.id +
        " webhook=" + wh.id +
        " err=" + String(err).substring(0, 200),
      )
    }
  }

  // 5) Log final. NÃO tentamos persistir delivered_count/delivery_error
  // porque $app.dao().saveRecord no AfterSuccess é descartado pela transação.
  console.log(
    "telegram_messages hook: msg=" + msg.id +
    " session=" + sessionRel +
    " webhooks=" + webhooks.length +
    " delivered=" + delivered +
    (firstError ? " firstError=" + firstError : ""),
  )
}, "telegram_messages")
