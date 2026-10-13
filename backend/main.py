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

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.events import NewMessage
from telethon.sessions import StringSession

import httpx

# =============================================================================
# Configuração
# =============================================================================

API_ID = int(os.getenv("TG_API_ID", "0"))
API_HASH = os.getenv("TG_API_HASH", "")
POCKETBASE_URL = os.getenv("POCKETBASE_URL", "http://localhost:8090")
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


class SetWebhookRequest(BaseModel):
    session_id: str
    webhook_url: str


class DeleteSessionRequest(BaseModel):
    session_id: str


# =============================================================================
# Persistência de Sessões
# =============================================================================

def get_session_file(session_id: str) -> Path:
    """Retorna o caminho do arquivo de sessão"""
    return SESSIONS_DIR / f"{session_id}.session"


def save_session(session_id: str, session_string: str, phone: str, webhook_url: str = None):
    """Salva sessão no sistema de arquivos"""
    session_file = get_session_file(session_id)
    data = {
        "session_string": session_string,
        "phone": phone,
        "webhook_url": webhook_url,
        "created_at": datetime.now().isoformat()
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
# Event Handler - Forward para Webhook
# =============================================================================

async def handle_new_message(event, session_id: str):
    """Handler que dispara quando chega nova mensagem"""
    try:
        # Busca webhook da sessão
        webhook_url = None
        if session_id in active_clients:
            session_file = get_session_file(session_id)
            if session_file.exists():
                data = json.loads(session_file.read_text())
                webhook_url = data.get("webhook_url")

        if not webhook_url:
            logger.debug(f"Sessão {session_id} sem webhook configurado, ignorando")
            return

        # Extrai dados da mensagem
        message_data = {
            "session_id": session_id,
            "chat_id": event.chat_id,
            "message_id": event.id,
            "text": event.text or "",
            "sender_id": event.sender_id,
            "timestamp": datetime.now().isoformat(),
        }

        # Adiciona nome do remetente se disponível
        if event.sender:
            message_data["sender_name"] = (
                event.sender.first_name or ""
            ) + (
                f" {event.sender.last_name}" if event.sender.last_name else ""
            )

        # Forward para webhook
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(webhook_url, json=message_data)
            if response.status_code == 200:
                logger.info(f"📤 Msg #{event.id} de {message_data.get('sender_name', '?')} → webhook OK")
            else:
                logger.warning(f"📤 Msg #{event.id} → webhook retornou {response.status_code}")

    except Exception as e:
        logger.error(f"Erro ao processar mensagem: {e}")


# =============================================================================
# Gerenciamento de Clientes Telethon
# =============================================================================

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

        # Adiciona event handler
        @client.on(NewMessage(incoming=True))
        async def handler(event):
            await handle_new_message(event, session_id)

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
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
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
    Dependency que valida o token PB enviado via header
    `Authorization: Bearer <jwt>`. Confia no PB como fonte de verdade
    (chama /api/collections/users/auth-refresh) e cacheia por 5 min pra
    não martelar o PB a cada request.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Não autenticado")

    token = authorization.split(" ", 1)[1].strip()
    now = time.time()

    cached = _auth_cache.get(token)
    if cached and cached[1] > now:
        return cached[0]

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
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Falha ao validar token PB: {e}")
        raise HTTPException(503, "Serviço de autenticação indisponível")


# =============================================================================
# Rotas
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "active_sessions": len(active_clients),
        "api_configured": API_ID != 0 and bool(API_HASH)
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
        await client.start()
        result = await client.send_code_request(request.phone_number)

        # Salva temporariamente para usar na verificação
        active_clients[session_id] = client
        active_clients[f"{session_id}_hash"] = result.phone_code_hash

        return {
            "success": True,
            "session_id": session_id,
            "phone_code_hash": result.phone_code_hash,
            "expires": result.expire_interval
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------------------------------------------------------
# 2. Verificar código e criar sessão
# -----------------------------------------------------------------------------
@app.post("/api/verify-code")
async def verify_code(
    request: VerifyCodeRequest,
    background_tasks: BackgroundTasks,
    _user: dict = Depends(verify_pb_auth),
):
    """
    Verifica o código, cria sessão persistente e inicia escuta.
    """
    session_id = f"pending_{request.phone_number}"
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
        if request.password:
            await client.sign_in(
                request.phone_number,
                code=request.code,
                password=request.password,
                phone_code_hash=phone_code_hash
            )
        else:
            await client.sign_in(
                request.phone_number,
                code=request.code,
                phone_code_hash=phone_code_hash
            )

        # Salva sessão
        session_string = client.session.save()
        final_session_id = f"account_{request.phone_number.replace('+', '')}"

        # Persiste em arquivo
        save_session(final_session_id, session_string, request.phone_number)

        # Move cliente para sessão final
        active_clients[final_session_id] = client
        del active_clients[session_id]
        del active_clients[hash_key]

        # Registra no PocketBase em background
        background_tasks.add_task(register_account_pb, final_session_id, request.phone_number)

        return {
            "success": True,
            "session_id": final_session_id,
            "message": "Conta pareada com sucesso!"
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------------------------------------------------------
# 3. Configurar webhook para sessão
# -----------------------------------------------------------------------------
@app.post("/api/set-webhook")
async def set_webhook(request: SetWebhookRequest, _user: dict = Depends(verify_pb_auth)):
    """
    Configura URL do webhook para uma sessão.
    """
    session_id = request.session_id

    # Valida sessão existe
    if session_id not in active_clients:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    # Atualiza arquivo de sessão
    session_file = get_session_file(session_id)
    if session_file.exists():
        data = json.loads(session_file.read_text())
        data["webhook_url"] = request.webhook_url
        session_file.write_text(json.dumps(data))
    else:
        # Cria arquivo se não existir
        save_session(session_id, "", "", request.webhook_url)

    logger.info(f"🔗 Webhook configurado para {session_id}: {request.webhook_url}")

    return {"success": True, "webhook_url": request.webhook_url}


# -----------------------------------------------------------------------------
# 4. Listar sessões
# -----------------------------------------------------------------------------
@app.get("/api/sessions")
async def list_sessions(_user: dict = Depends(verify_pb_auth)):
    """Lista todas as sessões (ativas e salvas)"""
    saved = load_sessions()

    return {
        "sessions": [
            {
                "session_id": s["session_id"],
                "phone": s.get("phone", ""),
                "webhook_url": s.get("webhook_url"),
                "active": s["session_id"] in active_clients,
                "created_at": s.get("created_at")
            }
            for s in saved
        ]
    }


# -----------------------------------------------------------------------------
# 5. Remover sessão
# -----------------------------------------------------------------------------
@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str, _user: dict = Depends(verify_pb_auth)):
    """Remove uma sessão (desconecta e apaga)"""
    # Desconecta cliente ativo
    if session_id in active_clients:
        await active_clients[session_id].disconnect()
        del active_clients[session_id]

    # Remove arquivo
    delete_session_file(session_id)

    return {"success": True}


# -----------------------------------------------------------------------------
# 6. Testar webhook
# -----------------------------------------------------------------------------
@app.post("/api/test-webhook")
async def test_webhook(webhook_url: str = "", _user: dict = Depends(verify_pb_auth)):
    """Envia uma mensagem de teste para o webhook"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                webhook_url,
                json={
                    "type": "test",
                    "message": "Conexão OK!",
                    "timestamp": datetime.now().isoformat()
                }
            )
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Funções Auxiliares
# =============================================================================

async def register_account_pb(session_id: str, phone: str):
    """
    Registra metadata da conta no PocketBase (collection `telegram_sessions`).
    A StringSession NÃO é enviada — ela fica só no FA em `/app/sessions/*.json`,
    pois a collection no PB é só pra auditoria/UI (não tem nem deve ter o
    session_string, que é a credencial real da conta Telegram).
    """
    payload = {
        "session_id": session_id,
        "phone": phone,
        "active": True,
    }
    if API_ID:
        payload["api_id"] = API_ID
    if API_HASH:
        payload["api_hash"] = API_HASH

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{POCKETBASE_URL}/api/collections/telegram_sessions/records",
                json=payload,
            )
        if 200 <= resp.status_code < 300:
            logger.info(f"📝 Conta registrada no PocketBase: {phone}")
        else:
            logger.error(
                f"PB recusou registro de {phone}: {resp.status_code} {resp.text}"
            )
    except Exception as e:
        logger.error(f"Erro ao registrar no PocketBase: {e}")


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
