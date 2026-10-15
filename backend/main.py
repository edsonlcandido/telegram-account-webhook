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
# Event Handler - INSERT em telegram_messages, hook do PB distribui
# =============================================================================
#
# A lógica de filtro + envio pros webhooks agora é responsabilidade do hook
# onRecordAfterCreate em pb_hooks/main.pb.js (roda DENTRO do PB, sem auth,
# sem propagação de token). O FastAPI só insere o record da mensagem.
#
# Caches necessários (todos populados em runtime):
# - _SESSION_OWNER[session_id] = pb_user_id  → qual user "dono" da sessão
# - _USER_TOKENS[pb_user_id] = user_token    → JWT do user pra fazer INSERT
# - _SESSION_PB_ID[session_id] = pb_record_id → record id do PB (pra relation)
#
# _SESSION_OWNER é populado no register_account_pb (background task do
# verify_code). _USER_TOKENS é populado em verify_pb_auth. _SESSION_PB_ID
# é populado no register_account_pb também. Se uma sessão for criada
# antes desse deploy, o cache vai estar vazio e o handler não consegue
# inserir — aí o user precisa re-adicionar via signup (que re-popula).
_SESSION_OWNER: Dict[str, str] = {}  # session_id -> pb_user_id
_USER_TOKENS: Dict[str, str] = {}  # pb_user_id -> user_token
_SESSION_PB_ID: Dict[str, str] = {}  # session_id -> pb_record_id


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


async def handle_new_message(event, session_id: str):
    """Handler que dispara quando chega nova mensagem.

    Comportamento novo (a partir desse refactor): só faz INSERT em
    `telegram_messages` no PB. O hook do PB cuida de listar webhooks
    ativos, aplicar filtros, e fazer POST em cada um. Sem auth propagation
    problema, sem cache envenenado, sem race condition.
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

        # Ignora mensagens que NÓS mesmos enviamos (loop infinito)
        if _is_recently_sent(event.id):
            return

        # Acha o token PB do user dono da sessão
        owner_id = _SESSION_OWNER.get(session_id)
        user_token = _USER_TOKENS.get(owner_id) if owner_id else None
        pb_session_id = _SESSION_PB_ID.get(session_id)

        # Fallback: se o cache não tem, busca no PB (1 chamada extra).
        # Caso comum: sessão criada antes desse deploy ou container
        # reiniciou e o cache em memória zerou.
        if (not user_token) or (not pb_session_id):
            if not user_token:
                logger.warning(
                    f"⚠️ Sem token PB pra sessão {session_id} (_SESSION_OWNER="
                    f"{owner_id!r}, _USER_TOKENS tem esse user? "
                    f"{bool(user_token)}). Ignorando mensagem."
                )
                return
            # pb_session_id ausente — busca
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(
                        f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
                        params={"filter": f'session_id="{session_id}"', "perPage": 1},
                        headers={"Authorization": user_token},
                    )
                items = r.json().get("items", [])
                if not items:
                    logger.warning(
                        f"⚠️ Sessão {session_id} não existe no PB — ignorando msg"
                    )
                    return
                pb_session_id = items[0]["id"]
                _SESSION_PB_ID[session_id] = pb_session_id
            except Exception as e:
                logger.error(f"Erro buscando pb_id da sessão: {e}")
                return

        # Monta o record mínimo (hook do PB lê o record e processa)
        sender_name = _sender_name(event)
        chat_title = _chat_title(event)
        is_outgoing = bool(getattr(event, "outgoing", False))
        msg_data = {
            "session": pb_session_id,
            "chat_id": int(event.chat_id) if event.chat_id is not None else 0,
            "chat_type": _classify_chat_type(event),
            "chat_title": chat_title or "",
            "direction": "outgoing" if is_outgoing else "incoming",
            "sender_id": int(event.sender_id) if event.sender_id is not None else 0,
            "sender_name": sender_name or "",
            "text": event.text or "",
        }

        # INSERT no PB → hook onRecordAfterCreate dispara automaticamente
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    f"{POCKETBASE_URL}/api/collections/telegram_messages/records",
                    json=msg_data,
                    headers={"Authorization": user_token},
                )
            if r.status_code >= 300:
                logger.warning(
                    f"PB recusou INSERT msg: {r.status_code} {r.text[:200]}"
                )
            else:
                logger.info(
                    f"📨 Msg #{event.id} inserida em telegram_messages (sessão "
                    f"{session_id}); hook do PB vai distribuir pros webhooks"
                )
        except Exception as e:
            logger.error(f"Erro fazendo INSERT de msg no PB: {e}")

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
        # Suprime mensagens enviadas por nós mesmos via /api/send-message
        # pra não gerar loop com o webhook receptor (ex: n8n respondendo).
        # Usa getattr pq o `event.outgoing` nem sempre delega (depende
        # da versão do Telethon — às vezes vem `Message has no attribute
        # 'outgoing'` se o message for None ou partial).
        if getattr(event, "outgoing", False) and _is_recently_sent(event.id):
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

    # Invalida cache de webhooks dessa sessão
    pass  # invalidate removed (hook do PB faz cache via SQL)

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
            # pra saber qual token do PB usar pra inserir em
            # telegram_messages (o hook do PB cuida do resto).
            if user_token:
                # Procura qual user_id tem esse token no cache. O cache
                # _USER_TOKENS é {user_id -> token}, populado em
                # verify_pb_auth. NÃO comparar com `in` (checaria se é
                # CHAVE do dict, não valor — sempre False).
                for uid, tok in _USER_TOKENS.items():
                    if tok == user_token:
                        _SESSION_OWNER[session_id] = uid
                        logger.info(
                            f"🔗 Sessão {session_id} associada ao user PB {uid}"
                        )
                        break
                else:
                    logger.warning(
                        f"⚠️ user_token não encontrado em _USER_TOKENS — "
                        f"_SESSION_OWNER[{session_id}] ficou vazio, webhook "
                        f"forwarding não vai funcionar até o user chamar "
                        f"qualquer endpoint autenticado e o backend recachear."
                    )
            # Cacheia o record id do PB pra relation no INSERT de mensagens
            try:
                resp_json = resp.json()
                if resp_json.get("id"):
                    _SESSION_PB_ID[session_id] = resp_json["id"]
            except Exception:
                pass
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
