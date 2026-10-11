"""
FastAPI Backend - Telegram Account Webhook
Gerencia sessões Telethon e forwards para webhooks dos clientes
"""

import os
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telethon import TelegramClient
from telethon.sessions import StringSession

import httpx

# Configuração
API_ID = int(os.getenv("TG_API_ID", "0"))
API_HASH = os.getenv("TG_API_HASH", "")
POCKETBASE_URL = os.getenv("POCKETBASE_URL", "http://localhost:8090")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Armazenamento de sessões ativas (em produção, usar Redis ou similar)
active_sessions: Dict[str, TelegramClient] = {}


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


class MessagePayload(BaseModel):
    chat_id: int
    message_id: int
    text: str
    sender_name: Optional[str] = None
    sender_id: Optional[int] = None
    timestamp: Optional[str] = None


# =============================================================================
# Funções Auxiliares
# =============================================================================

async def forward_to_webhook(webhook_url: str, payload: dict) -> bool:
    """Encaminha mensagem para o webhook do cliente"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Erro ao enviar para webhook {webhook_url}: {e}")
        return False


async def register_account_in_pb(session_id: str, phone: str, session_string: str):
    """Registra a conta no PocketBase"""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{POCKETBASE_URL}/api/collections/accounts/records",
                json={
                    "session_id": session_id,
                    "phone": phone,
                    "session_string": session_string,
                    "active": True
                }
            )
    except Exception as e:
        logger.error(f"Erro ao registrar no PocketBase: {e}")


# =============================================================================
# Lifespan - gerenciacleanup
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 FastAPI started")
    yield
    # Cleanup de sessões
    for session_id, client in active_sessions.items():
        await client.disconnect()
    logger.info("👋 FastAPI stopped")


# =============================================================================
# App
# =============================================================================

app = FastAPI(
    title="Telegram Account Webhook API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Rotas
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok", "active_sessions": len(active_sessions)}


@app.post("/api/send-code")
async def send_verification_code(request: SendCodeRequest):
    """
    Envia código de verificação para o Telegram.
    Retorna o phone_code_hash necessário para o próximo passo.
    """
    if API_ID == 0 or not API_HASH:
        raise HTTPException(
            status_code=500,
            detail="TG_API_ID e TG_API_HASH devem estar configurados"
        )

    session_id = f"temp_{request.phone_number}"
    client = TelegramClient(StringSession(), API_ID, API_HASH)

    try:
        await client.start()
        result = await client.send_code_request(request.phone_number)

        # Salva cliente temporariamente
        active_sessions[session_id] = client
        active_sessions[f"{session_id}_hash"] = result.phone_code_hash

        return {
            "success": True,
            "session_id": session_id,
            "phone_code_hash": result.phone_code_hash,
            "expires": result.expire_interval
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/verify-code")
async def verify_code(request: VerifyCodeRequest, background_tasks: BackgroundTasks):
    """
    Verifica o código e cria a sessão persistente.
    """
    session_id = f"temp_{request.phone_number}"
    hash_key = f"{session_id}_hash"

    if session_id not in active_sessions or hash_key not in active_sessions:
        raise HTTPException(status_code=400, detail="Sessão não encontrada. Solicite o código novamente.")

    client = active_sessions[session_id]
    phone_code_hash = active_sessions[hash_key]

    try:
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
        final_session_id = f"account_{request.phone_number}"

        # Armazena sessão ativa
        active_sessions[final_session_id] = client
        del active_sessions[session_id]
        del active_sessions[hash_key]

        # Registra no PocketBase em background
        background_tasks.add_task(
            register_account_in_pb,
            final_session_id,
            request.phone_number,
            session_string
        )

        return {
            "success": True,
            "session_id": final_session_id,
            "session_string": session_string
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/set-webhook")
async def set_webhook(request: SetWebhookRequest):
    """
    Configura o webhook para uma sessão.
    """
    if request.session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    # TODO: Implementar handler de eventos para esta sessão
    return {"success": True, "message": f"Webhook configurado para {request.session_id}"}


@app.delete("/api/session")
async def delete_session(request: DeleteSessionRequest):
    """
    Remove uma sessão.
    """
    if request.session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")

    client = active_sessions[request.session_id]
    await client.disconnect()
    del active_sessions[request.session_id]

    return {"success": True}


@app.get("/api/sessions")
async def list_sessions():
    """
    Lista sessões ativas.
    """
    return {
        "sessions": [
            {"session_id": sid, "connected": client.is_connected()}
            for sid, client in active_sessions.items()
            if not sid.endswith("_hash")
        ]
    }


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
