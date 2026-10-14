"""
FastAPI Backend - Telegram Account Webhook
Gerencia sessões Telethon e forwards mensagens para webhooks dos clientes
"""

import os
import json
import time
import asyncio
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
# Service token do PB: JWT de um user dedicado (criar no PB admin UI, ex:
# service@telegram-webhook.local). Usado nas chamadas internas ao PB
# que rodam SEM request HTTP no contexto (handler de mensagem do
# Telethon, jobs em background) — não dá pra repassar o token do user
# porque esses fluxos não têm user. Sem o service token, o PB rejeita
# com 401 e `_get_active_webhooks` retorna [], silenciosamente
# impedindo o webhook forwarding de funcionar.
POCKETBASE_SERVICE_TOKEN = os.getenv("POCKETBASE_SERVICE_TOKEN", "")
SESSIONS_DIR = Path("/app/sessions")
SESSIONS_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
# Event Handler - Forward para Webhook (multi-webhook com filtros)
# =============================================================================

# Cache de webhooks ativos por sessão: session_id -> (timestamp, list[dict]).
# Cada item é o record completo do PB. TTL 30s — webhooks novos/editados
# aparecem no máximo 30s depois; endpoints que mutam webhooks invalidam
# explicitamente o cache pra reduzir a janela.
_WEBHOOK_CACHE: Dict[str, tuple[float, list[dict]]] = {}
_WEBHOOK_CACHE_TTL_SEC = 30.0
# Cache de "qual user PB é dono de qual sessão Telegram".
# Populado no register_account_pb (signup). Permite ao handler do Telethon
# (que roda em background, sem request HTTP) saber qual token usar pra
# falar com o PB em nome do user.
_SESSION_OWNER: Dict[str, str] = {}  # session_id -> pb_user_id
# Cache de tokens JWT ativos por user PB.
# Populado em verify_pb_auth toda vez que o user chama qualquer endpoint.
# O _get_active_webhooks consulta esse cache pra falar com o PB.
# Tokens são renovados (refreshed) automaticamente pelo verify_pb_auth.
_USER_TOKENS: Dict[str, str] = {}  # pb_user_id -> user_token
# Flag pra logar o warning de service token ausente SÓ UMA VEZ no startup,
# não toda mensagem (evita flood no log).
_service_token_warned: bool = False


def _service_pb_headers() -> dict:
    """Header pro PB com o service token global (env var) OU cache por user.

    Ordem de preferência:
    1. POCKETBASE_SERVICE_TOKEN (env var) — se configurado, sempre usa.
    2. Token do user "dono" da sessão (cache _USER_TOKENS[_SESSION_OWNER[session_id]]).
       Atualizado automaticamente em verify_pb_auth.

    Se nenhum dos dois estiver disponível, retorna {} (PB rejeitará com 401).
    """
    if POCKETBASE_SERVICE_TOKEN:
        return {"Authorization": POCKETBASE_SERVICE_TOKEN}
    return {}


def _session_token_headers(session_id: str) -> dict:
    """Header pro PB específico da sessão Telegram — usa o token do user dono.

    Sem isso, o handler do Telethon (background, sem request) não tem
    accesso ao token do user. O token é cacheado em _USER_TOKENS toda
    vez que o user chama qualquer endpoint, então fica fresco (5 min
    de TTL no verify_pb_auth).
    """
    owner_id = _SESSION_OWNER.get(session_id)
    if not owner_id:
        return {}
    user_token = _USER_TOKENS.get(owner_id)
    if not user_token:
        return {}
    return {"Authorization": user_token}


async def _get_active_webhooks(session_id: str) -> list[dict]:
    """Busca webhooks ativos (enabled=true) da sessão, com cache 30s.

    Ordem de preferência do token PB:
    1. POCKETBASE_SERVICE_TOKEN (env var, global)
    2. Token do user dono da sessão (cache _USER_TOKENS, populado em
       verify_pb_auth). OBRIGATÓRIO se não tiver env var — sem isso o
       handler do Telethon não tem como falar com o PB.
    """
    import time as _time
    global _service_token_warned
    now = _time.time()
    cached = _WEBHOOK_CACHE.get(session_id)
    if cached and (now - cached[0]) < _WEBHOOK_CACHE_TTL_SEC:
        return cached[1]

    # 1) Tenta o env var primeiro
    headers = _service_pb_headers()
    # 2) Se não tiver, usa o token do user dono da sessão
    if not headers:
        headers = _session_token_headers(session_id)

    if not headers and not _service_token_warned:
        logger.warning(
            "Sem token PB disponível pro handler (nem POCKETBASE_SERVICE_TOKEN "
            "env var, nem user dono da sessão). Webhook forwarding vai falhar "
            "com 401 — popule POCKETBASE_SERVICE_TOKEN OU use a UI com a "
            "sessão logada pra popular _USER_TOKENS."
        )
        _service_token_warned = True

    # 1) Acha o record da sessão no PB
    async with httpx.AsyncClient(timeout=10.0) as client:
        sess_resp = await client.get(
            f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
            params={"filter": f'session_id="{session_id}"', "perPage": 1},
            headers=headers,
        )
        sess_items = sess_resp.json().get("items", [])
        if not sess_items:
            # Sessão não existe no PB (saiu do ar) — cacheia [] por 30s
            # pra não martelar o PB a cada mensagem. Mas só se o request
            # não falhou por auth.
            if sess_resp.status_code == 200:
                _WEBHOOK_CACHE[session_id] = (now, [])
            return []
        pb_session_id = sess_items[0]["id"]

        # 2) Lista os webhooks ativos
        wh_resp = await client.get(
            f"{POCKETBASE_URL}/api/collections/telegram_webhooks/records",
            params={"filter": f'session="{pb_session_id}" && enabled=true', "perPage": 500},
            headers=headers,
        )
        if wh_resp.status_code != 200:
            # 401/403/500: NÃO cacheia — tenta de novo na próxima mensagem.
            # Senão fica 30s preso no estado "envenenado".
            logger.warning(
                f"PB recusou listagem de webhooks: {wh_resp.status_code} {wh_resp.text[:200]}"
            )
            return []
        webhooks = wh_resp.json().get("items", [])

    _WEBHOOK_CACHE[session_id] = (now, webhooks)
    return webhooks


