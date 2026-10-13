/// <reference path="../pb_data/types.d.ts" />

// =============================================================================
// Proxy reverso: encaminha /api-telegram/* do frontend (mesma origem) para o
// servico Telegram API (FastAPI).
// =============================================================================
// ATENCAO: cada handler e self-contained. Nao declaramos funcoes top-level
// compartilhadas entre routerAdd, porque o JSVM do PB executa cada callback em
// um VM context separado do pool - referencias a `let`/`const`/`function` do
// top-level dao `ReferenceError: not defined` em producao (embora funcionem
// em testes single-thread). Por isso cada handler inline o seu `proxyToFastApi`.
// =============================================================================

const UPSTREAM_BASE = $os.getenv("TELEGRAM_API_URL") || "https://eh-tudo-telegram-account-webhook-telegram.aiyfgd.easypanel.host";

routerAdd("POST", "/api-telegram/send-code", (e) => {
    const url = UPSTREAM_BASE.replace(/\/+$/, "") + "/api/send-code";
    const reqInfo = e.requestInfo();
    const headers = { "Content-Type": "application/json" };
    if (reqInfo.headers && reqInfo.headers.authorization) {
        headers["Authorization"] = reqInfo.headers.authorization;
    }
    const body = reqInfo.body && (reqInfo.body.length || 0) > 0 ? toString(reqInfo.body) : null;
    let resp;
    try {
        resp = $http.send({ url: url, method: "POST", body: body, header: headers, timeout: 60 });
    } catch (err) {
        throw new Error("Servico Telegram API indisponivel");
    }
    let data;
    try { data = resp.json; } catch (_) { data = toString(resp.body); }
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("POST", "/api-telegram/verify-code", (e) => {
    const url = UPSTREAM_BASE.replace(/\/+$/, "") + "/api/verify-code";
    const reqInfo = e.requestInfo();
    const headers = { "Content-Type": "application/json" };
    if (reqInfo.headers && reqInfo.headers.authorization) {
        headers["Authorization"] = reqInfo.headers.authorization;
    }
    const body = reqInfo.body && (reqInfo.body.length || 0) > 0 ? toString(reqInfo.body) : null;
    let resp;
    try {
        resp = $http.send({ url: url, method: "POST", body: body, header: headers, timeout: 60 });
    } catch (err) {
        throw new Error("Servico Telegram API indisponivel");
    }
    let data;
    try { data = resp.json; } catch (_) { data = toString(resp.body); }
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("POST", "/api-telegram/set-webhook", (e) => {
    const url = UPSTREAM_BASE.replace(/\/+$/, "") + "/api/set-webhook";
    const reqInfo = e.requestInfo();
    const headers = { "Content-Type": "application/json" };
    if (reqInfo.headers && reqInfo.headers.authorization) {
        headers["Authorization"] = reqInfo.headers.authorization;
    }
    const body = reqInfo.body && (reqInfo.body.length || 0) > 0 ? toString(reqInfo.body) : null;
    let resp;
    try {
        resp = $http.send({ url: url, method: "POST", body: body, header: headers, timeout: 60 });
    } catch (err) {
        throw new Error("Servico Telegram API indisponivel");
    }
    let data;
    try { data = resp.json; } catch (_) { data = toString(resp.body); }
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("GET", "/api-telegram/sessions", (e) => {
    const url = UPSTREAM_BASE.replace(/\/+$/, "") + "/api/sessions";
    const reqInfo = e.requestInfo();
    const headers = { "Content-Type": "application/json" };
    if (reqInfo.headers && reqInfo.headers.authorization) {
        headers["Authorization"] = reqInfo.headers.authorization;
    }
    let resp;
    try {
        resp = $http.send({ url: url, method: "GET", header: headers, timeout: 60 });
    } catch (err) {
        throw new Error("Servico Telegram API indisponivel");
    }
    let data;
    try { data = resp.json; } catch (_) { data = toString(resp.body); }
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("DELETE", "/api-telegram/session/{sessionId}", (e) => {
    const parts = e.requestInfo().path.split("/").filter(Boolean);
    const sessionId = parts[parts.length - 1] || "";
    const url = UPSTREAM_BASE.replace(/\/+$/, "") + "/api/session/" + sessionId;
    const reqInfo = e.requestInfo();
    const headers = { "Content-Type": "application/json" };
    if (reqInfo.headers && reqInfo.headers.authorization) {
        headers["Authorization"] = reqInfo.headers.authorization;
    }
    let resp;
    try {
        resp = $http.send({ url: url, method: "DELETE", header: headers, timeout: 60 });
    } catch (err) {
        throw new Error("Servico Telegram API indisponivel");
    }
    let data;
    try { data = resp.json; } catch (_) { data = toString(resp.body); }
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("POST", "/api-telegram/test-webhook", (e) => {
    const url = UPSTREAM_BASE.replace(/\/+$/, "") + "/api/test-webhook";
    const reqInfo = e.requestInfo();
    const headers = { "Content-Type": "application/json" };
    if (reqInfo.headers && reqInfo.headers.authorization) {
        headers["Authorization"] = reqInfo.headers.authorization;
    }
    const body = reqInfo.body && (reqInfo.body.length || 0) > 0 ? toString(reqInfo.body) : null;
    let resp;
    try {
        resp = $http.send({ url: url, method: "POST", body: body, header: headers, timeout: 60 });
    } catch (err) {
        throw new Error("Servico Telegram API indisponivel");
    }
    let data;
    try { data = resp.json; } catch (_) { data = toString(resp.body); }
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});
