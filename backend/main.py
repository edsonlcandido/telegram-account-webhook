"""
FastAPI Backend - Telegram Account Webhook
Gerencia sessões Telethon e forwards mensagens para webhooks dos clientes
"""

import os
import json
import time
import asyncio
import base64
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.events import NewMessage
from telethon.sessions import StringSession
from telethon.tl import types as tl_types

import httpx

# =============================================================================
# Configuração
# =============================================================================

API_ID = int(os.getenv("TG_API_ID", "0"))
API_HASH = os.getenv("TG_API_HASH", "")
POCKETBASE_URL = os.getenv("POCKETBASE_URL", "http://localhost:8090")
# =============================================================================
# Service token do PB — autenticação ÚNICA usada por todos os fluxos em
# background (handler do Telethon, jobs em background, qualquer chamada
# ao PB que não tenha request HTTP no contexto).
#
# Por que: chamadas internas ao PB exigem auth (a collection
# `telegram_messages` tem createRule "@request.auth.id != ''"), e
# repassar o token do user nesses fluxos é frágil (cache que esvazia
# em restart, token que expira, race entre login e primeira mensagem).
#
# Origem do token (em ordem de preferência):
#   1) POCKETBASE_SERVICE_TOKEN env var com JWT pronto (mais simples, sem
#      senha em env). Gerar uma vez no admin UI do PB e colar aqui.
#   2) POCKETBASE_ADMIN_EMAIL + POCKETBASE_ADMIN_PASSWORD — login automático
#      via `/_superusers/auth-with-password` no startup do container.
#
# Tokens de superuser são long-lived (default 14 dias, renovável) — pra
# ambiente de produção vale gerar um JWT dedicado via opção 1 e esquecer.
# =============================================================================
POCKETBASE_SERVICE_TOKEN_ENV = os.getenv("POCKETBASE_SERVICE_TOKEN", "")
POCKETBASE_ADMIN_EMAIL = os.getenv("POCKETBASE_ADMIN_EMAIL", "")
POCKETBASE_ADMIN_PASSWORD = os.getenv("POCKETBASE_ADMIN_PASSWORD", "")
# Cache do token em memória. Populado pelo lifespan startup, refresh em
# background task se 401.
_PB_SERVICE_TOKEN: Optional[str] = None
# `exp` (epoch seconds) do token cacheado — usado pra refresh proativo
# antes de quebrar ao meio de uma request. PB default é 14 dias, mas o
# admin pode estender via "verification lifetime" no admin UI.
_PB_SERVICE_TOKEN_EXP: Optional[int] = None
# Margem de segurança: refresh quando faltar `_PB_REFRESH_MARGIN_SEC`
# segundos. Evita race entre checagem de exp e request que tá saindo.
_PB_REFRESH_MARGIN_SEC = 300  # 5 min

