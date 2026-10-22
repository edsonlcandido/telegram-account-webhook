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

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, AnyHttpUrl
from telethon import TelegramClient
from telethon.errors import PasswordHashInvalidError, SessionPasswordNeededError
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

# Pairings que JÁ validaram o código e estão esperando a senha de 2FA.
# Chave: `pending_<phone>` (o mesmo session_id do pairing em andamento).
# Existe porque o passo da senha do Telethon é um `sign_in` separado, sem
# o código — sem essa flag o backend não saberia que pode pular direto
# pro passo da senha.
pending_2fa: Dict[str, bool] = {}


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


class IntegrationTokenRequest(BaseModel):
    # Validade do token em SEGUNDOS. Ausente/None cai no default abaixo.
    # NUNCA aceitar `user_id` aqui: o id do usuário vem sempre do JWT já
    # verificado por `verify_pb_auth` — aceitar no body permitiria um usuário
    # comum pedir token de outra conta (escalação de privilégio).
    duration: Optional[int] = None


# ============================================================================
# Token de integração (API key via impersonate do PocketBase)
# ============================================================================

# O endpoint `impersonate` do PB aceita qualquer duração em segundos
# (>= 0). Nós clampamos numa faixa defensável: o piso evita token que expira
# antes do usuário conseguir colar no outro sistema; o teto evita que um token
# vire credencial quase-permanente.
INTEGRATION_TOKEN_MIN_DURATION = 300  # 5 minutos
INTEGRATION_TOKEN_MAX_DURATION = 31_536_000  # 365 dias
INTEGRATION_TOKEN_DEFAULT_DURATION = 2_592_000  # 30 dias


def _clamp_integration_duration(duration: Optional[int]) -> int:
    """Normaliza a duração pedida pra faixa [MIN, MAX]. None/absente = default."""
    if duration is None:
        return INTEGRATION_TOKEN_DEFAULT_DURATION
    return max(
        INTEGRATION_TOKEN_MIN_DURATION,
        min(int(duration), INTEGRATION_TOKEN_MAX_DURATION),
    )


# =============================================================================
# Persistência de Sessões
# =============================================================================

def get_session_file(session_id: str) -> Path:
    """Retorna o caminho do arquivo de sessão"""
    return SESSIONS_DIR / f"{session_id}.session"


def save_session(session_id: str, session_string: str, phone: str, owner_id: str | None = None):
    """Salva apenas a credencial no sistema de arquivos.

    Metadados editáveis (name, webhooks) ficam no PocketBase como source
    of truth — o arquivo é só pra carregar a sessão Telethon de volta no boot.

    `owner_id` é apenas um fallback de diagnóstico/fallback de posse: quem
    manda no dono da sessão é o record `telegram_sessions.owner` no PB.
    """
    session_file = get_session_file(session_id)
    data = {
        "session_string": session_string,
        "phone": phone,
        "created_at": datetime.now().isoformat(),
    }
    if owner_id:
        data["owner_id"] = owner_id
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


# =============================================================================
# Resolução de peer — caso do "primeiro contato"
# =============================================================================
#
# BUG (primeiro contato): quando alguém que NUNCA conversou com a conta
# monitorada manda mensagem, o Telegram entrega o update SEM o objeto
# `User` completo no batch. O Telethon resolve `event.sender`/`event.chat`
# EXCLUSIVAMENTE a partir do dict `entities` que veio naquele update
# (`utils._get_entity_pair` → `entities.get(peer_id)`), então os dois
# ficam `None`.
#
# O fallback `client.get_entity(peer_id)` TAMBÉM falha: sem `access_hash`
# não existe `InputPeerUser` possível, e o único pedido viável
# (`users.getUsers` com access_hash=0) só resolve pra contatos e bots.
#
# SOLUÇÃO: `messages.getDialogs` é a única fonte que devolve o User
# completo (com access_hash) de um peer desconhecido — o dialog é criado
# pelo Telegram no momento em que a mensagem chega. É exatamente a
# estratégia que o próprio Telethon usa em `ChatGetter.get_input_chat()`
# ("the chat may be recent, look in dialogs"). O fetch também popula o
# cache de entidades do Telethon, então depois dele `send_message(chat_id)`
# por ID passa a funcionar (era o segundo lado do bug: a resposta do n8n
# pro contato novo também quebrava).
# =============================================================================

# Quantos dialogs varrer atrás do peer desconhecido. O dialog novo fica
# no topo da lista (ordenada por atividade recente), então o peer é
# encontrado nos primeiros.
_PEER_DIALOG_SCAN_LIMIT = 100

# Cache curto de peers JÁ resolvidos. No chat privado o sender e o chat
# são o mesmo user (sender_id == chat_id) — sem isso, o `iter_dialogs`
# rodaria duas vezes na mesma mensagem.
_PEER_ENTITY_CACHE: Dict[str, tuple] = {}
_PEER_ENTITY_CACHE_TTL = 300.0  # 5 min

# Peers que falharam a resolução recentemente — evita martelar o
# `getDialogs` a cada mensagem do mesmo peer (ex: usuário bloqueado).
_PEER_RESOLVE_FAILED: Dict[str, float] = {}
_PEER_RESOLVE_FAILED_TTL = 60.0


def _peer_cache_key(client, peer_id: int) -> str:
    """Chave de cache por (client, peer) — `id(client)` isola sessões."""
    return f"{id(client)}:{peer_id}"


