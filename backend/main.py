"""
FastAPI Backend - Telegram Account Webhook
Gerencia sessões Telethon e forwards mensagens para webhooks dos clientes
"""

import os
import re
import io
import json
import time
import asyncio
import base64
import logging
import ipaddress
import socket as _socket
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime
from typing import Dict, Optional, Literal
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, AnyHttpUrl
from telethon import TelegramClient
from telethon.events import NewMessage
from telethon.sessions import StringSession
from telethon.tl import types as tl_types
from telethon.tl.types import InputMediaUploadedPhoto

import httpx
from PIL import Image

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
    text: Optional[str] = None
    parse_mode: Literal["plain", "html"] = "plain"
    image_url: Optional[AnyHttpUrl] = None
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
    sender_id = getattr(event, "sender_id", None)
    is_private = getattr(event, "is_private", False)
    sender = getattr(event, "sender", None)
    chat = getattr(event, "chat", None)

    # 1) Sender direto
    if sender:
        u = getattr(sender, "username", None)
        if u:
            return u
        # Log diagnóstico quando sender existe mas username=None
        logger.info(
            f"[sender_username] sender existe mas username=None; "
            f"sender_id={sender_id}, is_private={is_private}, "
            f"sender.first_name={getattr(sender, 'first_name', None)!r}, "
            f"sender.last_name={getattr(sender, 'last_name', None)!r}, "
            f"sender.__dict__.keys()={list(sender.__dict__.keys()) if hasattr(sender, '__dict__') else '?'}"
        )
    else:
        logger.info(
            f"[sender_username] event.sender=None; "
            f"sender_id={sender_id}, is_private={is_private}"
        )

    # 2) Em chat privado, chat É o user — checa essa fonte
    if is_private and chat:
        u = getattr(chat, "username", None)
        if u:
            return u
        # Log diagnóstico
        logger.info(
            f"[sender_username] chat privado mas chat.username=None; "
            f"chat_id={getattr(chat, 'id', None)}, "
            f"chat.first_name={getattr(chat, 'first_name', None)!r}, "
            f"chat.__dict__.keys()={list(chat.__dict__.keys()) if hasattr(chat, '__dict__') else '?'}"
        )

    # 3) Fallback: busca via API do Telegram
    client = getattr(event, "client", None)
    if sender_id and client:
        try:
            full = await client.get_entity(sender_id)
            if full:
                u = getattr(full, "username", None)
                if u:
                    return u
                logger.info(
                    f"[sender_username] get_entity OK mas username=None; "
                    f"sender_id={sender_id}, "
                    f"first_name={getattr(full, 'first_name', None)!r}, "
                    f"__dict__.keys()={list(full.__dict__.keys()) if hasattr(full, '__dict__') else '?'}"
                )
        except Exception as e:
            logger.info(f"sender_username fallback fetch falhou: {e}")

    return ""


def _user_to_dict(user) -> dict | None:
    """Extrai info pública de um Telethon User em dict limpo.

    Não expõe access_hash (interno, sensível) nem campos binários
    (photo). Todos os campos são opcionais — Telethon pode entregar
    User object parcial se o cache tá frio.
    """
    if not user:
        return None
    return {
        "id": getattr(user, "id", None),
        "first_name": getattr(user, "first_name", None) or "",
        "last_name": getattr(user, "last_name", None) or "",
        "username": getattr(user, "username", None) or "",
        "phone": getattr(user, "phone", None) or "",
        "is_bot": bool(getattr(user, "bot", False)),
        "is_verified": bool(getattr(user, "verified", False)),
        "is_premium": bool(getattr(user, "premium", False)),
        "is_scam": bool(getattr(user, "scam", False)),
        "is_fake": bool(getattr(user, "fake", False)),
        "is_contact": bool(getattr(user, "contact", False)),
        "is_mutual_contact": bool(getattr(user, "mutual_contact", False)),
        "lang_code": getattr(user, "lang_code", None) or "",
    }