SESSIONS_DIR = Path("/app/sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# PB Service Token — auth ÚNICA pra fluxos internos (handler Telethon)
# =============================================================================
# Por que: handler do Telethon roda em background sem request HTTP, então
# não tem user JWT pra repassar. Antes a gente tentava cachear o token
# do user dono da sessão em `_USER_TOKENS[user_id]`, mas o cache esvaziava
# em restart, em deploy, ou em qualquer janela onde o user ainda não
# tinha chamado endpoint autenticado desde o boot. A mensagem chegava,
# cache miss, handler DROP a mensagem com warning.
#
# Agora: UMA conta admin do PB (superuser) usada exclusivamente pra
# chamadas internas. Token cacheado em `_PB_SERVICE_TOKEN`, populado no
# lifespan startup, re-autenticado em background se 401.

def _jwt_exp(token: str) -> Optional[int]:
    """Extrai o claim `exp` (epoch seconds) de um JWT do PocketBase.

    Sem dependência externa (sem PyJWT). Decodifica só a payload
    (segundo segmento) com base64url. Retorna None se o token for
    malformado ou não tiver `exp`.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        # base64url precisa de padding múltiplo de 4
        payload_b64 += "=" * (-len(payload_b64) % 4)
        decoded = base64.urlsafe_b64decode(payload_b64)
        data = json.loads(decoded)
        exp = data.get("exp")
        return int(exp) if exp is not None else None
    except Exception:
        return None


async def _obtain_pb_service_token() -> tuple[str, Optional[int]]:
    """Obtém o service token (chamado quando precisa refresh).

    Estratégia (em ordem):
    1) POCKETBASE_SERVICE_TOKEN (env) com JWT pronto — sem senha no env.
       Gerar uma vez no admin UI. Pra refresh, o usuário é responsável
       por rotacionar o JWT antes de expirar (esse caminho não re-autentica).
    2) POCKETBASE_ADMIN_EMAIL + POCKETBASE_ADMIN_PASSWORD — login via
       /_superusers/auth-with-password. Esse caminho SEMPRE funciona e
       o token é refreshed automaticamente a cada `exp - 5min`.
    3) Senão, falha com mensagem clara.

    Returns: (token, exp_epoch_seconds ou None se caminho 1)
    """
    if POCKETBASE_SERVICE_TOKEN_ENV:
        logger.info("🔑 PB service token: usando POCKETBASE_SERVICE_TOKEN do env")
        return POCKETBASE_SERVICE_TOKEN_ENV, _jwt_exp(POCKETBASE_SERVICE_TOKEN_ENV)

    if not POCKETBASE_ADMIN_EMAIL or not POCKETBASE_ADMIN_PASSWORD:
        raise RuntimeError(
            "PB admin não configurado. Defina POCKETBASE_SERVICE_TOKEN (JWT) "
            "OU POCKETBASE_ADMIN_EMAIL + POCKETBASE_ADMIN_PASSWORD no env do "
            "serviço telegram-account-webhook-telegram."
        )

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{POCKETBASE_URL}/api/collections/_superusers/auth-with-password",
            json={
                "identity": POCKETBASE_ADMIN_EMAIL,
                "password": POCKETBASE_ADMIN_PASSWORD,
            },
        )
    if r.status_code != 200:
        raise RuntimeError(
            f"PB admin login falhou: {r.status_code} "
            f"{r.text[:200]} (verifique POCKETBASE_ADMIN_EMAIL/PASSWORD)"
        )
    body = r.json()
    token = body.get("token")
    if not token:
        raise RuntimeError(f"PB admin login não retornou token: {str(body)[:200]}")
    exp = _jwt_exp(token)
    if exp:
        remaining_days = (exp - int(time.time())) / 86400
        logger.info(
            f"🔑 PB service token: login como {POCKETBASE_ADMIN_EMAIL} OK "
            f"(exp em {remaining_days:.1f} dias)"
        )
    else:
        logger.info(f"🔑 PB service token: login como {POCKETBASE_ADMIN_EMAIL} OK")
    return token, exp


async def _ensure_pb_service_token() -> str:
    """Garante `_PB_SERVICE_TOKEN` válido (lazy + cached + auto-refresh).

    Refresh proativo: re-autentica quando faltar `_PB_REFRESH_MARGIN_SEC`
    segundos pro `exp` do token cacheado. Evita que uma request morra
    no meio com 401 porque o token expirou.

    Refresh reativo: se uma request retorna 401, o caller pode chamar
    `force_refresh_pb_service_token()` pra re-autenticar fora do ciclo
    lazy.
    """
    global _PB_SERVICE_TOKEN, _PB_SERVICE_TOKEN_EXP
    now = int(time.time())

    if _PB_SERVICE_TOKEN and _PB_SERVICE_TOKEN_EXP:
        if now < _PB_SERVICE_TOKEN_EXP - _PB_REFRESH_MARGIN_SEC:
            return _PB_SERVICE_TOKEN
        logger.info(
            f"🔄 PB service token próximo do expiry "
            f"(now={now}, exp={_PB_SERVICE_TOKEN_EXP}, margin={_PB_REFRESH_MARGIN_SEC}s). "
            f"Re-autenticando..."
        )
    elif _PB_SERVICE_TOKEN and not _PB_SERVICE_TOKEN_EXP:
        # Caminho 1 (token fixo do env) sem exp parseado — assume válido.
        # Pra ter auto-refresh, o user precisa usar caminho 2 (login).
        return _PB_SERVICE_TOKEN

    _PB_SERVICE_TOKEN, _PB_SERVICE_TOKEN_EXP = await _obtain_pb_service_token()
    return _PB_SERVICE_TOKEN


async def force_refresh_pb_service_token() -> str:
    """Força re-autenticação (chamar quando PB retorna 401)."""
    global _PB_SERVICE_TOKEN, _PB_SERVICE_TOKEN_EXP
    logger.info("🔄 PB service token: refresh forçado (provável 401)")
    _PB_SERVICE_TOKEN, _PB_SERVICE_TOKEN_EXP = await _obtain_pb_service_token()
    return _PB_SERVICE_TOKEN


def pb_service_headers() -> dict:
    """Header pronto pra chamadas internas ao PB (Telethon handler etc).

    Raises se o token não tiver sido inicializado — nesse caso o caller
    deve chamar `_ensure_pb_service_token()` antes (normalmente já foi
    feito no lifespan startup).
    """
    if not _PB_SERVICE_TOKEN:
        raise RuntimeError(
            "_PB_SERVICE_TOKEN não inicializado. Chame _ensure_pb_service_token() "
            "antes (lifespan startup deve ter feito isso)."
        )
    return {"Authorization": _PB_SERVICE_TOKEN}


# Armazenamento em memória: session_id -> TelegramClient
active_clients: Dict[str, TelegramClient] = {}


# =============================================================================
# Modelos Pydantic
# =============================================================================

class SendCodeRequest(BaseModel):
    phone_number: str


class VerifyCodeRequest(BaseModel):
    phone_number: str
    code: str
    password: Optional[str] = None
    name: Optional[str] = None  # alias amigável pro usuário


class CreateWebhookRequest(BaseModel):
    name: Optional[str] = None
    url: str
    enabled: bool = True
    filter_direction: str = "all"  # all | incoming | outgoing
    filter_chat_type: str = "all"  # all | private | group | supergroup | channel
    filter_text_match_operator: str = "none"  # none | equals | contains
    filter_text_match_value: Optional[str] = None


class UpdateWebhookRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    enabled: Optional[bool] = None
    filter_direction: Optional[str] = None
    filter_chat_type: Optional[str] = None
    filter_text_match_operator: Optional[str] = None
    filter_text_match_value: Optional[str] = None


class ToggleWebhookRequest(BaseModel):
    enabled: bool


class TestWebhookRequest(BaseModel):
    pass  # sem body — a URL vem do webhook_id na rota


class UpdateSessionRequest(BaseModel):
    name: Optional[str] = None  # alias


class SendMessageRequest(BaseModel):
    session_id: str
    chat_id: int | str  # aceita ID numérico (int) ou @username (str)
    text: str
    reply_to_message_id: Optional[int] = None


# =============================================================================
# Persistência de Sessões
# =============================================================================

def get_session_file(session_id: str) -> Path:
    """Retorna o caminho do arquivo de sessão"""
    return SESSIONS_DIR / f"{session_id}.session"


def save_session(session_id: str, session_string: str, phone: str):
    """Salva apenas a credencial no sistema de arquivos.

    Metadados editáveis (name, webhooks) ficam no PocketBase como source
    of truth — o arquivo é só pra carregar a sessão Telethon de volta no boot.
    """
    session_file = get_session_file(session_id)
    data = {
        "session_string": session_string,
        "phone": phone,
        "created_at": datetime.now().isoformat(),
    }
    session_file.write_text(json.dumps(data))
    logger.info(f"💾 Sessão salva: {session_id}")


def load_sessions() -> list:
    """Carrega todas as sessões salvas"""
    sessions = []
    for session_file in SESSIONS_DIR.glob("*.session"):
        try:
            data = json.loads(session_file.read_text())
            session_id = session_file.stem
            sessions.append({
                "session_id": session_id,
                **data
            })
        except Exception as e:
            logger.error(f"Erro ao carregar {session_file}: {e}")
    return sessions


def delete_session_file(session_id: str):
    """Remove arquivo de sessão"""
    session_file = get_session_file(session_id)
    if session_file.exists():
        session_file.unlink()
        logger.info(f"🗑️ Arquivo de sessão removido: {session_id}")


# =============================================================================
# Event Handler - Forwarding + audit log
# =============================================================================
#
# A lógica de filtro + envio pros webhooks + INSERT de audit é feita
# toda pelo Telethon service (este arquivo). Razão: o container do
# PB no Easypanel pode ter egress restrito pra certos IPs externos
# (network ACL) — $http.send trava indefinidamente. O Telethon
# service tem egress liberado (fala com Telegram API, PB, IPs
# externos) e Python httpx com timeout limpo.
#
# O FastAPI usa UM único service token (_PB_SERVICE_TOKEN, cacheado
# no lifespan startup) pra TODAS as chamadas internas ao PB — não
# cacheia token por user, não cacheia pb_id por sessão, não tenta
# descobrir "dono" da sessão. O token é refrescado proativamente
# 5 min antes do `exp` (ver `_ensure_pb_service_token`).
#
# O hook `onRecordAfterCreateSuccess` em `pocketbase/pb_hooks/main.pb.js`
# é NO-OP — só loga o INSERT, sem fazer forwarding. Sem duplicação
# de webhook.
#
# Audit log: `telegram_messages` recebe TODA mensagem (incoming +
# outgoing), incluindo as que o user enviou via /api/send-message.
# A supressão de forwarding pra evitar loop com o receptor do webhook
# (ex: n8n respondendo) acontece SÓ no loop de webhooks, não no INSERT.


def _classify_chat_type(event) -> str:
    """Retorna o tipo do chat: 'private' | 'group' | 'supergroup' | 'channel' | 'unknown'."""
    if event.is_private:
        return "private"
    if event.is_channel:
        return "channel"
    if event.is_group:
        # Telethon não distingue group de supergroup via flag — assume 'group'
        # (o hook pode fazer o refinamento se precisar)
        return "group"
    return "unknown"


def _chat_title(event) -> str | None:
    """Title do chat (pra groups) ou first_name (pra private). None se não tem."""
    if not event.chat:
        return None
    return getattr(event.chat, "title", None) or getattr(event.chat, "first_name", None)


def _sender_name(event) -> str | None:
    """Nome completo do sender, ou None."""
    if not event.sender:
        return None
    first = event.sender.first_name or ""
    last = f" {event.sender.last_name}" if getattr(event.sender, "last_name", None) else ""
    full = (first + last).strip()
    return full or None


async def _sender_username(event) -> str:
    """@username do sender no Telegram (sem o @), ou string vazia.

    Vem vazio se:
    - Sender é um canal (canais usam channel username, não user)
    - User não tem @username configurado
    - event.sender ausente (msg anônima)
    - API do Telegram recusou (user bloqueado, sem permissão, etc)

    Estratégia (tenta em ordem, retorna o primeiro que achar):
    1) `event.sender.username` — Telethon cacheia quando abre a conversa.
    2) `event.chat.username` — em chat privado, `event.chat` É o outro
       user, então é mais confiável que `event.sender` (que pode vir
       com User object incompleto se o cache do Telethon tá frio).
    3) `await client.get_entity(sender_id)` — fallback assíncrono via
       API do Telegram. Funciona se o user já interagiu com a conta
       monitorada (Telethon tem access_hash em cache).
    """
    # 1) Sender direto
    sender = getattr(event, "sender", None)
    if sender:
        u = getattr(sender, "username", None)
        if u:
            return u

    # 2) Em chat privado, chat É o user — checa essa fonte
    if getattr(event, "is_private", False):
        chat = getattr(event, "chat", None)
        if chat:
            u = getattr(chat, "username", None)
            if u:
                return u

    # 3) Fallback: busca via API do Telegram
    sender_id = getattr(event, "sender_id", None)
    client = getattr(event, "client", None)
    if sender_id and client:
        try:
            full = await client.get_entity(sender_id)
            if full:
                u = getattr(full, "username", None)
                if u:
                    return u
        except Exception as e:
            logger.debug(f"sender_username fallback fetch falhou: {e}")

    return ""


async def handle_new_message(event, session_id: str):
    """Handler que dispara quando chega nova mensagem.

    Fluxo (refactor — Telethon service faz o forwarding direto):
    1) Garante service token do PB (cacheado no lifespan startup).
    2) Acha o pb_id da sessão (1 GET).
    3) Lista webhooks ativos dessa sessão (1 GET, com filter).
    4) Aplica filtros (direction, chat_type, text_match).
    5) POST em cada webhook que passar — httpx com timeout 10s.
    6) INSERT em `telegram_messages` (audit log; hook do PB é no-op).

    Por que FastAPI faz forwarding e não o hook do PB:
    O container do PB pode não ter egress liberado pra certos IPs
    externos (Easypanel network ACL). Telethon service JÁ tem egress
    OK — fala com Telegram API, com PB, e tem Python httpx com
    timeout/error handling limpos. Antes não era possível porque o
    service token não existia — agora existe (ver `_PB_SERVICE_TOKEN`).
    """
    try:
        logger.info(
            f"📩 Nova mensagem: session={session_id} "
            f"chat={event.chat_id} msg_id={event.id}"
        )

        if session_id not in active_clients:
            logger.warning(
                f"⚠️ Msg de sessão {session_id} que não está em active_clients"
            )
            return

        # Audit log SEMPRE acontece — mesmo pras mensagens que nós
        # mesmos enviamos via /api/send-message. A supressão de
        # forwarding pra essas mensagens é feita DENTRO do loop
        # de webhooks (skip do POST, não do audit).

        # Service token (cacheado no lifespan, re-auth se expirado)
        await _ensure_pb_service_token()
        headers = pb_service_headers()

        # 1) Lookup da sessão
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
                params={"filter": f'session_id="{session_id}"', "perPage": 1},
                headers=headers,
            )
        if r.status_code != 200:
            logger.error(
                f"PB recusou lookup de sessão {session_id}: "
                f"{r.status_code} {r.text[:200]}"
            )
            return
        items = r.json().get("items", [])
        if not items:
            logger.warning(
                f"⚠️ Sessão {session_id} não existe no PB — ignorando msg "
                f"(provavelmente foi deletada mas o Telethon client ainda tá "
                f"rodando com sessão antiga)"
            )
            return
        session = items[0]
        pb_session_id = session["id"]
        session_phone = session.get("phone", "")
        session_name = session.get("name", "")

        # 2) Extrai metadados da mensagem
        sender_name = _sender_name(event) or ""
        sender_username = await _sender_username(event)
        chat_title = _chat_title(event) or ""
        is_outgoing = bool(getattr(event, "outgoing", False))
        direction = "outgoing" if is_outgoing else "incoming"
        chat_type = _classify_chat_type(event)
        text = event.text or ""
        ts = event.date.isoformat() if getattr(event, "date", None) else ""

        # 3) Lista webhooks ativos da sessão
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records",
                params={
                    "filter": f'session="{pb_session_id}" && enabled=true',
                    "perPage": 500,
                },
                headers=headers,
            )
        if r.status_code != 200:
            logger.error(
                f"PB recusou listagem de webhooks: {r.status_code} {r.text[:200]}"
            )
            # Não retorna — INSERT de audit pode continuar
            webhooks = []
        else:
            webhooks = r.json().get("items", [])

        # 5) Filtra e distribui
        # Anti-loop: se a mensagem foi enviada por NÓS mesmos via
        # /api/send-message nos últimos 10s, suprime o POST mas a
        # audit INSERT em `telegram_messages` continua normal.
        skip_forwarding = _is_recently_sent(event.id)
        delivered = 0
        failed = 0
        for wh in webhooks:
            if not wh:
                continue

            # Filtro de direction
            fdir = wh.get("filter_direction") or "all"
            if fdir != "all" and fdir != direction:
                continue

            # Filtro de chat_type
            fct = wh.get("filter_chat_type") or "all"
            if fct != "all" and fct != chat_type:
                continue

            # Filtro de text_match
            op = wh.get("filter_text_match_operator") or "none"
            if op != "none":
                val = (wh.get("filter_text_match_value") or "").strip()
                if val:
                    needle = val.lower()
                    haystack = text.lower()
                    if op == "equals" and haystack != needle:
                        continue
                    if op == "contains" and needle not in haystack:
                        continue

            # Anti-loop: pular o POST (mas o audit INSERT já foi
            # feito, ou vai ser feito depois).
            if skip_forwarding:
                continue

            url = wh.get("url")
            if not url:
                continue

            payload = {
                "event": "telegram.message",
                "webhook_id": wh.get("id"),
                "webhook_name": wh.get("name"),
                "session": {
                    "pb_id": pb_session_id,
                    "session_id": session_id,
                    "phone": session_phone,
                    "name": session_name,
                },
                "message": {
                    "id": event.id,
                    "chat_id": event.chat_id,
                    "chat_type": chat_type,
                    "chat_title": chat_title,
                    "direction": direction,
                    "sender_id": event.sender_id,
                    "sender_name": sender_name,
                    "sender_username": sender_username,
                    "text": text,
                    "timestamp": ts,
                },
            }

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, json=payload)
                if 200 <= resp.status_code < 300:
                    delivered += 1
                    logger.info(
                        f"✅ webhook delivered msg={event.id} "
                        f"wh={wh.get('id')} status={resp.status_code}"
                    )
                else:
                    failed += 1
                    logger.warning(
                        f"⚠️ webhook non-2xx msg={event.id} "
                        f"wh={wh.get('id')} status={resp.status_code} "
                        f"body={resp.text[:200]}"
                    )
            except Exception as e:
                failed += 1
                logger.warning(
                    f"⚠️ webhook FAILED msg={event.id} "
                    f"wh={wh.get('id')} url={url} "
                    f"err={str(e)[:200]}"
                )

        logger.info(
            f"📨 Msg #{event.id} (sessão {session_id}): "
            f"webhooks={len(webhooks)} delivered={delivered} failed={failed}"
        )

        # 6) INSERT em telegram_messages (audit log). Hook do PB é no-op
        # então não dispara forwarding duplicado.
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    f"{POCKETBASE_URL}/api/collections/telegram_messages/records",
                    json={
                        "session": pb_session_id,
                        "chat_id": int(event.chat_id or 0),
                        "chat_type": chat_type,
                        "chat_title": chat_title,
                        "direction": direction,
                        "sender_id": int(event.sender_id or 0),
                        "sender_name": sender_name,
                        "sender_username": sender_username,
                        "text": text,
                    },
                    headers=headers,
                )
            if r.status_code >= 300:
                logger.warning(
                    f"PB recusou INSERT audit msg: {r.status_code} {r.text[:200]}"
                )
        except Exception as e:
            logger.error(f"Erro fazendo INSERT audit de msg no PB: {e}")

    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {e}")


# =============================================================================
# Gerenciamento de Clientes Telethon
# =============================================================================

# Cache de IDs que enviamos via /api/send-message — evita que o handler
# dispare o webhook de volta pra mensagens que NÓS mesmos enviamos pela
# nossa API (loop infinito: webhook chega → n8n chama /api/send-message →
# webhook chega de novo → ...).
#
# Formato: {message_id: timestamp_envio}. TTL: 10 segundos (Telethon
# entrega o evento outgoing de forma síncrona logo após o send_message
# retornar, então 10s é folgado).
_RECENTLY_SENT_IDS: dict[int, float] = {}
_RECENTLY_SENT_TTL_SEC = 10.0


def _is_recently_sent(message_id: int) -> bool:
    """True se essa mensagem foi enviada por nós via /api/send-message
    nos últimos _RECENTLY_SENT_TTL_SEC segundos."""
    import time as _time
    now = _time.time()
    expired = [k for k, v in _RECENTLY_SENT_IDS.items() if now - v > _RECENTLY_SENT_TTL_SEC]
    for k in expired:
        _RECENTLY_SENT_IDS.pop(k, None)
    return message_id in _RECENTLY_SENT_IDS


def register_message_handler(client, session_id: str):
    """
    Anexa o handler de novas mensagens ao client. Chamado tanto por
    `start_client` (sessões carregadas do disco no boot) quanto por
    `verify_code` (sessões criadas no signup) — sem isso, o webhook
    nunca dispara ao receber mensagem em contas recém-criadas.

    Captura TANTO incoming (mensagens de outros) QUANTO outgoing (mensagens
    enviadas pela própria conta — pelo celular, desktop, web Telegram). O
    payload inclui `outgoing: bool` pra o consumidor filtrar como quiser.

    Mensagens enviadas via nosso próprio /api/send-message são suprimidas
    via _is_recently_sent() pra evitar loop com o webhook.

    NOTA: precisa ser `def` (não `async def`) porque não há `await`
    dentro. Se fosse `async def` chamado sem `await`, retornaria uma
    coroutine não-awaitada e o `@client.on(...)` nunca seria aplicado.
    """
    @client.on(NewMessage())
    async def handler(event):
        # NÃO suprime aqui — queremos que TODA mensagem (incluindo as
        # que nós mesmos enviamos via /api/send-message) seja inserida
        # em `telegram_messages` (audit log completo). A supressão
        # pra evitar loop com o receptor do webhook (ex: n8n
        # respondendo às nossas mensagens) acontece DENTRO do
        # `handle_new_message`, no loop de webhooks (skip só do
        # POST, não do audit).
        await handle_new_message(event, session_id)
    logger.debug(f"📨 Handler NewMessage registrado para {session_id}")


async def start_client(session_id: str, session_string: str, phone: str):
    """Inicia um cliente Telethon com event handler"""
    client = TelegramClient(
        StringSession(session_string),
        API_ID,
        API_HASH,
        device_model="Telegram-Webhook-Service"
    )

    try:
        await client.start()
        logger.info(f"✅ Cliente conectado: {session_id} ({phone})")

        register_message_handler(client, session_id)

        # Armazena cliente ativo
        active_clients[session_id] = client

        return client

    except Exception as e:
        logger.error(f"Erro ao iniciar cliente {session_id}: {e}")
        raise


async def initialize_sessions():
    """Inicializa todas as sessões salvas ao iniciar o servidor"""
    logger.info("🔄 Carregando sessões salvas...")
    sessions = load_sessions()

    for session in sessions:
        try:
            await start_client(
                session["session_id"],
                session["session_string"],
                session["phone"]
            )
        except Exception as e:
            logger.error(f"Falha ao carregar sessão {session['session_id']}: {e}")

    logger.info(f"📡 {len(active_clients)} sessões ativas")


# =============================================================================
# Lifespan - Inicialização e Cleanup
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 FastAPI Starting...")

    # Valida credenciais Telegram
    if API_ID == 0 or not API_HASH:
        logger.warning("⚠️ TG_API_ID ou TG_API_HASH não configurados!")

    # Obtém o service token do PB. Sem isso, o handler do Telethon não
    # consegue inserir em `telegram_messages` (createRule exige auth).
    # Se falhar aqui, NÃO inicia o app — crash loud.
    try:
        await _ensure_pb_service_token()
    except Exception as e:
        logger.error(f"❌ Falha ao obter PB service token: {e}")
        raise

    # Inicializa sessões Telethon
    await initialize_sessions()

    yield

    # Cleanup
    logger.info("👋 FastAPI Shutting down...")
    for session_id, client in active_clients.items():
        await client.disconnect()
    logger.info("✅ Todas as sessões desconectadas")


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Telegram Account Webhook API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS restrito — em produção o frontend e o telegram-api ficam atrás do
# proxy do Easypanel na mesma origem (sem necessidade de CORS). A env var
# `ALLOWED_ORIGINS` aceita uma lista CSV pra casos de dev ou domínios
# específicos (ex.: app.exemplo.com,admin.exemplo.com).
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8090,http://localhost:5173,http://localhost:5174",
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# =============================================================================
# Autenticação via token (validado pelo próprio PB via /auth-refresh)
# =============================================================================

# Cache: token -> (user_dict, expires_at_epoch)
_auth_cache: Dict[str, tuple] = {}
AUTH_CACHE_TTL = 300  # 5 minutos


async def verify_pb_auth(authorization: str | None = Header(default=None)) -> dict:
    """
    Dependency que valida o token PB. Aceita tanto `Authorization: Bearer <jwt>`
    quanto `Authorization: <jwt>` (PB envia so o JWT cru, sem prefixo Bearer).
    Confia no PB como fonte de verdade (chama /auth-refresh) e cacheia por
    5 min pra nao martelar o PB a cada request.
    """
    if not authorization:
        raise HTTPException(401, "Não autenticado")

    # Aceita "Bearer <token>" ou "<token>" direto
    parts = authorization.strip().split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1].strip()
    else:
        token = parts[0].strip()
    now = time.time()

    cached = _auth_cache.get(token)
    if cached and cached[1] > now:
        user = cached[0]
    else:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # PB 0.40+ mudou o endpoint de GET pra POST. GET agora retorna 404.
                resp = await client.post(
                    f"{POCKETBASE_URL}/api/collections/users/auth-refresh",
                    headers={"Authorization": f"Bearer {token}"},
                )
            if resp.status_code != 200:
                _auth_cache.pop(token, None)
                raise HTTPException(401, "Token inválido ou expirado")
            user = resp.json()
            _auth_cache[token] = (user, now + AUTH_CACHE_TTL)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Falha ao validar token PB: {e}")
            raise HTTPException(503, "Serviço de autenticação indisponível")

    return user


async def get_user_token(authorization: str | None = Header(default=None)) -> str:
    """
    Extrai o JWT cru do header Authorization pra repassar nas chamadas
    internas ao PocketBase.

    Por que separado de `verify_pb_auth`: aquele VALIDA o token (chama
    /auth-refresh no PB, cacheia 5min); este só EXTRAI o string do header
    sem chamar nada. Os endpoints que fazem proxy ao PB precisam dos dois
    — o validate garante que o user está logado, o extract dá o string
    pra mandar de volta pro PB.

    O PB NÃO aceita o prefixo "Bearer" no header — só lê
    `Authorization: <token>` cru. Se receber "Bearer xxx" o parse
    interno não reconhece o token.
    """
    if not authorization:
        raise HTTPException(401, "Não autenticado")
    parts = authorization.strip().split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return parts[0].strip()


def pb_headers(user_token: str) -> dict:
    """Monta o header que o PB aceita: `Authorization: <token>` (sem Bearer)."""
    return {"Authorization": user_token}


# =============================================================================
# Rotas
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Conta arquivos salvos em /app/sessions/*.json (sem fazer I/O pesado —
    # só glob, não lê conteúdo). Útil pra distinguir:
    #   - active=0 + saved=0 → nunca criou conta ou volume foi perdido
    #   - active=0 + saved>0 → arquivos persistem mas client.start() falhou
    saved_count = sum(1 for _ in SESSIONS_DIR.glob("*.session"))
    return {
        "status": "ok",
        "active_sessions": len(active_clients),
        "saved_sessions": saved_count,
        "sessions_dir": str(SESSIONS_DIR),
        "api_configured": API_ID != 0 and bool(API_HASH),
    }


# -----------------------------------------------------------------------------
# 1. Enviar código de verificação
# -----------------------------------------------------------------------------
@app.post("/api/send-code")
async def send_code(request: SendCodeRequest, _user: dict = Depends(verify_pb_auth)):
    """
    Envia código de verificação SMS para o número.
    Retorna phone_code_hash necessário para o próximo passo.
    """
    if API_ID == 0 or not API_HASH:
        raise HTTPException(
            status_code=500,
            detail="TG_API_ID e TG_API_HASH não configurados"
        )

    session_id = f"pending_{request.phone_number}"
    client = TelegramClient(StringSession(), API_ID, API_HASH)

    try:
        # Em modo servidor NÃO usar client.start() — ele tenta ler phone/código
        # do stdin interativamente e dispara EOFError. connect() só estabelece
        # a conexão TCP sem autenticar; send_code_request depois pede o SMS
        # sem precisar de auth prévia.
        await client.connect()
        result = await client.send_code_request(request.phone_number)

        # Salva temporariamente para usar na verificação
        active_clients[session_id] = client
        active_clients[f"{session_id}_hash"] = result.phone_code_hash

        return {
            "success": True,
            "session_id": session_id,
            "phone_code_hash": result.phone_code_hash,
            "expires": result.timeout
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------------------------------------------------------
# 2. Verificar código e criar sessão
# -----------------------------------------------------------------------------
@app.post("/api/verify-code")
async def verify_code(
    http_request: Request,
    body: VerifyCodeRequest,
    background_tasks: BackgroundTasks,
    _user: dict = Depends(verify_pb_auth),
):
    """
    Verifica o código, cria sessão persistente e inicia escuta.
    """
    session_id = f"pending_{body.phone_number}"
    hash_key = f"{session_id}_hash"

    if session_id not in active_clients or hash_key not in active_clients:
        raise HTTPException(
            status_code=400,
            detail="Sessão não encontrada. Solicite o código novamente."
        )

    client = active_clients[session_id]
    phone_code_hash = active_clients[hash_key]

    try:
        # Verifica código
        if body.password:
            await client.sign_in(
                body.phone_number,
                code=body.code,
                password=body.password,
                phone_code_hash=phone_code_hash
            )
        else:
            await client.sign_in(
                body.phone_number,
                code=body.code,
                phone_code_hash=phone_code_hash
            )

        # Salva sessão
        session_string = client.session.save()
        final_session_id = f"account_{body.phone_number.replace('+', '')}"

        # Persiste em arquivo (só credencial — name vai pro PB)
        save_session(final_session_id, session_string, body.phone_number)

        # Move cliente para sessão final
        active_clients[final_session_id] = client
        del active_clients[session_id]
        del active_clients[hash_key]

        # Registra handler de novas mensagens — sem isso, webhook nunca dispara
        # em contas criadas via signup (só funciona pra contas carregadas do
        # disco no boot via initialize_sessions → start_client).
        register_message_handler(client, final_session_id)

        # Extrai o token cru do header Authorization (PB só aceita sem prefixo
        # "Bearer"). Background tasks do FastAPI NÃO herdam o header da
        # request original — sem repassar, o PB rejeita com 401 porque a rule
        # `createRule: "@request.auth.id != ''"` falha em request anônimo.
        raw_auth = http_request.headers.get("authorization", "").strip()
        if raw_auth.lower().startswith("bearer "):
            user_token = raw_auth[7:].strip()
        else:
            user_token = raw_auth

        # Registra no PocketBase em background (inclui o alias se o user forneceu)
        background_tasks.add_task(
            register_account_pb,
            final_session_id,
            body.phone_number,
            user_token,
            body.name,
        )

        return {
            "success": True,
            "session_id": final_session_id,
            "message": "Conta pareada com sucesso!"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------------------------------------------------------
# 3. Webhooks (multi-webhook por sessão, com filtros)
# -----------------------------------------------------------------------------

async def _resolve_pb_session_id(session_id: str, user_token: str | None = None) -> str | None:
    """Resolve o `session_id` (string única) pro `id` do PB (record id)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
                params={"filter": f'session_id="{session_id}"', "perPage": 1},
                headers=pb_headers(user_token) if user_token else None,
            )
        items = r.json().get("items", [])
        return items[0]["id"] if items else None
    except Exception as e:
        logger.error(f"Erro resolvendo PB session: {e}")
        return None