async def _resolve_peer_entity(client, peer_id: int):
    """Resolve um peer (user/chat/channel) na entidade completa do Telethon.

    Retorna `tl.types.User` / `Chat` / `Channel`, ou None se não conseguir.

    Cadeia:
    1) `client.get_entity(peer_id)` — cache em memória → session (sqlite).
       Cobre todo peer já conhecido (contato, grupo, conversa antiga).
    2) `client.iter_dialogs(...)` — varre os dialogs recentes atrás do peer.
       É o que resolve o caso de PRIMEIRO CONTATO, porque o Telegram
       devolve o `access_hash` do User junto com o dialog.
    """
    if not peer_id:
        return None

    cache_key = _peer_cache_key(client, peer_id)
    now = time.time()

    # Cache curto: o mesmo peer pode ser pedido duas vezes na mesma
    # mensagem (sender + chat são o mesmo user no chat privado).
    cached = _PEER_ENTITY_CACHE.get(cache_key)
    if cached and (now - cached[1]) < _PEER_ENTITY_CACHE_TTL:
        return cached[0]

    # Cooldown: peer que já falhou não é reprocessado agora.
    failed_at = _PEER_RESOLVE_FAILED.get(cache_key)
    if failed_at is not None and (now - failed_at) < _PEER_RESOLVE_FAILED_TTL:
        return None

    # 1) Cache do Telethon (memória + sqlite da session).
    try:
        entity = await client.get_entity(peer_id)
        if entity is not None:
            _PEER_ENTITY_CACHE[cache_key] = (entity, now)
            return entity
    except Exception as e:
        logger.info(
            f"[resolve_peer] peer {peer_id} não está no cache do Telethon "
            f"({type(e).__name__}) — indo procurar nos dialogs"
        )

    # 2) Dialogs — peer de primeiro contato aparece aqui (com access_hash).
    try:
        async for dialog in client.iter_dialogs(_PEER_DIALOG_SCAN_LIMIT):
            if dialog.id != peer_id:
                continue
            entity = dialog.entity
            if entity is None:
                continue
            logger.info(
                f"✅ Peer {peer_id} resolvido via dialogs (primeiro contato) "
                f"— tipo={type(entity).__name__}"
            )
            _PEER_ENTITY_CACHE[cache_key] = (entity, now)
            return entity
    except Exception as e:
        logger.warning(
            f"[resolve_peer] iter_dialogs falhou pro peer {peer_id}: "
            f"{type(e).__name__}: {e}"
        )

    # 3) Último recurso: o `iter_dialogs` pode ter populado o cache do
    #    Telethon com o access_hash mesmo sem achar o dialog.
    try:
        entity = await client.get_entity(peer_id)
        if entity is not None:
            _PEER_ENTITY_CACHE[cache_key] = (entity, now)
            return entity
    except Exception:
        pass

    logger.warning(f"[resolve_peer] peer {peer_id} não resolvido")
    _PEER_RESOLVE_FAILED[cache_key] = now

    # Limpa entradas velhas dos dois caches.
    for key, (_entity, ts) in list(_PEER_ENTITY_CACHE.items()):
        if now - ts > _PEER_ENTITY_CACHE_TTL:
            _PEER_ENTITY_CACHE.pop(key, None)
    for key, ts in list(_PEER_RESOLVE_FAILED.items()):
        if now - ts > _PEER_RESOLVE_FAILED_TTL:
            _PEER_RESOLVE_FAILED.pop(key, None)

    return None


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

    # Fallback: resolução via cache + dialogs (cobre peer de primeiro
    # contato — `get_entity` sozinho não basta, precisa do `iter_dialogs`).
    sender_id = getattr(event, "sender_id", None)
    client = getattr(event, "client", None)
    if sender_id and client:
        full = await _resolve_peer_entity(client, sender_id)
        if full is not None:
            d = _user_to_dict(full)
            if d:
                return d
    return None


async def _chat_full_dict(event) -> dict | None:
    """Chat/receiver object completo (User, Chat ou Channel).

    Fallback chain (retorna o primeiro que der):
    1) `event.chat` (cache do Telethon; pode vir None pra user de
       primeiro contato).
    2) `_resolve_peer_entity` — combina cache + `iter_dialogs`. O
       `iter_dialogs` é o que resolve o caso de PRIMEIRO CONTATO (o
       `get_entity` direto não basta, precisa do access_hash que só o
       `getDialogs` devolve).
    """
    chat = getattr(event, "chat", None)
    if chat:
        return _chat_to_dict(chat)

    client = getattr(event, "client", None)
    chat_id = getattr(event, "chat_id", None)
    if client and chat_id is not None:
        full = await _resolve_peer_entity(client, chat_id)
        if full is not None:
            return _chat_to_dict(full)
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
                            # ID da mensagem no Telegram (único por chat).
                            # Diferente do `id` do record no PB.
                            "telegram_message_id": int(event.id),
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

    # Valida que o service token é de SUPERUSER. Com as rules de escrita
    # trancadas (createRule/updateRule/deleteRule = null), um token sem
    # privilégio de superuser faz TODAS as escritas falharem.
    await _check_service_token_is_superuser()

    # Log de reconciliação: sessões sem dono (invisíveis pra todo mundo
    # até o admin reatribuir o `owner` no Admin UI do PB).
    await _log_unowned_sessions()

    # Inicializa sessões Telethon
    await initialize_sessions()

    yield

    # Cleanup
    logger.info("👋 FastAPI Shutting down...")
    for session_id, client in list(active_clients.items()):
        # `active_clients` também guarda entradas que NÃO são clients: o
        # `phone_code_hash` (string) e o client pendente do pairing. Só o
        # TelegramClient tem `disconnect()` — sem esse check o shutdown
        # quebrava com AttributeError se o container parasse entre o
        # send-code e o verify-code.
        if not hasattr(client, "disconnect"):
            continue
        try:
            await client.disconnect()
        except Exception as e:
            logger.warning(f"Falha ao desconectar sessão {session_id}: {e}")
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


# NOTA: não existe mais `get_user_token`/`pb_headers` (extrair o JWT cru do
# header pra repassar ao PB). Com o isolamento por dono:
#   - ESCRITAS no PB são sempre com o service token (superuser) — as rules
#     de escrita estão trancadas (create/update/delete = null) e o FastAPI
#     valida o dono antes de escrever;
#   - LEITURAS com o token do usuário não são mais proxyadas pelo backend
#     (o front lê direto do PB, já escopado pelas rules de dono).
# Repassar o token do caller pro PB seria um bypass do isolamento.