def _invalidate_webhook_cache(session_id: str | None = None) -> None:
    """Invalida o cache. Se session_id=None, invalida tudo (usar com cuidado)."""
    if session_id is None:
        _WEBHOOK_CACHE.clear()
    else:
        _WEBHOOK_CACHE.pop(session_id, None)


def _matches_filters(event, webhook: dict) -> bool:
    """Avalia os 3 filtros do webhook contra o evento do Telethon."""
    # Filtro de direção
    direction = webhook.get("filter_direction", "all")
    if direction == "incoming" and event.outgoing:
        return False
    if direction == "outgoing" and not event.outgoing:
        return False

    # Filtro de tipo de chat
    chat_type = webhook.get("filter_chat_type", "all")
    if chat_type != "all" and chat_type != _chat_type(event):
        return False

    # Filtro de texto
    op = webhook.get("filter_text_match_operator", "none")
    value = (webhook.get("filter_text_match_value") or "").strip()
    if op == "none" or not value:
        return True
    text = (event.text or "").strip()
    if op == "equals":
        return text == value
    if op == "contains":
        return value in text
    return True


async def handle_new_message(event, session_id: str):
    """Handler que dispara quando chega nova mensagem nova.

    Pra cada webhook ativo da sessão (PB + cache), avalia os filtros
    configurados e faz POST na URL se passar. Best-effort: status != 200
    ou timeout são logados, sem retry.
    """
    try:
        logger.info(
            f"📩 Nova mensagem recebida: session={session_id} "
            f"chat={event.chat_id} msg_id={event.id}"
        )

        if session_id not in active_clients:
            logger.warning(
                f"⚠️ Mensagem de sessão {session_id} NÃO está em active_clients "
                f"— handler foi chamado mas cliente foi desconectado?"
            )
            return

        webhooks = await _get_active_webhooks(session_id)
        if not webhooks:
            logger.debug(
                f"⏭️ Sessão {session_id} sem webhooks ativos, ignorando"
            )
            return

        # Filtra pelos filtros configurados em cada webhook
        matched = [wh for wh in webhooks if _matches_filters(event, wh)]
        if not matched:
            logger.debug(
                f"⏭️ Msg #{event.id} não casou com nenhum webhook ativo "
                f"de {session_id} (filtros)"
            )
            return

        message_data = _build_message_payload(event, session_id)

        # Forward pra cada webhook que passou nos filtros
        async with httpx.AsyncClient(timeout=30.0) as client:
            for wh in matched:
                url = wh.get("url")
                wh_id = wh.get("id", "?")
                try:
                    response = await client.post(url, json=message_data)
                    if response.status_code == 200:
                        logger.info(
                            f"📤 Msg #{event.id} de "
                            f"{message_data.get('sender_name', '?')} → "
                            f"webhook {wh_id} OK"
                        )
                    else:
                        logger.warning(
                            f"📤 Msg #{event.id} → webhook {wh_id} "
                            f"retornou {response.status_code}"
                        )
                except Exception as send_err:
                    logger.warning(
                        f"📤 Msg #{event.id} → webhook {wh_id} falhou: "
                        f"{send_err}"
                    )

    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {e}")


