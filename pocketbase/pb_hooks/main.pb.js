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
// problemas de propagação de token. Resolve o bug do `_get_active_webhooks`
// que não conseguia listar sem user context.
// =============================================================================

/**
 * Verifica se uma mensagem passa pelos filtros do webhook.
 * Retorna true se o webhook deve receber a mensagem.
 */
function matchesFilters(msg, wh) {
  // direction: all / incoming / outgoing
  const dir = wh.getString("filter_direction") || "all"
  if (dir !== "all" && dir !== msg.getString("direction")) return false

  // chat_type: all / private / group / supergroup / channel / unknown
  const ct = wh.getString("filter_chat_type") || "all"
  if (ct !== "all" && ct !== msg.getString("chat_type")) return false

  // text_match: none / equals / contains
  const op = wh.getString("filter_text_match_operator") || "none"
  if (op === "none") return true
  const val = (wh.getString("filter_text_match_value") || "").trim()
  if (!val) return true // operator set but empty value = no filter
  const text = (msg.getString("text") || "").toLowerCase()
  const needle = val.toLowerCase()
  if (op === "equals") return text === needle
  if (op === "contains") return text.indexOf(needle) !== -1
  return true
}

/**
 * Monta o payload JSON enviado pro webhook receptor (n8n, etc).
 */
function buildPayload(msg, session, wh) {
  return {
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
  }
}

onRecordAfterCreateSuccess((e) => {
  // O record JÁ foi salvo quando esse hook dispara (é "AfterSuccess").
  // Fazemos o trabalho de distribuir pros webhooks e atualizar o record
  // com o resultado. Se o save inicial falhar, esse hook não é chamado.

  const msg = e.record
  const sessionRel = msg.getString("session") // PB id do record da sessão

  // 1) Acha a sessão (pra ter phone, name, etc no payload)
  let session
  try {
    session = $app.findRecordById("telegram_sessions", sessionRel)
  } catch (err) {
    console.log("telegram_messages hook: sessão não encontrada:", sessionRel, err)
    return
  }

  // 2) Lista webhooks ativos da sessão
  let webhooks
  try {
    webhooks = $app.findAllRecords("telegram_webhooks", {
      filter: $app.filter("session={:sid} && enabled=true", { sid: sessionRel }),
    })
  } catch (err) {
    console.log("telegram_messages hook: erro listando webhooks:", err)
    return
  }

  if (!webhooks || webhooks.length === 0) {
    console.log("telegram_messages hook: nenhum webhook ativo pra sessão", sessionRel)
    return
  }

  // 3) Distribui pros webhooks que passam no filtro
  let delivered = 0
  let firstError = null
  const body = JSON.stringify(buildPayload(msg, session, webhooks[0]))
  // buildPayload é o mesmo shape pra todos os webhooks, mas os
  // headers/dados por webhook vêm do record individual. Refaz o body
  // dentro do loop pra incluir webhook_id/webhook_name corretos.
  for (const wh of webhooks) {
    if (!matchesFilters(msg, wh)) continue

    try {
      $http.send({
        url: wh.getString("url"),
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload(msg, session, wh)),
        timeout: 10,
      })
      delivered++
    } catch (err) {
      if (!firstError) firstError = String(err).substring(0, 500)
      console.log("telegram_messages hook: webhook falhou", wh.id, err)
    }
  }

  // 4) Atualizar delivered_count/delivery_error no record.
  // NOTA: o $app.dao().saveRecord aqui roda DENTRO da transação do
  // AfterSuccess hook, então é descartado no commit (o INSERT inicial
  // é o que persiste). Por isso só logamos o resultado em vez de
  // persistir. O webhook forwarding funciona mesmo sem essa métrica.
  if (firstError) {
    console.log(
      "telegram_messages hook: msg=" + msg.id +
      " session=" + sessionRel +
      " webhooks=" + webhooks.length +
      " delivered=" + delivered +
      " firstError=" + firstError,
    )
  } else {
    console.log(
      "telegram_messages hook: msg=" + msg.id +
      " session=" + sessionRel +
      " webhooks=" + webhooks.length +
      " delivered=" + delivered,
    )
  }

  console.log(
    "telegram_messages hook: msg=" + msg.id +
    " session=" + sessionRel +
    " webhooks=" + webhooks.length +
    " delivered=" + delivered,
  )
}, "telegram_messages")