# =============================================================================
# Isolamento por usuário (dono da sessão)
# =============================================================================
# O PB é a autoridade de "quem é o dono" da sessão: o campo
# `telegram_sessions.owner` (relation → `users`), criado pela migration
# `1792491708_link_sessions_to_users.js`.
#
# DUAS camadas de proteção:
#
#   1) Rules do PB — protegem o acesso DIRETO do browser às coleções
#      (`telegram_sessions` e `telegram_messages` são lidas no front com o
#      JWT do usuário). Sem elas, o front leria a sessão e o histórico de
#      mensagens de outros usuários.
#
#   2) Checagem explícita AQUI — protege os endpoints da API, que usam o
#      service token (superuser) em algumas operações. Superuser ignora as
#      rules do PB, então sem esta checagem o isolamento seria furado.
#
# Transição de deploy: o backend entra em produção ANTES da migration (que é
# o que cria o campo `owner`). Enquanto o campo não existir no PB, o
# isolamento não está ativo — os helpers detectam isso (campo ausente no
# record) e mantêm o comportamento permissivo, sem derrubar o app.
# =============================================================================

_ownership_warned = False


def _warn_ownership_inactive() -> None:
    """Avisa UMA VEZ que o isolamento por dono ainda não está no ar."""
    global _ownership_warned
    if not _ownership_warned:
        logger.warning(
            "⚠️ PB ainda sem o campo `owner` em telegram_sessions — "
            "isolamento por usuário INATIVO (aplicou a migration "
            "1792491708_link_sessions_to_users.js?)"
        )
        _ownership_warned = True


async def _get_session_record(pb_id: str) -> dict | None:
    """Record de `telegram_sessions` via service token (superuser).

    Usa o service token de propósito: as rules do PB não valem pra
    superuser, e aqui a gente PRECISA enxergar a sessão de qualquer dono
    pra poder comparar o `owner` com o caller.
    """
    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records/{pb_id}",
                headers=pb_service_headers(),
            )
        if r.status_code == 200:
            return r.json()
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar sessão {pb_id} no PB: {e}")
        return None


async def _resolve_session_record(session_id: str) -> dict | None:
    """Record de `telegram_sessions` pelo `session_id` (string) — service token."""
    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
                params={
                    "filter": f'session_id="{session_id}"',
                    "perPage": 1,
                    "fields": "id,session_id,name,phone,owner",
                },
                headers=pb_service_headers(),
            )
        items = r.json().get("items", [])
        return items[0] if items else None
    except Exception as e:
        logger.error(f"Erro resolvendo PB session: {e}")
        raise HTTPException(503, "PocketBase indisponível")


async def _assert_record_owned(record: dict, caller_id: str) -> None:
    """404 se o record não for do caller.

    404 (e não 403) de propósito: não revela que a sessão de outra pessoa
    existe. Sessão SEM DONO (`owner` vazio) também é negada — ela só volta
    a funcionar quando o admin reatribui o dono no Admin UI do PB.
    """
    if "owner" not in record:
        # Schema antigo (transição de deploy) → sem isolamento ainda.
        _warn_ownership_inactive()
        return
    if str(record.get("owner") or "") != caller_id:
        raise HTTPException(404, "Sessão não encontrada ou sem permissão")


async def _resolve_owned_session(session_id: str, caller_id: str) -> dict:
    """Record da sessão do caller. 404 se não existir ou for de outro usuário."""
    record = await _resolve_session_record(session_id)
    if not record:
        raise HTTPException(404, "Sessão não encontrada ou sem permissão")
    await _assert_record_owned(record, caller_id)
    return record


async def _assert_session_owned_by_pb_id(pb_id: str, caller_id: str) -> None:
    """Valida o dono de uma sessão pelo `id` do PB (usado pelos webhooks)."""
    record = await _get_session_record(pb_id)
    if not record:
        raise HTTPException(404, "Sessão não encontrada ou sem permissão")
    await _assert_record_owned(record, caller_id)


async def _assert_webhook_owned(webhook_id: str, caller_id: str) -> dict:
    """Busca o webhook e valida o dono (via a sessão dele). 404 se não for do caller."""
    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records/{webhook_id}",
                headers=pb_service_headers(),
            )
        if r.status_code != 200:
            raise HTTPException(404, "Webhook não encontrado")
        webhook = r.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao buscar webhook {webhook_id}: {e}")
        raise HTTPException(404, "Webhook não encontrado")

    session_pb_id = webhook.get("session", "")
    if session_pb_id:
        await _assert_session_owned_by_pb_id(session_pb_id, caller_id)
    return webhook


async def _list_owned_sessions(caller_id: str) -> tuple[Dict[str, dict], bool]:
    """Mapa `session_id` → record das sessões do caller.

    Retorna `(mapa, ownership_ativo)`. Com `ownership_ativo=False` o mapa
    traz TODAS as sessões (comportamento antigo) — transição de deploy ou
    PB fora do ar.
    """
    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
                params={"perPage": 500, "fields": "id,session_id,name,phone,owner"},
                headers=pb_service_headers(),
            )
        items = r.json().get("items", [])
    except Exception as e:
        logger.warning(f"Falha ao buscar sessões no PB: {e}")
        return ({}, False)

    if not items:
        return ({}, True)

    if "owner" not in items[0]:
        # Schema antigo → sem isolamento ainda (comportamento antigo).
        _warn_ownership_inactive()
        return ({s.get("session_id", ""): s for s in items}, False)

    owned: Dict[str, dict] = {}
    for s in items:
        if str(s.get("owner") or "") == caller_id:
            owned[s.get("session_id", "")] = s
    return (owned, True)