def _classify_chat_type_from_entity(chat) -> str:
    """Classifica o tipo de chat a partir da entidade (User/Chat/Channel)."""
    # User → privado
    if hasattr(chat, "first_name") and not hasattr(chat, "title"):
        return "private"
    # Channel (supergroup ou canal broadcast)
    if hasattr(chat, "broadcast"):
        if getattr(chat, "broadcast", False):
            return "channel"
        if getattr(chat, "megagroup", False):
            return "supergroup"
    # Chat (grupo legacy)
    if hasattr(chat, "title"):
        return "group"
    return "unknown"


def _chat_to_dict(chat) -> dict | None:
    """Extrai info do chat (User/Chat/Channel) em dict limpo.

    Funciona pros 3 tipos de entidade do Telethon:
    - User (chat privado): tem first_name/last_name, NÃO tem title
    - Chat (grupo legacy): tem title
    - Channel (supergroup ou canal): tem title, megagroup, broadcast

    `title` é resolvido com fallback: title → "Primeiro Último" (se for User)
    """
    if not chat:
        return None

    # Resolve um "title" sensato independente do tipo de entidade
    title = getattr(chat, "title", None) or ""
    if not title:
        # Provavelmente é User (chat privado)
        first = getattr(chat, "first_name", None) or ""
        last = getattr(chat, "last_name", None) or ""
        title = (f"{first} {last}").strip()

    return {
        "id": getattr(chat, "id", None),
        "type": _classify_chat_type_from_entity(chat),
        "title": title,
        "username": getattr(chat, "username", None) or "",
        "is_verified": bool(getattr(chat, "verified", False)),
        "is_creator": bool(getattr(chat, "creator", False)),
        "participants_count": getattr(chat, "participants_count", None),
        "about": getattr(chat, "about", None) or "",
        "has_protected_content": bool(getattr(chat, "has_protected_content", False)),
    }


async def _self_user_dict(event) -> dict | None:
    """Info da própria conta Telegram que recebeu/mandou a mensagem.

    `client.get_me()` é cacheado internamente pelo Telethon — chamadas
    repetidas não fazem round-trip pro Telegram.
    """
    client = getattr(event, "client", None)
    if not client:
        return None
    try:
        me = await client.get_me()
        return _user_to_dict(me)
    except Exception as e:
        logger.info(f"get_me() falhou: {e}")
        return None


async def _sender_full_dict(event) -> dict | None:
    """User object completo do sender (com fallback assíncrono se preciso).

    Retorna None se não for um user (canal/grupo, sem first_name).
    """
    sender = getattr(event, "sender", None)
    if sender:
        d = _user_to_dict(sender)
        if d:
            return d

    # Fallback: get_entity
    sender_id = getattr(event, "sender_id", None)
    client = getattr(event, "client", None)
    if sender_id and client:
        try:
            full = await client.get_entity(sender_id)
            if full:
                d = _user_to_dict(full)
                if d:
                    return d
        except Exception as e:
            logger.info(f"_sender_full_dict fallback fetch falhou: {e}")
    return None


