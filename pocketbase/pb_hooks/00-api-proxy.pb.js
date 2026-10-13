/// <reference path="../pb_data/types.d.ts" />

// =============================================================================
// Proxy reverso: encaminha /api-telegram/* do frontend (mesma origem) para o
// servico Telegram API (FastAPI).
// =============================================================================
// ATENCAO: cada handler e 100% self-contained. Nenhum `const`/`let`/`function`
// declarado no top-level do arquivo, porque o JSVM do PB executa cada callback
// de routerAdd em um VM context separado do pool - qualquer referencia a
// declaracao do top-level (mesmo `const`) da `ReferenceError: not defined` em
// producao. Cada handler le a env, monta o URL e faz o $http.send sozinho.
// =============================================================================

routerAdd("POST", "/api-telegram/send-code", (e) => {
    const base = $os.getenv("TELEGRAM_API_URL") || "https://eh-tudo-telegram-account-webhook-telegram.aiyfgd.easypanel.host";
    const url = base.replace(/\/+$/, "") + "/api/send-code";
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
    // Protege contra status 0 do $http.send (timeout/DNS/connection refused).
    // e.json(0, ...) causa panic no Go: "invalid WriteHeader code 0".
    if (!resp || resp.status < 100) {
        return e.json(502, { detail: "Upstream Telegram API nao respondeu (status 0)" });
    }
    let data;
    // DEBUG: log do body antes de tentar decodar
    const _b = resp.body;
    const _bType = typeof _b;
    const _bLen = _b ? (_b.length || 0) : 0;
    let _bPreview = "";
    try { _bPreview = String(_b).substring(0, 50); } catch (_) {}
    console.log(`[proxy DEBUG] bodyType=${_bType} bodyLen=${_bLen} stringified=${_bPreview}`);

    // Tenta varias formas de decodificar Uint8Array -> string
    let text = "";
    if (_b && _bLen > 0) {
        // 1) helper global toString (documentado na skill pocketbase-jsvm)
        if (typeof toString === "function") {
            try { text = toString(_b); } catch (_) {}
            console.log(`[proxy DEBUG] toString -> len=${text.length} preview=${text.substring(0, 50)}`);
        }
        // 2) TextDecoder (se existir)
        if (!text && typeof TextDecoder !== "undefined") {
            try { text = new TextDecoder("utf-8").decode(_b); } catch (_) {}
            console.log(`[proxy DEBUG] TextDecoder -> len=${text.length}`);
        }
        // 3) fallback manual: itera bytes
        if (!text) {
            try {
                for (let i = 0; i < _bLen; i++) {
                    text += String.fromCharCode(_b[i] & 0xFF);
                }
                console.log(`[proxy DEBUG] manualLoop -> len=${text.length} preview=${text.substring(0, 50)}`);
            } catch (err) {
                console.log(`[proxy DEBUG] manualLoop ERROR: ${err.message}`);
            }
        }
    }
    try {
        data = JSON.parse(text);
    } catch (_) {
        data = text;
    }
    if (data === null || data === undefined) {
        data = text;
    }
    console.log(`[proxy DEBUG] final data type=${typeof data} len=${typeof data === "string" ? data.length : "n/a"}`);
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("POST", "/api-telegram/verify-code", (e) => {
    const base = $os.getenv("TELEGRAM_API_URL") || "https://eh-tudo-telegram-account-webhook-telegram.aiyfgd.easypanel.host";
    const url = base.replace(/\/+$/, "") + "/api/verify-code";
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
    // Protege contra status 0 do $http.send (timeout/DNS/connection refused).
    // e.json(0, ...) causa panic no Go: "invalid WriteHeader code 0".
    if (!resp || resp.status < 100) {
        return e.json(502, { detail: "Upstream Telegram API nao respondeu (status 0)" });
    }
    let data;
    // DEBUG: log do body antes de tentar decodar
    const _b = resp.body;
    const _bType = typeof _b;
    const _bLen = _b ? (_b.length || 0) : 0;
    let _bPreview = "";
    try { _bPreview = String(_b).substring(0, 50); } catch (_) {}
    console.log(`[proxy DEBUG] bodyType=${_bType} bodyLen=${_bLen} stringified=${_bPreview}`);

    // Tenta varias formas de decodificar Uint8Array -> string
    let text = "";
    if (_b && _bLen > 0) {
        // 1) helper global toString (documentado na skill pocketbase-jsvm)
        if (typeof toString === "function") {
            try { text = toString(_b); } catch (_) {}
            console.log(`[proxy DEBUG] toString -> len=${text.length} preview=${text.substring(0, 50)}`);
        }
        // 2) TextDecoder (se existir)
        if (!text && typeof TextDecoder !== "undefined") {
            try { text = new TextDecoder("utf-8").decode(_b); } catch (_) {}
            console.log(`[proxy DEBUG] TextDecoder -> len=${text.length}`);
        }
        // 3) fallback manual: itera bytes
        if (!text) {
            try {
                for (let i = 0; i < _bLen; i++) {
                    text += String.fromCharCode(_b[i] & 0xFF);
                }
                console.log(`[proxy DEBUG] manualLoop -> len=${text.length} preview=${text.substring(0, 50)}`);
            } catch (err) {
                console.log(`[proxy DEBUG] manualLoop ERROR: ${err.message}`);
            }
        }
    }
    try {
        data = JSON.parse(text);
    } catch (_) {
        data = text;
    }
    if (data === null || data === undefined) {
        data = text;
    }
    console.log(`[proxy DEBUG] final data type=${typeof data} len=${typeof data === "string" ? data.length : "n/a"}`);
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("POST", "/api-telegram/set-webhook", (e) => {
    const base = $os.getenv("TELEGRAM_API_URL") || "https://eh-tudo-telegram-account-webhook-telegram.aiyfgd.easypanel.host";
    const url = base.replace(/\/+$/, "") + "/api/set-webhook";
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
    // Protege contra status 0 do $http.send (timeout/DNS/connection refused).
    // e.json(0, ...) causa panic no Go: "invalid WriteHeader code 0".
    if (!resp || resp.status < 100) {
        return e.json(502, { detail: "Upstream Telegram API nao respondeu (status 0)" });
    }
    let data;
    // DEBUG: log do body antes de tentar decodar
    const _b = resp.body;
    const _bType = typeof _b;
    const _bLen = _b ? (_b.length || 0) : 0;
    let _bPreview = "";
    try { _bPreview = String(_b).substring(0, 50); } catch (_) {}
    console.log(`[proxy DEBUG] bodyType=${_bType} bodyLen=${_bLen} stringified=${_bPreview}`);

    // Tenta varias formas de decodificar Uint8Array -> string
    let text = "";
    if (_b && _bLen > 0) {
        // 1) helper global toString (documentado na skill pocketbase-jsvm)
        if (typeof toString === "function") {
            try { text = toString(_b); } catch (_) {}
            console.log(`[proxy DEBUG] toString -> len=${text.length} preview=${text.substring(0, 50)}`);
        }
        // 2) TextDecoder (se existir)
        if (!text && typeof TextDecoder !== "undefined") {
            try { text = new TextDecoder("utf-8").decode(_b); } catch (_) {}
            console.log(`[proxy DEBUG] TextDecoder -> len=${text.length}`);
        }
        // 3) fallback manual: itera bytes
        if (!text) {
            try {
                for (let i = 0; i < _bLen; i++) {
                    text += String.fromCharCode(_b[i] & 0xFF);
                }
                console.log(`[proxy DEBUG] manualLoop -> len=${text.length} preview=${text.substring(0, 50)}`);
            } catch (err) {
                console.log(`[proxy DEBUG] manualLoop ERROR: ${err.message}`);
            }
        }
    }
    try {
        data = JSON.parse(text);
    } catch (_) {
        data = text;
    }
    if (data === null || data === undefined) {
        data = text;
    }
    console.log(`[proxy DEBUG] final data type=${typeof data} len=${typeof data === "string" ? data.length : "n/a"}`);
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("GET", "/api-telegram/sessions", (e) => {
    const base = $os.getenv("TELEGRAM_API_URL") || "https://eh-tudo-telegram-account-webhook-telegram.aiyfgd.easypanel.host";
    const url = base.replace(/\/+$/, "") + "/api/sessions";
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
    // Protege contra status 0 do $http.send (timeout/DNS/connection refused).
    // e.json(0, ...) causa panic no Go: "invalid WriteHeader code 0".
    if (!resp || resp.status < 100) {
        return e.json(502, { detail: "Upstream Telegram API nao respondeu (status 0)" });
    }
    let data;
    // DEBUG: log do body antes de tentar decodar
    const _b = resp.body;
    const _bType = typeof _b;
    const _bLen = _b ? (_b.length || 0) : 0;
    let _bPreview = "";
    try { _bPreview = String(_b).substring(0, 50); } catch (_) {}
    console.log(`[proxy DEBUG] bodyType=${_bType} bodyLen=${_bLen} stringified=${_bPreview}`);

    // Tenta varias formas de decodificar Uint8Array -> string
    let text = "";
    if (_b && _bLen > 0) {
        // 1) helper global toString (documentado na skill pocketbase-jsvm)
        if (typeof toString === "function") {
            try { text = toString(_b); } catch (_) {}
            console.log(`[proxy DEBUG] toString -> len=${text.length} preview=${text.substring(0, 50)}`);
        }
        // 2) TextDecoder (se existir)
        if (!text && typeof TextDecoder !== "undefined") {
            try { text = new TextDecoder("utf-8").decode(_b); } catch (_) {}
            console.log(`[proxy DEBUG] TextDecoder -> len=${text.length}`);
        }
        // 3) fallback manual: itera bytes
        if (!text) {
            try {
                for (let i = 0; i < _bLen; i++) {
                    text += String.fromCharCode(_b[i] & 0xFF);
                }
                console.log(`[proxy DEBUG] manualLoop -> len=${text.length} preview=${text.substring(0, 50)}`);
            } catch (err) {
                console.log(`[proxy DEBUG] manualLoop ERROR: ${err.message}`);
            }
        }
    }
    try {
        data = JSON.parse(text);
    } catch (_) {
        data = text;
    }
    if (data === null || data === undefined) {
        data = text;
    }
    console.log(`[proxy DEBUG] final data type=${typeof data} len=${typeof data === "string" ? data.length : "n/a"}`);
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("DELETE", "/api-telegram/session/{sessionId}", (e) => {
    const base = $os.getenv("TELEGRAM_API_URL") || "https://eh-tudo-telegram-account-webhook-telegram.aiyfgd.easypanel.host";
    const parts = e.requestInfo().path.split("/").filter(Boolean);
    const sessionId = parts[parts.length - 1] || "";
    const url = base.replace(/\/+$/, "") + "/api/session/" + sessionId;
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
    // Protege contra status 0 do $http.send (timeout/DNS/connection refused).
    // e.json(0, ...) causa panic no Go: "invalid WriteHeader code 0".
    if (!resp || resp.status < 100) {
        return e.json(502, { detail: "Upstream Telegram API nao respondeu (status 0)" });
    }
    let data;
    // DEBUG: log do body antes de tentar decodar
    const _b = resp.body;
    const _bType = typeof _b;
    const _bLen = _b ? (_b.length || 0) : 0;
    let _bPreview = "";
    try { _bPreview = String(_b).substring(0, 50); } catch (_) {}
    console.log(`[proxy DEBUG] bodyType=${_bType} bodyLen=${_bLen} stringified=${_bPreview}`);

    // Tenta varias formas de decodificar Uint8Array -> string
    let text = "";
    if (_b && _bLen > 0) {
        // 1) helper global toString (documentado na skill pocketbase-jsvm)
        if (typeof toString === "function") {
            try { text = toString(_b); } catch (_) {}
            console.log(`[proxy DEBUG] toString -> len=${text.length} preview=${text.substring(0, 50)}`);
        }
        // 2) TextDecoder (se existir)
        if (!text && typeof TextDecoder !== "undefined") {
            try { text = new TextDecoder("utf-8").decode(_b); } catch (_) {}
            console.log(`[proxy DEBUG] TextDecoder -> len=${text.length}`);
        }
        // 3) fallback manual: itera bytes
        if (!text) {
            try {
                for (let i = 0; i < _bLen; i++) {
                    text += String.fromCharCode(_b[i] & 0xFF);
                }
                console.log(`[proxy DEBUG] manualLoop -> len=${text.length} preview=${text.substring(0, 50)}`);
            } catch (err) {
                console.log(`[proxy DEBUG] manualLoop ERROR: ${err.message}`);
            }
        }
    }
    try {
        data = JSON.parse(text);
    } catch (_) {
        data = text;
    }
    if (data === null || data === undefined) {
        data = text;
    }
    console.log(`[proxy DEBUG] final data type=${typeof data} len=${typeof data === "string" ? data.length : "n/a"}`);
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});

routerAdd("POST", "/api-telegram/test-webhook", (e) => {
    const base = $os.getenv("TELEGRAM_API_URL") || "https://eh-tudo-telegram-account-webhook-telegram.aiyfgd.easypanel.host";
    const url = base.replace(/\/+$/, "") + "/api/test-webhook";
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
    // Protege contra status 0 do $http.send (timeout/DNS/connection refused).
    // e.json(0, ...) causa panic no Go: "invalid WriteHeader code 0".
    if (!resp || resp.status < 100) {
        return e.json(502, { detail: "Upstream Telegram API nao respondeu (status 0)" });
    }
    let data;
    // DEBUG: log do body antes de tentar decodar
    const _b = resp.body;
    const _bType = typeof _b;
    const _bLen = _b ? (_b.length || 0) : 0;
    let _bPreview = "";
    try { _bPreview = String(_b).substring(0, 50); } catch (_) {}
    console.log(`[proxy DEBUG] bodyType=${_bType} bodyLen=${_bLen} stringified=${_bPreview}`);

    // Tenta varias formas de decodificar Uint8Array -> string
    let text = "";
    if (_b && _bLen > 0) {
        // 1) helper global toString (documentado na skill pocketbase-jsvm)
        if (typeof toString === "function") {
            try { text = toString(_b); } catch (_) {}
            console.log(`[proxy DEBUG] toString -> len=${text.length} preview=${text.substring(0, 50)}`);
        }
        // 2) TextDecoder (se existir)
        if (!text && typeof TextDecoder !== "undefined") {
            try { text = new TextDecoder("utf-8").decode(_b); } catch (_) {}
            console.log(`[proxy DEBUG] TextDecoder -> len=${text.length}`);
        }
        // 3) fallback manual: itera bytes
        if (!text) {
            try {
                for (let i = 0; i < _bLen; i++) {
                    text += String.fromCharCode(_b[i] & 0xFF);
                }
                console.log(`[proxy DEBUG] manualLoop -> len=${text.length} preview=${text.substring(0, 50)}`);
            } catch (err) {
                console.log(`[proxy DEBUG] manualLoop ERROR: ${err.message}`);
            }
        }
    }
    try {
        data = JSON.parse(text);
    } catch (_) {
        data = text;
    }
    if (data === null || data === undefined) {
        data = text;
    }
    console.log(`[proxy DEBUG] final data type=${typeof data} len=${typeof data === "string" ? data.length : "n/a"}`);
    return typeof data === "string" ? e.string(resp.status, data) : e.json(resp.status, data);
});