async def _check_session_conflict(session_id: str, caller_id: str) -> bool:
    """True se a sessão já pertence a OUTRO usuário (conflito de número).

    Sessão sem dono (`owner` vazio) NÃO é conflito — ela é "adotada" pelo
    primeiro usuário que parear o número (legado em migração manual).
    """
    record = await _resolve_session_record(session_id)
    if not record:
        return False
    if "owner" not in record:
        _warn_ownership_inactive()
        return False
    owner = str(record.get("owner") or "")
    return bool(owner) and owner != caller_id


async def _discard_pending_client(session_id: str, hash_key: str, client) -> None:
    """Desconecta e limpa o client de um pairing que deu conflito de dono.

    Sem isso, o client fica em `active_clients` (e o Telegram conta
    pareada) mesmo depois do 409 — vazamento de client órfão.
    """
    active_clients.pop(session_id, None)
    active_clients.pop(hash_key, None)
    pending_2fa.pop(session_id, None)
    try:
        await client.disconnect()
    except Exception as e:
        logger.warning(f"Falha ao desconectar client pendente {session_id}: {e}")


async def _resolve_session_id_by_pb_id(pb_id: str) -> str | None:
    """Resolve o `id` do PB pro `session_id` (string) via service token."""
    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records/{pb_id}",
                params={"fields": "session_id"},
                headers=pb_service_headers(),
            )
        if r.status_code == 200:
            return r.json().get("session_id")
    except Exception as e:
        logger.error(f"Erro resolvendo session_id: {e}")
    return None


async def _check_service_token_is_superuser() -> None:
    """Log-only: avisa se o service token NÃO for superuser.

    Com as rules de escrita trancadas (create/update/delete = null), um
    service token sem privilégio de superuser faz TODAS as escritas
    falharem (pairing de conta e audit log de mensagens).
    """
    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/_superusers/records",
                params={"perPage": 1},
                headers=pb_service_headers(),
            )
        if r.status_code == 200:
            logger.info("✅ service token do PB é superuser (escritas liberadas)")
        else:
            logger.error(
                "❌ service token do PB NÃO é superuser (HTTP %s) — as escritas "
                "vão falhar (createRule/updateRule/deleteRule = null). Defina "
                "POCKETBASE_SERVICE_TOKEN de um superuser ou use "
                "POCKETBASE_ADMIN_EMAIL + PASSWORD.",
                r.status_code,
            )
    except Exception as e:
        logger.warning(f"Não foi possível validar se o service token é superuser: {e}")