def _classify_media(media) -> tuple[bool, str | None, str | None]:
    """
    Classifica o `event.media` (MessageMediaPhoto / MessageMediaDocument / etc.)
    num tipo simples pro payload do webhook. Retorna (has_media, media_type, mime_type).
    """
    if media is None:
        return False, None, None

    if isinstance(media, tl_types.MessageMediaPhoto):
        return True, "photo", "image/jpeg"

    if isinstance(media, tl_types.MessageMediaGeo):
        return True, "geo", None

    if isinstance(media, tl_types.MessageMediaContact):
        return True, "contact", None

    if isinstance(media, tl_types.MessageMediaPoll):
        return True, "poll", None

    if isinstance(media, tl_types.MessageMediaDocument):
        doc = media.document
        mime = getattr(doc, "mime_type", None)
        kind = "document"
        # heurística por mime
        if mime:
            if mime.startswith("image/"):
                kind = "photo" if mime == "image/webp" else "image"
            elif mime.startswith("video/"):
                kind = "video"
            elif mime.startswith("audio/"):
                kind = "voice" if mime == "audio/ogg" else "audio"
        # sticker é um documento com attribute Sticker
        if doc and any(isinstance(a, tl_types.DocumentAttributeSticker) for a in (doc.attributes or [])):
            kind = "sticker"
        return True, kind, mime

    # fallback genérico
    return True, type(media).__name__, None


def _chat_type(event) -> str:
    """
    Retorna o tipo do chat da mensagem: 'private' | 'group' | 'supergroup' | 'channel'.
    Usa os helpers do Telethon (is_private, is_group, is_channel).
    """
    if event.is_private:
        return "private"
    if event.is_channel:
        return "channel"
    if event.is_group:
        return "group"
    return "unknown"


def _build_message_payload(event, session_id: str) -> dict:
    """
    Monta o payload enriquecido enviado pro webhook. Inclui:
    - session_id, message_id, chat_id, text
    - chat_type (private/group/supergroup/channel) + chat_title quando aplicável
    - sender_id, sender_name, sender_username
    - is_reply + reply_to_message_id (pra permitir responder via /api/send-message)
    - has_media, media_type, media_mime_type
    - timestamp
    """
    has_media, media_type, media_mime = _classify_media(event.media)

    # chat_title: para private é o first_name do peer, senão é o title do chat
    chat_title = None
    if event.chat:
        chat_title = getattr(event.chat, "title", None) or getattr(event.chat, "first_name", None)

    # reply_to: Telethon expõe em event.reply_to e event.reply_to_msg_id (se reply)
    reply_to_msg_id = getattr(event, "reply_to_msg_id", None)
    is_reply = reply_to_msg_id is not None

    # sender_username: nem todo User tem; pode ser None
    sender_username = None
    if event.sender and getattr(event.sender, "username", None):
        sender_username = event.sender.username

    return {
        "session_id": session_id,
        "message_id": event.id,
        "chat_id": event.chat_id,
        "chat_type": _chat_type(event),
        "chat_title": chat_title,
        "outgoing": bool(event.outgoing),  # True se foi enviada pela própria conta
        "text": event.text or "",
        "sender_id": event.sender_id,
        "sender_name": (
            (
                (event.sender.first_name or "")
                + (f" {event.sender.last_name}" if event.sender.last_name else "")
            )
            if event.sender else None
        ),
        "sender_username": sender_username,
        "is_reply": is_reply,
        "reply_to_message_id": reply_to_msg_id,
        "has_media": has_media,
        "media_type": media_type,
        "media_mime_type": media_mime,
        "timestamp": datetime.now().isoformat(),
    }


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
        # Suprime mensagens enviadas por nós mesmos via /api/send-message
        # pra não gerar loop com o webhook receptor (ex: n8n respondendo).
        if event.outgoing and _is_recently_sent(event.id):
            return
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

    # Valida credenciais
    if API_ID == 0 or not API_HASH:
        logger.warning("⚠️ TG_API_ID ou TG_API_HASH não configurados!")

    # Inicializa sessões
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

    # Popula _USER_TOKENS (cache de "qual JWT usar pra falar com o PB
    # em nome deste user"). Usado pelo _get_active_webhooks em background
    # tasks (handler do Telethon) que não têm request HTTP no contexto.
    user_id = user.get("id", "")
    if user_id and token:
        _USER_TOKENS[user_id] = token

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
        _invalidate_webhook_cache(session_id)
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
            _invalidate_webhook_cache(sid)
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
            _invalidate_webhook_cache(sid)
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
            _invalidate_webhook_cache(sid)
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
    _invalidate_webhook_cache()
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

    # Invalida cache de webhooks dessa sessão
    _invalidate_webhook_cache(session_id)

    # Remove associação session_id -> user_id
    _SESSION_OWNER.pop(session_id, None)

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
            # Cacheia a associação session_id -> pb_user_id. O handler do
            # Telethon (que roda em background) consulta _SESSION_OWNER
            # pra saber qual token do PB usar pro _get_active_webhooks.
            if user_token and user_token in _USER_TOKENS:
                # Já temos o user_id cacheado pelo verify_pb_auth
                for uid, tok in _USER_TOKENS.items():
                    if tok == user_token:
                        _SESSION_OWNER[session_id] = uid
                        logger.info(
                            f"🔗 Sessão {session_id} associada ao user PB {uid}"
                        )
                        break
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