async def _resolve_session_id_from_pb(pb_id: str, user_token: str | None = None) -> str | None:
    """Resolve o `id` do PB pra `session_id` (string)."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records/{pb_id}",
                headers=pb_headers(user_token) if user_token else None,
            )
        if r.status_code == 200:
            return r.json().get("session_id")
    except Exception as e:
        logger.error(f"Erro resolvendo session_id: {e}")
    return None


# 3a. Listar webhooks de uma sessão
@app.get("/api/sessions/{session_id}/webhooks")
async def list_session_webhooks(
    session_id: str,
    _user: dict = Depends(verify_pb_auth),
    user_token: str = Depends(get_user_token),
):
    pb_id = await _resolve_pb_session_id(session_id, user_token)
    if not pb_id:
        return {"webhooks": []}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records",
                # Sem `sort=created`: PB 0.40+ rejeita sort nos system fields
                # `created`/`updated` com 400. Como só listamos webhooks de UMA
                # sessão, a ordem de criação não é tão importante — o `id`
                # (gerado pelo PB em ordem cronológica) é suficiente.
                params={"filter": f'session="{pb_id}"', "perPage": 500},
                headers=pb_headers(user_token),
            )
        items = r.json().get("items", [])
        for w in items:
            w["session_id"] = session_id
        return {"webhooks": items}
    except Exception as e:
        raise HTTPException(500, f"Erro ao listar webhooks: {e}")


# 3b. Criar webhook
@app.post("/api/sessions/{session_id}/webhooks")
async def create_webhook(
    session_id: str,
    request: CreateWebhookRequest,
    _user: dict = Depends(verify_pb_auth),
    user_token: str = Depends(get_user_token),
):
    pb_id = await _resolve_pb_session_id(session_id, user_token)
    if not pb_id:
        raise HTTPException(404, "Sessão não encontrada no PB")

    # Default name = "Webhook 1", "Webhook 2"... baseado em quantos já existem
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            cnt_r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records",
                params={"filter": f'session="{pb_id}"', "perPage": 500, "fields": "id"},
                headers=pb_headers(user_token),
            )
        existing_count = len(cnt_r.json().get("items", []))
    except Exception:
        existing_count = 0
    name = request.name or f"Webhook {existing_count + 1}"

    payload = {
        "session": pb_id,
        "name": name,
        "url": request.url,
        "enabled": request.enabled,
        "filter_direction": request.filter_direction,
        "filter_chat_type": request.filter_chat_type,
        "filter_text_match_operator": request.filter_text_match_operator,
        "filter_text_match_value": request.filter_text_match_value or "",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records",
                json=payload,
                headers=pb_headers(user_token),
            )
        if r.status_code >= 300:
            raise HTTPException(400, f"PB recusou: {r.text}")
        pass  # invalidate removed (hook do PB faz cache via SQL)
        result = r.json()
        result["session_id"] = session_id
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao criar webhook: {e}")


# 3c. Atualizar webhook parcial
@app.patch("/api/webhooks/{webhook_id}")
async def update_webhook(
    webhook_id: str,
    request: UpdateWebhookRequest,
    _user: dict = Depends(verify_pb_auth),
    user_token: str = Depends(get_user_token),
):
    payload = {k: v for k, v in request.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(400, "Nada pra atualizar")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.patch(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records/{webhook_id}",
                json=payload,
                headers=pb_headers(user_token),
            )
        if r.status_code >= 300:
            raise HTTPException(400, f"PB recusou: {r.text}")
        result = r.json()
        sid = await _resolve_session_id_from_pb(result.get("session", ""), user_token)
        if sid:
            pass  # invalidate removed (hook do PB faz cache via SQL)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao atualizar webhook: {e}")


# 3d. Remover webhook
@app.delete("/api/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: str,
    _user: dict = Depends(verify_pb_auth),
    user_token: str = Depends(get_user_token),
):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r_get = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records/{webhook_id}",
                headers=pb_headers(user_token),
            )
            if r_get.status_code != 200:
                raise HTTPException(404, "Webhook não encontrado")
            wh = r_get.json()
            sid = await _resolve_session_id_from_pb(wh.get("session", ""), user_token)

            r = await client.delete(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records/{webhook_id}",
                headers=pb_headers(user_token),
            )
        if r.status_code >= 300:
            raise HTTPException(400, f"PB recusou: {r.text}")
        if sid:
            pass  # invalidate removed (hook do PB faz cache via SQL)
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao remover webhook: {e}")


# 3e. Pausar/retomar webhook
@app.post("/api/webhooks/{webhook_id}/toggle")
async def toggle_webhook(
    webhook_id: str,
    request: ToggleWebhookRequest,
    _user: dict = Depends(verify_pb_auth),
    user_token: str = Depends(get_user_token),
):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r_get = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records/{webhook_id}",
                headers=pb_headers(user_token),
            )
            if r_get.status_code != 200:
                raise HTTPException(404, "Webhook não encontrado")
            sid = await _resolve_session_id_from_pb(r_get.json().get("session", ""), user_token)

            r = await client.patch(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records/{webhook_id}",
                json={"enabled": request.enabled},
                headers=pb_headers(user_token),
            )
        if r.status_code >= 300:
            raise HTTPException(400, f"PB recusou: {r.text}")
        if sid:
            pass  # invalidate removed (hook do PB faz cache via SQL)
        return r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao alternar webhook: {e}")


# 3f. Testar webhook (POST simplificado)
@app.post("/api/webhooks/{webhook_id}/test")
async def test_webhook_endpoint(
    webhook_id: str,
    _user: dict = Depends(verify_pb_auth),
    user_token: str = Depends(get_user_token),
):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r_get = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records/{webhook_id}",
                headers=pb_headers(user_token),
            )
            if r_get.status_code != 200:
                raise HTTPException(404, "Webhook não encontrado")
            url = r_get.json().get("url")
            if not url:
                raise HTTPException(400, "Webhook sem URL")

            response = await client.post(
                url,
                json={
                    "type": "test",
                    "message": "Conexão OK!",
                    "timestamp": datetime.now().isoformat(),
                },
            )
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, str(e))


# 3g. Atualizar metadados da sessão (alias)
@app.patch("/api/sessions/{session_id}")
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    _user: dict = Depends(verify_pb_auth),
    user_token: str = Depends(get_user_token),
):
    if request.name is None:
        raise HTTPException(400, "Nada pra atualizar")
    pb_id = await _resolve_pb_session_id(session_id, user_token)
    if not pb_id:
        raise HTTPException(404, "Sessão não encontrada no PB")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.patch(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records/{pb_id}",
                json={"name": request.name},
                headers=pb_headers(user_token),
            )
        if r.status_code >= 300:
            raise HTTPException(400, f"PB recusou: {r.text}")
        return r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao atualizar sessão: {e}")


# 3h. Refresh manual do cache (admin)
@app.post("/api/webhooks/refresh-cache")
async def refresh_webhook_cache(_user: dict = Depends(verify_pb_auth)):
    pass  # invalidate removed (hook do PB faz cache via SQL)
    return {"success": True}


# -----------------------------------------------------------------------------
# 4. Listar sessões
# -----------------------------------------------------------------------------
@app.get("/api/sessions")
async def list_sessions(
    _user: dict = Depends(verify_pb_auth),
    user_token: str = Depends(get_user_token),
):
    """Lista todas as sessões (arquivo é source of truth pra credencial; PB pra metadados)."""
    saved = load_sessions()

    # Cruza com PB pra buscar name + webhook_count em batch.
    # PB não tem JOIN — faço 2 queries globais e cruz em memória (N é pequeno).
    name_by_sid: Dict[str, str] = {}
    pb_id_by_sid: Dict[str, str] = {}
    counts_by_pb_id: Dict[str, int] = {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            sess_resp = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
                params={"perPage": 500, "fields": "id,session_id,name"},
                headers=pb_headers(user_token),
            )
            for s in sess_resp.json().get("items", []):
                sid = s.get("session_id", "")
                name_by_sid[sid] = s.get("name", "") or ""
                pb_id_by_sid[sid] = s.get("id", "")

            wh_resp = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records",
                params={"perPage": 500, "fields": "session"},
                headers=pb_headers(user_token),
            )
            for w in wh_resp.json().get("items", []):
                sid = w.get("session", "")
                counts_by_pb_id[sid] = counts_by_pb_id.get(sid, 0) + 1
    except Exception as e:
        logger.warning(f"Falha ao buscar metadados PB pra list_sessions: {e}")

    return {
        "sessions": [
            {
                "session_id": s["session_id"],
                "phone": s.get("phone", ""),
                "name": name_by_sid.get(s["session_id"], "") or "",
                "active": s["session_id"] in active_clients,
                "created_at": s.get("created_at"),
                "webhook_count": counts_by_pb_id.get(
                    pb_id_by_sid.get(s["session_id"], ""), 0
                ),
            }
            for s in saved
        ]
    }


# -----------------------------------------------------------------------------
# 5. Remover sessão
# -----------------------------------------------------------------------------
@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str, _user: dict = Depends(verify_pb_auth)):
    """Remove uma sessão (desconecta cliente ativo, remove arquivo + cache)."""
    # Desconecta cliente ativo
    if session_id in active_clients:
        await active_clients[session_id].disconnect()
        del active_clients[session_id]

    # Remove arquivo
    delete_session_file(session_id)

    return {"success": True}


# =============================================================================
# Funções Auxiliares
# =============================================================================

async def register_account_pb(
    session_id: str,
    phone: str,
    user_token: str | None = None,
    name: str | None = None,
):
    """Registra/atualiza a conta no PB (collection `telegram_sessions`).

    A StringSession NÃO é enviada — ela fica só no arquivo em
    `/app/sessions/*.json` (credencial). A collection no PB guarda só
    metadados leves (phone, name) e a relação com `telegram_webhooks`.
    Credenciais do app Telegram (api_id/api_hash) vivem nos env vars
    do container e são sempre as mesmas (single-app).

    `user_token` é o JWT cru do usuário (sem prefixo "Bearer" — o PB
    não aceita). Sem ele, o PB rejeita as chamadas com 401 porque
    `createRule: "@request.auth.id != ''"` exige auth.
    """
    payload: dict = {
        "session_id": session_id,
        "phone": phone,
    }
    if name:
        payload["name"] = name

    # PB lê o header como "Authorization: <token>" (sem prefixo "Bearer").
    # Se receber "Bearer xxx" o parse interno não reconhece o token.
    headers: dict = {}
    if user_token:
        headers = pb_headers(user_token)

    try:
        # Se já existe record com esse session_id, atualiza (mantém id e created);
        # senão, cria. Idempotente.
        async with httpx.AsyncClient(timeout=10.0) as client:
            find = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
                params={"filter": f'session_id="{session_id}"', "perPage": 1},
                headers=headers,
            )
            existing = find.json().get("items", [])
            if existing:
                rec_id = existing[0]["id"]
                resp = await client.patch(
                    f"{POCKETBASE_URL}/api/collections/telegram_sessions/records/{rec_id}",
                    json=payload,
                    headers=headers,
                )
            else:
                resp = await client.post(
                    f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
                    json=payload,
                    headers=headers,
                )
        if 200 <= resp.status_code < 300:
            logger.info(f"📝 Conta registrada no PocketBase: {phone}")
        else:
            logger.error(
                f"PB recusou registro de {phone}: {resp.status_code} {resp.text}"
            )
    except Exception as e:
        logger.error(f"Erro ao registrar no PocketBase: {e}")


# -----------------------------------------------------------------------------
# 7. Enviar mensagem (reply do webhook)
# -----------------------------------------------------------------------------
@app.post("/api/send-message")
async def send_message(
    request: SendMessageRequest,
    _user: dict = Depends(verify_pb_auth),
):
    """
    Envia uma mensagem via uma sessão Telegram autenticada.

    Aceita:
    - `chat_id` numérico (int) ou @username (str)
    - `reply_to_message_id` opcional pra responder uma mensagem específica

    Esse é o endpoint que o serviço externo (ex: n8n) chama pra responder
    depois de receber o webhook de uma mensagem recebida. O payload do
    webhook já entrega `chat_id` e `message_id` suficientes pra isso.
    """
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Texto vazio")

    if request.session_id not in active_clients:
        raise HTTPException(status_code=404, detail="Sessão não encontrada ou offline")

    client = active_clients[request.session_id]

    try:
        import time
        kwargs = {}
        if request.reply_to_message_id:
            kwargs["reply_to"] = request.reply_to_message_id

        sent = await client.send_message(request.chat_id, request.text, **kwargs)

        # Marca o message_id como "nosso" pra suprimir o webhook que o
        # handler vai disparar logo em seguida (Telethon emite o evento
        # outgoing sincronamente). Sem isso, gera loop com o receptor
        # do webhook (ex: n8n respondendo às nossas mensagens).
        _RECENTLY_SENT_IDS[sent.id] = time.time()

        return {
            "success": True,
            "message_id": sent.id,
            "chat_id": sent.chat_id,
            "timestamp": sent.date.isoformat(),
            "is_reply": bool(kwargs.get("reply_to")),
        }
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem via {request.session_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Admin / Debug
# =============================================================================

@app.get("/api/admin/sessions")
async def admin_list_sessions(_user: dict = Depends(verify_pb_auth)):
    """
    Lista sessões salvas em /app/sessions/*.json — útil pra debug quando
    `active_sessions=0` no /health. NÃO expõe `session_string` (credencial
    real da conta Telegram). Mostra apenas phone, webhook_url, created_at,
    tamanho do session_string e flag active (se está em active_clients).
    """
    sessions = []
    for session_file in sorted(SESSIONS_DIR.glob("*.session")):
        try:
            data = json.loads(session_file.read_text())
            session_id = session_file.stem
            sessions.append({
                "session_id": session_id,
                "phone": data.get("phone"),
                "webhook_url": data.get("webhook_url"),
                "webhook_enabled": data.get("webhook_enabled", True),
                "created_at": data.get("created_at"),
                "session_string_length": len(data.get("session_string", "")),
                "active": session_id in active_clients,
            })
        except Exception as e:
            sessions.append({
                "session_id": session_file.stem,
                "error": f"falha ao ler: {e}",
            })
    return {
        "sessions_dir": str(SESSIONS_DIR),
        "total": len(sessions),
        "active_count": sum(1 for s in sessions if s.get("active")),
        "sessions": sessions,
    }


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