async def _log_unowned_sessions() -> None:
    """Log de reconciliação: sessões sem dono (reatribuição manual no Admin UI).

    Sessão sem dono fica INVISÍVEL pra todo mundo (as rules negam) até o
    admin preencher o campo `owner` no Admin UI do PB. O forwarding dos
    webhooks não depende de dono — a conta continua ativa.
    """
    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
                params={"perPage": 500, "fields": "id,session_id,name,owner"},
                headers=pb_service_headers(),
            )
        items = r.json().get("items", [])
    except Exception as e:
        logger.warning(f"Falha ao buscar sessões para reconciliação: {e}")
        return

    if not items:
        return
    if "owner" not in items[0]:
        _warn_ownership_inactive()
        return

    unowned = [
        s.get("session_id", "")
        for s in items
        if not str(s.get("owner") or "")
    ]
    if unowned:
        logger.warning(
            "🧭 %d sessão(ões) SEM DONO (invisíveis pra todo mundo — "
            "reatribua o campo `owner` no Admin UI do PB): %s",
            len(unowned),
            ", ".join(unowned),
        )


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
        # Código novo => recomeça o estado de 2FA
        pending_2fa.pop(session_id, None)

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
    body: VerifyCodeRequest,
    _user: dict = Depends(verify_pb_auth),
):
    """
    Verifica o código, cria sessão persistente e inicia escuta.

    A posse da sessão é validada ANTES de gravar qualquer coisa: se o
    número já estiver vinculado a outro usuário, a resposta é 409 e nada
    é criado (nem arquivo, nem client ativo, nem record no PB).
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
        # Verifica código (e senha de 2FA, se a conta exigir)
        try:
            if body.password and pending_2fa.get(session_id):
                # CONTINUAÇÃO do 2FA: o código JÁ foi validado na
                # tentativa anterior (a sessão ficou pendente esperando a
                # senha). O passo da senha é um `sign_in` SEPARADO, SEM o
                # código.
                #
                # Por que separado: no Telethon 1.36 o `sign_in` é um
                # if/elif — com `code` E `password` juntos o ramo
                # `elif code:` vence, a senha é IGNORADA e o Telegram
                # responde SessionPasswordNeededError de novo (a senha
                # nunca chega a ser checada).
                await client.sign_in(
                    body.phone_number,
                    password=body.password,
                )
            else:
                await client.sign_in(
                    body.phone_number,
                    code=body.code,
                    phone_code_hash=phone_code_hash
                )
        except SessionPasswordNeededError:
            # Conta com verificação em duas etapas (2FA): o Telegram exige a
            # SENHA da conta, não só o código do SMS/app.
            #
            # O client pendente e o `phone_code_hash` ficam VIVOS de propósito
            # (não descarta nada aqui): a próxima chamada com a senha completa
            # o login. A flag `pending_2fa` marca que o código já valeu.
            # O front detecta o `error: two_factor_required` e mostra o campo
            # de senha.
            if not body.password:
                pending_2fa[session_id] = True
                logger.info(
                    f"🔐 2FA exigido na verificação de {body.phone_number} — "
                    f"aguardando senha de 2FA"
                )
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error": "two_factor_required",
                        "message": (
                            "Esta conta usa verificação em duas etapas (2FA). "
                            "Informe a senha de 2FA para continuar."
                        ),
                    },
                )
            # O código foi aceito mas a conta exige 2FA e a senha veio
            # junto: completa o login agora com o passo da senha.
            try:
                await client.sign_in(
                    body.phone_number,
                    password=body.password,
                )
            except PasswordHashInvalidError:
                raise HTTPException(
                    status_code=400,
                    detail="Senha de 2FA incorreta. Confira e tente de novo.",
                )
        except PasswordHashInvalidError:
            raise HTTPException(
                status_code=400,
                detail="Senha de 2FA incorreta. Confira e tente de novo.",
            )

        # Salva sessão
        session_string = client.session.save()
        final_session_id = f"account_{body.phone_number.replace('+', '')}"
        caller_id, _ = _auth_user(_user)

        # (1) PRE-CHECK de posse. Feito ANTES de gravar o arquivo: se o
        #     número é de outro usuário, não sobrescreve a credencial
        #     alheia nem deixa client ativo. "Primeiro dono vence".
        if await _check_session_conflict(final_session_id, caller_id):
            await _discard_pending_client(session_id, hash_key, client)
            raise HTTPException(
                status_code=409,
                detail="Esta conta Telegram já está vinculada a outro usuário.",
            )

        # (2) Persiste em arquivo (credencial — name/dono vão pro PB)
        save_session(
            final_session_id,
            session_string,
            body.phone_number,
            owner_id=caller_id,
        )

        # (3) Registra no PocketBase de forma SÍNCRONA. Antes era
        #     background task: a falha nunca chegava ao usuário e a sessão
        #     ficava órfã (sem record no PB = invisível na listagem).
        #     Agora o conflito de dono volta como 409.
        try:
            await register_account_pb(
                final_session_id,
                body.phone_number,
                caller_id,
                body.name,
            )
        except HTTPException:
            # Conflito de dono (ou falha do PB): desfaz tudo pra não
            # deixar sessão órfã no disco.
            delete_session_file(final_session_id)
            await _discard_pending_client(session_id, hash_key, client)
            raise

        # (4) Move cliente para sessão final
        active_clients[final_session_id] = client
        del active_clients[session_id]
        del active_clients[hash_key]
        pending_2fa.pop(session_id, None)

        # Registra handler de novas mensagens — sem isso, webhook nunca dispara
        # em contas criadas via signup (só funciona pra contas carregadas do
        # disco no boot via initialize_sessions → start_client).
        register_message_handler(client, final_session_id)

        return {
            "success": True,
            "session_id": final_session_id,
            "message": "Conta pareada com sucesso!"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------------------------------------------------------
# 3. Webhooks (multi-webhook por sessão, com filtros)
# -----------------------------------------------------------------------------
#
# NOTA: não existe mais "resolver sessão pelo token do usuário" aqui. Com o
# isolamento por dono, a resolução de sessão SEMPRE passa por
# `_resolve_owned_session()` (service token + comparação do `owner`), porque
# as rules de escrita da collection estão trancadas e o FastAPI é o único
# escritor. Resolver pelo token do usuário traria de volta o bypass.


# 3a. Listar webhooks de uma sessão
@app.get("/api/sessions/{session_id}/webhooks")
async def list_session_webhooks(
    session_id: str,
    _user: dict = Depends(verify_pb_auth),
):
    """Webhooks de uma sessão. Só o DONO da sessão enxerga os dele."""
    caller_id, _ = _auth_user(_user)
    session = await _resolve_owned_session(session_id, caller_id)
    pb_id = session.get("id", "")
    if not pb_id:
        return {"webhooks": []}
    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records",
                # Sem `sort=created`: PB 0.40+ rejeita sort nos system fields
                # `created`/`updated` com 400. Como só listamos webhooks de UMA
                # sessão, a ordem de criação não é tão importante — o `id`
                # (gerado pelo PB em ordem cronológica) é suficiente.
                params={"filter": f'session="{pb_id}"', "perPage": 500},
                headers=pb_service_headers(),
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
):
    """Cria um webhook na sessão. Só o DONO da sessão pode criar.

    A escrita usa o service token (superuser) porque as rules de escrita
    da collection estão trancadas (createRule = null): o FastAPI é o único
    escritor e valida o dono da sessão ANTES de escrever. Isso fecha o
    vetor de "anexar webhook na sessão de outro" via chamada direta na
    API do PocketBase.
    """
    caller_id, _ = _auth_user(_user)
    session = await _resolve_owned_session(session_id, caller_id)
    pb_id = session.get("id", "")
    if not pb_id:
        raise HTTPException(404, "Sessão não encontrada no PB")

    # Default name = "Webhook 1", "Webhook 2"... baseado em quantos já existem
    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            cnt_r = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records",
                params={"filter": f'session="{pb_id}"', "perPage": 500, "fields": "id"},
                headers=pb_service_headers(),
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
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records",
                json=payload,
                headers=pb_service_headers(),
            )
        if r.status_code >= 300:
            raise HTTPException(400, f"PB recusou: {r.text}")
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
):
    """Atualiza um webhook. Só o DONO da sessão do webhook pode mexer nele."""
    payload = {k: v for k, v in request.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(400, "Nada pra atualizar")

    caller_id, _ = _auth_user(_user)
    webhook = await _assert_webhook_owned(webhook_id, caller_id)

    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.patch(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records/{webhook_id}",
                json=payload,
                headers=pb_service_headers(),
            )
        if r.status_code >= 300:
            raise HTTPException(400, f"PB recusou: {r.text}")
        result = r.json()
        sid = await _resolve_session_id_by_pb_id(result.get("session", ""))
        if sid:
            result["session_id"] = sid
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
):
    """Remove um webhook. Só o DONO da sessão do webhook pode remover."""
    caller_id, _ = _auth_user(_user)
    webhook = await _assert_webhook_owned(webhook_id, caller_id)

    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.delete(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records/{webhook_id}",
                headers=pb_service_headers(),
            )
        if r.status_code >= 300:
            raise HTTPException(400, f"PB recusou: {r.text}")
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
):
    """Pausa/retoma um webhook. Só o DONO da sessão do webhook pode mexer."""
    caller_id, _ = _auth_user(_user)
    webhook = await _assert_webhook_owned(webhook_id, caller_id)

    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.patch(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records/{webhook_id}",
                json={"enabled": request.enabled},
                headers=pb_service_headers(),
            )
        if r.status_code >= 300:
            raise HTTPException(400, f"PB recusou: {r.text}")
        result = r.json()
        sid = await _resolve_session_id_by_pb_id(result.get("session", ""))
        if sid:
            result["session_id"] = sid
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Erro ao alternar webhook: {e}")


# 3f. Testar webhook (POST simplificado)
@app.post("/api/webhooks/{webhook_id}/test")
async def test_webhook_endpoint(
    webhook_id: str,
    _user: dict = Depends(verify_pb_auth),
):
    """Dispara um POST de teste na URL do webhook. Só o DONO pode testar."""
    caller_id, _ = _auth_user(_user)
    webhook = await _assert_webhook_owned(webhook_id, caller_id)

    try:
        url = webhook.get("url")
        if not url:
            raise HTTPException(400, "Webhook sem URL")

        async with httpx.AsyncClient(timeout=10.0) as client:
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
):
    """Renomeia a sessão. Só o DONO da sessão pode renomear."""
    if request.name is None:
        raise HTTPException(400, "Nada pra atualizar")
    caller_id, _ = _auth_user(_user)
    session = await _resolve_owned_session(session_id, caller_id)
    pb_id = session.get("id", "")
    if not pb_id:
        raise HTTPException(404, "Sessão não encontrada no PB")
    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.patch(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records/{pb_id}",
                json={"name": request.name},
                headers=pb_service_headers(),
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
):
    """Lista as sessões do USUÁRIO.

    A lista é a INTERSEÇÃO de duas fontes:
      - arquivos em disco (`load_sessions()`) → a credencial
      - records `telegram_sessions` do PB cujo `owner` é o caller → o dono

    O PB é a autoridade de posse: sessão sem record (ou sem dono) não
    aparece na lista. Ela volta a aparecer quando o admin reatribui o
    `owner` no Admin UI do PB — sem reiniciar nada.
    """
    caller_id, _ = _auth_user(_user)
    saved = load_sessions()

    owned, ownership_active = await _list_owned_sessions(caller_id)

    if ownership_active:
        visible = [s for s in saved if s.get("session_id") in owned]
    else:
        # Transição de deploy (PB sem o campo `owner`) ou PB fora do ar:
        # mantém o comportamento antigo em vez de mostrar lista vazia.
        logger.warning(
            "list_sessions: isolamento por dono INATIVO — listando todas as sessões"
        )
        visible = saved

    # Cruza com PB pra buscar name + webhook_count em batch.
    # PB não tem JOIN — faço 2 queries globais e cruz em memória (N é pequeno).
    name_by_sid: Dict[str, str] = {}
    pb_id_by_sid: Dict[str, str] = {}
    counts_by_pb_id: Dict[str, int] = {}
    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            wh_resp = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records",
                params={"perPage": 500, "fields": "session"},
                headers=pb_service_headers(),
            )
            for w in wh_resp.json().get("items", []):
                sid = w.get("session", "")
                counts_by_pb_id[sid] = counts_by_pb_id.get(sid, 0) + 1
    except Exception as e:
        logger.warning(f"Falha ao buscar metadados PB pra list_sessions: {e}")

    for sid, rec in owned.items():
        name_by_sid[sid] = rec.get("name", "") or ""
        pb_id_by_sid[sid] = rec.get("id", "")

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
            for s in visible
        ]
    }


# -----------------------------------------------------------------------------
# 5. Remover sessão
# -----------------------------------------------------------------------------
@app.delete("/api/session/{session_id}")
async def delete_session(
    session_id: str,
    _user: dict = Depends(verify_pb_auth),
):
    """Remove uma sessão inteira: cliente ativo, arquivo em disco e
    record no PocketBase.

    A checagem de posse vem ANTES de qualquer efeito: quem não é dono
    recebe 404 e NADA é tocado (nem o arquivo, nem o client Telethon do
    outro).

    O DELETE no PB é o que importa pra integridade: as relations
    `telegram_webhooks.session` e `telegram_messages.session` são
    `cascadeDelete = true`, então apagar o record da sessão arrasta os
    webhooks e TODO o histórico de mensagens junto.

    Sem isso o PB acumulava sessões zumbis: `list_sessions` monta a
    lista a partir dos ARQUIVOS em disco (`load_sessions()`), não do PB
    — então a conta sumia da UI, mas o record, os webhooks e as
    mensagens ficavam no banco para sempre.
    """
    caller_id, _ = _auth_user(_user)

    # (1) Resolve + valida o dono. 404 = não existe OU é de outro usuário.
    session = await _resolve_session_record(session_id)
    if session:
        await _assert_record_owned(session, caller_id)
        pb_id = session.get("id", "")
    else:
        # Órfão: sem record no PB. O fallback de posse é o `owner_id`
        # gravado no arquivo (quando a sessão foi criada com dono).
        pb_id = ""
        file_owner = _session_file_owner(session_id)
        if not file_owner or file_owner != caller_id:
            raise HTTPException(404, "Sessão não encontrada ou sem permissão")

    # (2) Só agora mexe em tudo.
    # Desconecta cliente ativo
    if session_id in active_clients:
        await active_clients[session_id].disconnect()
        del active_clients[session_id]

    # Remove arquivo (fonte de verdade da credencial)
    delete_session_file(session_id)

    # Remove o record no PB (cascade de webhooks + mensagens)
    deleted_in_pb = await _delete_session_record_pb(pb_id)
    if not deleted_in_pb:
        logger.warning(
            f"⚠️ Sessão {session_id} removida do disco mas o record no PB "
            f"não foi deletado — sobraram mensagens/webhooks órfãos"
        )

    return {"success": True, "deleted_pb_record": deleted_in_pb}


def _session_file_owner(session_id: str) -> str:
    """`owner_id` gravado no arquivo da sessão (fallback de posse)."""
    session_file = get_session_file(session_id)
    if not session_file.exists():
        return ""
    try:
        data = json.loads(session_file.read_text())
        return str(data.get("owner_id") or "")
    except Exception:
        return ""


async def _delete_session_record_pb(pb_id: str) -> bool:
    """Apaga o record de `telegram_sessions` no PB (cascade de webhooks
    + mensagens).

    Idempotente: se o record não existir mais (404) retorna False sem
    estourar erro — o objetivo é o banco limpo, não o status HTTP.
    """
    if not pb_id:
        return False
    try:
        await _ensure_pb_service_token()
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.delete(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records/{pb_id}",
                headers=pb_service_headers(),
            )
        if r.status_code == 404:
            return False
        if r.status_code >= 300:
            logger.warning(
                f"PB recusou DELETE da sessão {pb_id}: "
                f"{r.status_code} {r.text[:200]}"
            )
            return False
        logger.info(
            f"🗑️ Sessão removida do PB (cascade webhooks+mensagens): {pb_id}"
        )
        return True
    except Exception as e:
        logger.warning(f"Falha ao remover sessão {pb_id} do PB: {e}")
        return False


# =============================================================================
# Funções Auxiliares
# =============================================================================

async def register_account_pb(
    session_id: str,
    phone: str,
    caller_id: str,
    name: str | None = None,
) -> str:
    """Registra/atualiza a conta no PB (collection `telegram_sessions`).

    A StringSession NÃO é enviada — ela fica só no arquivo em
    `/app/sessions/*.session` (credencial). A collection no PB guarda só
    metadados leves (phone, name), o DONO da sessão (`owner`) e a relação
    com `telegram_webhooks`. Credenciais do app Telegram (api_id/api_hash)
    vivem nos env vars do container e são sempre as mesmas (single-app).

    Usa o service token (superuser) porque as rules de escrita da
    collection estão trancadas (createRule/updateRule = null) — o FastAPI
    é o único escritor e valida o dono antes de escrever.

    Comportamento por estado do record:
      - não existe          → cria com `owner = caller_id`
      - dono == caller      → atualiza (name/phone)
      - SEM dono (legado)   → adota (`owner = caller_id`)
      - dono de OUTRO       → 409 (não rouba a conta de ninguém)

    Retorna "created" | "updated" | "adopted".
    """
    await _ensure_pb_service_token()
    headers = pb_service_headers()

    payload: dict = {
        "session_id": session_id,
        "phone": phone,
    }
    if name:
        payload["name"] = name

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Se já existe record com esse session_id, atualiza (mantém id e
            # created); senão, cria. Idempotente.
            find = await client.get(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
                params={
                    "filter": f'session_id="{session_id}"',
                    "perPage": 1,
                    "fields": "id,session_id,owner",
                },
                headers=headers,
            )
            existing = find.json().get("items", [])
            if existing:
                rec = existing[0]
                rec_id = rec["id"]
                if "owner" in rec:
                    current_owner = str(rec.get("owner") or "")
                    if current_owner and current_owner != caller_id:
                        raise HTTPException(
                            status_code=409,
                            detail="Esta conta Telegram já está vinculada a outro usuário.",
                        )
                    if not current_owner:
                        # Legado sem dono → adota pro caller atual.
                        payload["owner"] = caller_id
                        action = "adopted"
                    else:
                        action = "updated"
                else:
                    # Schema antigo (sem campo `owner`) → isolamento ainda
                    # inativo. O PB ignora campo desconhecido no payload.
                    _warn_ownership_inactive()
                    action = "updated"

                resp = await client.patch(
                    f"{POCKETBASE_URL}/api/collections/telegram_sessions/records/{rec_id}",
                    json=payload,
                    headers=headers,
                )
            else:
                # Cria. `owner` só entra no payload se o campo existir no
                # schema — o PB ignora campo desconhecido, mas fica explícito.
                payload["owner"] = caller_id
                action = "created"
                resp = await client.post(
                    f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
                    json=payload,
                    headers=headers,
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao registrar no PocketBase: {e}")
        raise HTTPException(status_code=503, detail=f"Falha ao registrar no PocketBase: {e}")

    if 200 <= resp.status_code < 300:
        logger.info(f"📝 Conta registrada no PocketBase ({action}): {phone}")
        return action

    # Índice UNIQUE de phone/session_id estourou → o número já pertence a
    # outra conta. Mesma mensagem do 409 do pre-check (UX consistente).
    detail = resp.text[:300]
    if resp.status_code == 400 and ("unique" in detail.lower() or "phone" in detail):
        logger.warning(f"PB recusou registro de {phone} (unique constraint): {detail}")
        raise HTTPException(
            status_code=409,
            detail="Esta conta Telegram já está vinculada a outro usuário.",
        )
    logger.error(f"PB recusou registro de {phone}: {resp.status_code} {detail}")
    raise HTTPException(status_code=400, detail=f"PB recusou registro: {detail}")


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
    # (negativo pra groups/channels). Usa `_resolve_peer_entity` (que
    # inclui a varredura de dialogs) pra não perder sender/chat_title
    # quando a mensagem foi enviada pra alguém de primeiro contato.
    entity = await _resolve_peer_entity(client, sent.chat_id)
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
        # ID da mensagem no Telegram (único por chat). Diferente do `id`
        # do record no PB.
        "telegram_message_id": int(sent.id),
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

    # Isolamento por dono: a sessão precisa PERTENCER ao caller. Sem esta
    # checagem, qualquer autenticado (inclusive o token de integração de
    # outro cliente) enviaria mensagem pela conta Telegram de outra pessoa —
    # o `active_clients` é global do processo e não sabe de dono.
    caller_id, _ = _auth_user(_user)
    await _resolve_owned_session(request.session_id, caller_id)

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

    # Resolve o peer ANTES de enviar. `send_message(chat_id)` monta um
    # `InputPeerUser` a partir do chat_id e falha com "Could not find the
    # input entity for PeerUser(...)" quando o destinatário é alguém de
    # PRIMEIRO CONTATO (sem access_hash no cache do Telethon).
    # `_resolve_peer_entity` varre os dialogs, que é o que traz o
    # access_hash — sem isso a resposta automatizada pro contato novo
    # quebrava com HTTP 400.
    target = request.chat_id
    if isinstance(target, str) and target.lstrip("-").isdigit():
        try:
            target = int(target)
        except ValueError:
            target = None
    if isinstance(target, int):
        await _resolve_peer_entity(client, target)

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


def _auth_user(auth_response: dict) -> tuple[str, str]:
    """
    Extrai `(id, email)` do dict devolvido por `verify_pb_auth`.

    O PB `/auth-refresh` responde o ENVELOPE `{"token": ..., "record": {...}}`,
    não o record direto — por isso o `record` é lido primeiro. O fallback pra
    `id`/`email` no topo cobre o caso de o envelope mudar, em vez de devolver
    id vazio e gerar um token de ninguém.
    """
    record = auth_response.get("record")
    source = record if isinstance(record, dict) else auth_response
    return str(source.get("id") or ""), str(source.get("email") or "")


# =============================================================================
# Token de integração (API key estilo impersonate do PocketBase)
# =============================================================================

@app.post("/api/integration-token")
async def create_integration_token(
    request: IntegrationTokenRequest,
    auth_response: dict = Depends(verify_pb_auth),
):
    """
    Gera um token do PocketBase para o usuário AUTENTICADO usando o endpoint
    `impersonate` — que, por definição, só o superuser pode chamar. O frontend
    não tem superuser (só o JWT do próprio user), então o proxy acontece aqui.

    Uso: o usuário gera o token no painel (`/docs`), copia e usa como
    `Authorization: <token>` em OUTRO sistema (n8n, Make, backend próprio)
    pra chamar `POST /api/send-message`.

    O token gerado é um JWT de auth record normal, então o `verify_pb_auth`
    existente valida sem precisar saber da origem dele.

    ⚠ O token é ESTÁTICO: não renova e NÃO tem revogação individual (o PB é
    stateless, sem sessão e sem logout). Gerar outro não invalida este — o
    caminho real de revogação é trocar a senha do usuário no Admin UI do PB,
    o que rotaciona o `tokenKey` dele.
    """
    user_id, user_email = _auth_user(auth_response)
    if not user_id:
        # Token válido pro PB mas sem record utilizável — não gera nada.
        raise HTTPException(401, "Token inválido ou expirado")

    duration = _clamp_integration_duration(request.duration)
    url = f"{POCKETBASE_URL}/api/collections/users/impersonate/{user_id}"

    async def _ask_pb(token: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=15.0) as client:
            return await client.post(
                url,
                json={"duration": duration},
                # O PB NÃO aceita o prefixo "Bearer" — só o JWT cru (mesma
                # regra de `pb_service_headers`).
                headers={"Authorization": token},
            )

    try:
        service_token = await _ensure_pb_service_token()
    except Exception as e:
        logger.error(f"Falha ao obter o service token do PB: {e}")
        raise HTTPException(status_code=503, detail="Serviço de autenticação indisponível")

    try:
        r = await _ask_pb(service_token)
        if r.status_code == 401:
            # Caminho "POCKETBASE_SERVICE_TOKEN = JWT fixo" não tem auto-refresh:
            # se o JWT do env expirou, o PB rejeita. Re-autentica e tenta 1x.
            logger.warning("Impersonate recusou o service token — forçando refresh")
            service_token = await force_refresh_pb_service_token()
            r = await _ask_pb(service_token)

        if r.status_code == 404:
            raise HTTPException(status_code=404, detail="Usuário não encontrado no PocketBase")

        if r.status_code != 200:
            # Loga o body do PB (contexto do erro). NUNCA o header/token.
            logger.error(
                f"Impersonate falhou no PB: HTTP {r.status_code} — {r.text[:300]}"
            )
            raise HTTPException(status_code=502, detail="Falha ao gerar o token no PocketBase")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao gerar token de integração: {e}")
        raise HTTPException(status_code=502, detail="Falha ao gerar o token no PocketBase")

    try:
        body = r.json()
    except Exception:
        body = {}

    token = body.get("token")
    if not token:
        # Loga só as CHAVES — o body dessa rota, quando 200, carrega o token.
        logger.error(f"Impersonate respondeu sem token. Chaves: {list(body.keys())}")
        raise HTTPException(status_code=502, detail="Falha ao gerar o token no PocketBase")

    expires_at = _jwt_exp(token) or 0

    # Log de auditoria. NÃO inclui o token.
    logger.info(
        f"🔑 Token de integração gerado para {user_email or user_id} "
        f"(user_id={user_id}, duração={duration}s, expira em={expires_at})"
    )

    return {
        "success": True,
        "token": token,
        "expires_at": expires_at,
        "duration": duration,
        "user": {"id": user_id, "email": user_email},
    }


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

    IMPORTANTE: só lista as sessões DO CALLER. Esse endpoint é autenticado
    (não é admin de verdade) — expor o telefone de todo mundo seria o
    mesmo vazamento que estamos fechando.
    """
    caller_id, _ = _auth_user(_user)
    owned, ownership_active = await _list_owned_sessions(caller_id)

    sessions = []
    for session_file in sorted(SESSIONS_DIR.glob("*.session")):
        try:
            data = json.loads(session_file.read_text())
            session_id = session_file.stem
            if ownership_active and session_id not in owned:
                # Sessão de outro usuário (ou sem dono) → não expõe.
                continue
            sessions.append({
                "session_id": session_id,
                "phone": data.get("phone"),
                "owner_id": data.get("owner_id"),
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