async def _chat_full_dict(event) -> dict | None:
    """Chat/receiver object completo (User, Chat ou Channel).

    Fallback chain (retorna o primeiro que der):
    1) `event.chat` (cache do Telethon; pode vir None em outgoing pra
       user novo que o cliente nunca viu)
    2) `client.get_entity(event.chat_id)` — busca o peer via API.
       Resolvido internamente pelo Telethon, sem custo de round-trip
       se o peer já tá em cache.
    3) Se ambos falharem, retorna None.
    """
    chat = getattr(event, "chat", None)
    if chat:
        return _chat_to_dict(chat)

    client = getattr(event, "client", None)
    chat_id = getattr(event, "chat_id", None)
    if client and chat_id is not None:
        try:
            full = await client.get_entity(chat_id)
            if full:
                return _chat_to_dict(full)
        except Exception as e:
            logger.info(f"_chat_full_dict fallback fetch falhou: {e}")
    return None


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

        # 2b) Objetos Telethon enriquecidos (sender, chat, self).
        # Tira `self_full` ANTES do direction check pq ele é usado no fallback
        # de is_outgoing (ver abaixo).
        sender_full = await _sender_full_dict(event)
        chat_full = await _chat_full_dict(event)
        self_full = await _self_user_dict(event)

        # 2) Extrai metadados da mensagem
        # sender_name e chat_title são resolvidos a partir dos dicts já
        # populados (com fallback de get_entity) — mais robusto que os
        # helpers legados `_sender_name` e `_chat_title`, que falham
        # quando o cache do Telethon tá frio (comum em outgoing message
        # pra user novo).
        sender_name = ""
        if sender_full:
            first = sender_full.get("first_name") or ""
            last = sender_full.get("last_name") or ""
            sender_name = f"{first} {last}".strip()
        sender_username = (sender_full or {}).get("username") or ""
        chat_title = (chat_full or {}).get("title") or ""

        # Detecção de direction COM FALLBACK.
        # O `event.outgoing` do Telethon falha em alguns cenários:
        # - Mensagem enviada pelo user via Telegram app/desktop (outro
        #   client) — Telethon recebe como notification, `outgoing` é False
        #   mas `from_id` é o nosso próprio user_id
        # - Sincronização de mensagens históricas
        # - Echo de mensagem recém-enviada
        # Fallback: se `from.id == session.user.id`, é outgoing.
        is_outgoing_telethon = bool(getattr(event, "outgoing", False))
        self_id = (self_full or {}).get("id")
        is_outgoing_self = bool(
            self_id is not None
            and event.sender_id is not None
            and int(event.sender_id) == int(self_id)
        )
        is_outgoing = is_outgoing_telethon or is_outgoing_self
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
        # Anti-loop + dedupe: se a mensagem foi enviada por NÓS mesmos
        # via /api/send-message nos últimos 10s, suprime o POST pros
        # webhooks E o INSERT em `telegram_messages` (o INSERT é feito
        # direto pelo endpoint pra garantir que aparece na página
        # mesmo quando o handler do Telethon não dispara o evento
        # outgoing — cenário comum após boot ou chat novo).
        skip_everything = _is_recently_sent(event.id)
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

            # Anti-loop: pular o POST (o audit INSERT é responsabilidade
            # do endpoint /api/send-message; aqui só evita duplicar).
            if skip_everything:
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
                    "user": self_full,  # Info da nossa própria conta Telegram
                },
                "from": sender_full,  # Quem mandou (User object completo ou None)
                "chat": chat_full,    # Onde a msg chegou (User/Chat/Channel object)
                "message": {
                    # Campos legados (mantidos pra não quebrar consumers existentes)
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
                    "reply_to_msg_id": getattr(
                        getattr(event, "reply_to", None) or {}, "reply_to_msg_id", None
                    ) or getattr(getattr(event, "message", None) or {}, "reply_to_msg_id", None),
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
        #
        # Se a mensagem foi enviada por NÓS mesmos via /api/send-message
        # (skip_everything == True), o INSERT já foi feito direto pelo
        # endpoint — pula aqui pra não duplicar.
        if not skip_everything:
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
    enviadas pela própria conta pelo celular/desktop/web Telegram). O
    payload inclui `outgoing: bool` pra o consumidor filtrar como quiser.

    Mensagens enviadas via nosso próprio /api/send-message são
    detectadas via `_is_recently_sent(event.id)` (cache setado pelo
    endpoint logo após o send_message retornar). Nesse caso, o
    `handle_new_message` SUPRIME tanto o POST pros webhooks quanto o
    INSERT em `telegram_messages` — o INSERT é feito direto pelo
    endpoint pra garantir que aparece na UI mesmo quando o Telethon
    não dispara o evento outgoing (comum após boot ou pra chat novo).

    NOTA: precisa ser `def` (não `async def`) porque não há `await`
    dentro. Se fosse `async def` chamado sem `await`, retornaria uma
    coroutine não-awaitada e o `@client.on(...)` nunca seria aplicado.
    """
    @client.on(NewMessage())
    async def handler(event):
        await handle_new_message(event, session_id)
    logger.info(f"📨 Handler NewMessage registrado para {session_id}")


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
async def delete_session(
    session_id: str,
    _user: dict = Depends(verify_pb_auth),
    user_token: str = Depends(get_user_token),
):
    """Remove uma sessão inteira: cliente ativo, arquivo em disco e
    record no PocketBase.

    O DELETE no PB é o que importa pra integridade: as relations
    `telegram_webhooks.session` e `telegram_messages.session` são
    `cascadeDelete = true`, então apagar o record da sessão arrasta os
    webhooks e TODO o histórico de mensagens junto.

    Sem isso o PB acumulava sessões zumbis: `list_sessions` monta a
    lista a partir dos ARQUIVOS em disco (`load_sessions()`), não do PB
    — então a conta sumia da UI, mas o record, os webhooks e as
    mensagens ficavam no banco para sempre.
    """
    # Desconecta cliente ativo
    if session_id in active_clients:
        await active_clients[session_id].disconnect()
        del active_clients[session_id]

    # Remove arquivo (fonte de verdade da credencial)
    delete_session_file(session_id)

    # Remove o record no PB (cascade de webhooks + mensagens)
    deleted_in_pb = await _delete_session_record_pb(session_id, user_token)
    if not deleted_in_pb:
        logger.warning(
            f"⚠️ Sessão {session_id} removida do disco mas o record no PB "
            f"não foi deletado — sobraram mensagens/webhooks órfãos"
        )

    return {"success": True, "deleted_pb_record": deleted_in_pb}


async def _delete_session_record_pb(session_id: str, user_token: str) -> bool:
    """Apaga o record de `telegram_sessions` no PB (cascade de webhooks
    + mensagens).
    
    Idempotente: se o record não existir mais (404) retorna False sem
    estourar erro — o objetivo é o banco limpo, não o status HTTP.
    """
    pb_id = await _resolve_pb_session_id(session_id, user_token)
    if not pb_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.delete(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records/{pb_id}",
                headers=pb_headers(user_token),
            )
        if r.status_code == 404:
            return False
        if r.status_code >= 300:
            logger.warning(
                f"PB recusou DELETE da sessão {session_id}: "
                f"{r.status_code} {r.text[:200]}"
            )
            return False
        logger.info(
            f"🗑️ Sessão removida do PB (cascade webhooks+mensagens): {session_id}"
        )
        return True
    except Exception as e:
        logger.warning(f"Falha ao remover sessão {session_id} do PB: {e}")
        return False


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
# Subset HTML que o Telegram aceita nativamente (mesmo do Bot API). Validar
# ANTES de mandar pro Telethon dá mensagem de erro mais clara que deixar
# o cliente estourar com `MsgStyleParseError` genérico.
_ALLOWED_HTML_TAGS = {
    "b", "strong", "i", "em", "u", "s", "strike", "del",
    "code", "pre", "a",
}
_ALLOWED_HTML_ATTRS: Dict[str, set] = {"a": {"href"}}
_HTML_TAG_RE = re.compile(
    r"</?\s*([a-zA-Z][a-zA-Z0-9]*)\b([^>]*)>", re.DOTALL
)
_HTML_ATTR_RE = re.compile(r'([a-zA-Z][a-zA-Z0-9-]*)\s*=\s*"([^"]*)"')


def _validate_html_subset(text: str) -> None:
    """Levanta ValueError se houver tag/atributo fora do subset do Telegram."""
    for m in _HTML_TAG_RE.finditer(text):
        tag = m.group(1).lower()
        if tag not in _ALLOWED_HTML_TAGS:
            raise ValueError(f"tag HTML não permitida: <{tag}>")
        attrs_str = m.group(2)
        for am in _HTML_ATTR_RE.finditer(attrs_str):
            attr_name = am.group(1).lower()
            allowed = _ALLOWED_HTML_ATTRS.get(tag, set())
            if attr_name not in allowed:
                raise ValueError(
                    f"atributo não permitido: {attr_name} em <{tag}>"
                )


def _validate_image_url(url: str) -> None:
    """Bloqueia SSRF: scheme inválido + host que resolve pra IP privado/loopback.

    Resolve o host via getaddrinfo e checa cada IP retornado contra ranges
    privados/loopback/link-local/multicast/reservados. Não é à prova de
    DNS rebinding (resolvemos 1x, Telethon baixa depois), mas combinado
    com auth obrigatória no endpoint reduz a superfície de ataque.
    """
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        raise ValueError(f"scheme inválido: {p.scheme}")
    host = p.hostname
    if not host:
        raise ValueError("host vazio")
    try:
        infos = _socket.getaddrinfo(host, None)
    except _socket.gaierror as e:
        raise ValueError(f"DNS falhou: {e}")
    for info in infos:
        ip = info[4][0]
        ip_obj = ipaddress.ip_address(ip)
        if (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
        ):
            raise ValueError(f"host resolve para IP bloqueado: {ip}")


# Telegram auto-classifica WebP como sticker (mesmo que o usuário queira
# uma foto comum). Pra forçar como photo, baixamos o arquivo, convertemos
# WebP→JPEG (ou passamos JPEG/PNG direto) e fazemos upload via
# InputMediaUploadedPhoto — que o servidor Telegram trata como foto
# inline, sem análise de sticker.
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB (limite do Telegram pra foto)
_DOWNLOAD_TIMEOUT_S = 30.0


async def _download_and_prepare_image(url: str) -> bytes:
    """Baixa a imagem, valida tamanho/formato, converte WebP→JPEG se preciso.

    Retorna os bytes prontos pra upload via InputMediaUploadedPhoto. JPEG e
    PNG passam direto. WebP é convertido pra JPEG (Pillow). Outros formatos
    ou falha de decode levantam HTTPException 400.
    """
    try:
        async with httpx.AsyncClient(
            timeout=_DOWNLOAD_TIMEOUT_S, follow_redirects=True
        ) as http:
            resp = await http.get(url)
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=400, detail=f"falha ao baixar imagem: {e}"
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"URL retornou status {resp.status_code}",
        )

    raw = resp.content
    if len(raw) > _MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"imagem maior que {_MAX_IMAGE_BYTES // (1024*1024)} MB",
        )

    try:
        img = Image.open(io.BytesIO(raw))
        img_format = (img.format or "").upper()
        img.load()  # força decode pra falhar cedo em bytes inválidos
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"arquivo não é uma imagem válida: {e}"
        )

    # JPEG/PNG: passa direto. Outros (incluindo WebP): converte pra JPEG.
    if img_format in ("JPEG", "PNG"):
        return raw

    if img.mode in ("RGBA", "LA", "P"):
        # JPEG não suporta alpha. Compor sobre fundo branco.
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(
            img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None
        )
        img = background
    else:
        img = img.convert("RGB")

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=92, optimize=True)
    return out.getvalue()


async def _audit_outgoing_message(
    client: TelegramClient,
    sent,
    session_id: str,
    text: str,
    has_image: bool,
) -> None:
    """INSERT em `telegram_messages` pra mensagem enviada via /api/send-message.

    Garante que a mensagem aparece na página de Mensagens mesmo quando
    o handler `NewMessage` do Telethon NÃO dispara pra outgoing (cenário
    comum após boot, restart, ou quando o chat não tem entity em cache
    ainda — Telethon só dispara `NewMessage` outgoing pra chats já
    conhecidos e em momentos em que o `updates` handler tá ativo).
    Se o handler disparar depois, ele detecta via `_is_recently_sent()`
    e pula o próprio INSERT — sem duplicação.

    Fluxo:
    1) Garante `_PB_SERVICE_TOKEN` (lazy refresh + auto-refresh).
    2) Resolve `pb_id` da sessão (1 GET) — ancora a mensagem na sessão.
    3) Resolve peer info (chat_type/chat_title) via `client.get_entity`.
       Usa `sent.chat_id` (já normalizado pelo Telethon) — cache hit em
       chats conhecidos.
    4) Resolve self user (sender_id/username) via `client.get_me()`.
       Telethon cacheia internamente; sem round-trip repetido.
    5) POST em `telegram_messages` com direction="outgoing". O `text`
       é o caption quando foi foto, ou o body puro quando foi texto.

    Falhas em qualquer passo são re-levantadas (RuntimeError) — o caller
    decide se swallow (no /api/send-message: sim, a entrega pro Telegram
    já foi feita e perder o audit é recoverable, só perdemos a entrada
    na página de Mensagens).
    """
    await _ensure_pb_service_token()
    headers = pb_service_headers()

    # 2) Lookup do pb_id da sessão
    async with httpx.AsyncClient(timeout=10.0) as http:
        r = await http.get(
            f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
            params={"filter": f'session_id="{session_id}"', "perPage": 1},
            headers=headers,
        )
    if r.status_code != 200:
        raise RuntimeError(
            f"PB lookup sessão {session_id} falhou: {r.status_code}"
        )
    items = r.json().get("items", [])
    if not items:
        raise RuntimeError(
            f"sessão {session_id} não cadastrada no PB (audit sem anchor)"
        )
    pb_session_id = items[0]["id"]

    # 3) Resolve peer. `sent.chat_id` é int já normalizado pelo Telethon
    # (negativo pra groups/channels). Usa-o pra hit no cache de entity.
    try:
        entity = await client.get_entity(sent.chat_id)
    except Exception as e:
        logger.info(
            f"_audit_outgoing_message: get_entity({sent.chat_id}) falhou: {e}"
        )
        entity = None
    if entity:
        chat_type = _classify_chat_type_from_entity(entity)
        chat_title = getattr(entity, "title", None) or ""
        if not chat_title:
            chat_title = (
                f"{getattr(entity, 'first_name', '') or ''} "
                f"{getattr(entity, 'last_name', '') or ''}"
            ).strip()
    else:
        chat_type = "unknown"
        chat_title = ""

    # 4) Self user. `get_me()` é cacheado internamente — chamar aqui é
    # barato mesmo dentro do hot path.
    try:
        me = await client.get_me()
    except Exception as e:
        logger.info(f"_audit_outgoing_message: get_me() falhou: {e}")
        me = None
    if me:
        sender_id = int(getattr(me, "id", 0) or 0)
        sender_name = (
            f"{getattr(me, 'first_name', '') or ''} "
            f"{getattr(me, 'last_name', '') or ''}"
        ).strip()
        if not sender_name:
            sender_name = getattr(me, "username", None) or ""
        sender_username = getattr(me, "username", None) or ""
    else:
        sender_id = 0
        sender_name = ""
        sender_username = ""

    # 5) INSERT
    payload = {
        "session": pb_session_id,
        "chat_id": int(sent.chat_id or 0),
        "chat_type": chat_type,
        "chat_title": chat_title,
        "direction": "outgoing",
        "sender_id": sender_id,
        "sender_name": sender_name,
        "sender_username": sender_username,
        "text": text,
    }
    async with httpx.AsyncClient(timeout=10.0) as http:
        r = await http.post(
            f"{POCKETBASE_URL}/api/collections/telegram_messages/records",
            json=payload,
            headers=headers,
        )
    if r.status_code >= 300:
        raise RuntimeError(
            f"PB recusou INSERT audit outgoing: {r.status_code} {r.text[:200]}"
        )
    logger.info(
        f"📝 audit outgoing INSERT: msg={sent.id} chat={sent.chat_id} "
        f"session={session_id} text_len={len(text or '')}"
    )


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
    - `parse_mode` opcional: "plain" (default) ou "html" (subset Telegram)
    - `image_url` opcional: URL http/https pública; vira caption se combinado
      com `text` (também com `parse_mode` aplicável).

    Esse é o endpoint que o serviço externo (ex: n8n) chama pra responder
    depois de receber o webhook de uma mensagem recebida. O payload do
    webhook já entrega `chat_id` e `message_id` suficientes pra isso.
    """
    has_text = bool(request.text and request.text.strip())
    has_image = bool(request.image_url)
    if not has_text and not has_image:
        raise HTTPException(
            status_code=400, detail="Informe text ou image_url"
        )

    if request.session_id not in active_clients:
        raise HTTPException(
            status_code=404, detail="Sessão não encontrada ou offline"
        )

    client = active_clients[request.session_id]

    # parse_mode='html' só faz sentido com texto. Validar subset aqui dá
    # mensagem mais clara que deixar o Telethon estourar depois.
    parse_mode_arg: Optional[str] = None
    if request.parse_mode == "html" and has_text:
        try:
            _validate_html_subset(request.text)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"HTML inválido: {e}")
        parse_mode_arg = "html"

    # URL SSRF: scheme http/https + host não-privado
    if has_image:
        try:
            _validate_image_url(str(request.image_url))
        except ValueError as e:
            raise HTTPException(
                status_code=400, detail=f"image_url inválida: {e}"
            )

    # kwargs comuns (reply_to aplica a texto E foto)
    common_kwargs: dict = {}
    if request.reply_to_message_id:
        common_kwargs["reply_to"] = request.reply_to_message_id

    try:
        if has_image:
            # Baixar e normalizar a imagem (WebP→JPEG) antes do upload.
            # Se passar URL cru pra send_file, o Telegram auto-classifica
            # WebP como sticker. Pré-processar garante que vire foto.
            image_bytes = await _download_and_prepare_image(
                str(request.image_url)
            )
            # Upload via InputFile e wrap em InputMediaUploadedPhoto.
            # O Telethon trata isso como photo (InputMediaUploadedPhoto)
            # em vez de deixar o servidor decidir baseado no formato.
            uploaded = await client.upload_file(
                image_bytes, file_name="image.jpg"
            )
            media = InputMediaUploadedPhoto(
                file=uploaded, stickers=None, ttl_seconds=None
            )
            sent = await client.send_file(
                request.chat_id,
                media,
                caption=request.text if has_text else "",
                parse_mode=parse_mode_arg,
                **common_kwargs,
            )
        else:
            sent = await client.send_message(
                request.chat_id,
                request.text,
                parse_mode=parse_mode_arg,
                **common_kwargs,
            )

        # Marca o message_id como "nosso" pra suprimir o webhook que o
        # handler vai disparar logo em seguida (Telethon emite o evento
        # outgoing sincronamente). Sem isso, gera loop com o receptor
        # do webhook (ex: n8n respondendo às nossas mensagens).
        _RECENTLY_SENT_IDS[sent.id] = time.time()

        # INSERT em `telegram_messages` direto do endpoint — garante que
        # a mensagem aparece na UI mesmo quando o Telethon NÃO dispara
        # `NewMessage` pra outgoing (comum após restart, em chat novo
        # onde o cache tá frio, ou em versões onde outgoing vem só via
        # updateMessage em vez de NewMessage). O handler do Telethon,
        # se disparar o evento, detecta via `_is_recently_sent()` e
        # pula o próprio INSERT — sem duplicação.
        #
        # Falha aqui NÃO quebra a response do send_message — o user
        # já recebeu o OK do Telegram; só perdemos o audit log. Loga
        # warning pra investigação.
        try:
            await _audit_outgoing_message(
                client=client,
                sent=sent,
                session_id=request.session_id,
                text=request.text if has_text else "",
                has_image=has_image,
            )
        except Exception as e:
            logger.warning(
                f"⚠️ audit INSERT falhou pra msg #{sent.id} (sessão "
                f"{request.session_id}): {e} — msg já foi entregue ao "
                f"Telegram, só não vai aparecer na página de mensagens"
            )

        return {
            "success": True,
            "message_id": sent.id,
            "chat_id": sent.chat_id,
            "timestamp": sent.date.isoformat(),
            "is_reply": bool(common_kwargs.get("reply_to")),
            "parse_mode": request.parse_mode if has_text else None,
            "has_media": has_image,
            "media_type": "photo" if has_image else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)
        # FloodWait, ChatWriteForbidden, PeerIdInvalid, etc. caem aqui.
        logger.error(f"Erro ao enviar mensagem via {request.session_id}: {msg}")
        raise HTTPException(status_code=400, detail=msg)


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
