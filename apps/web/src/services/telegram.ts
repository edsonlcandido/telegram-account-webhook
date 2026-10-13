import pb from './pocketbase'

// URL do backend Telegram API. O frontend chama DIRETO (cross-origin), sem
// passar por hook do PocketBase. O JSVM do PB 0.40.5 tem bug onde
// e.string/e.json perde o body apos chamar $http.send, o que impossibilita
// proxy via hook. CORS no FastAPI ja aceita o dominio publico do frontend.
// Inclui o prefixo /api porque as rotas do FastAPI sao /api/send-code,
// /api/sessions, etc.
const apiUrl = 'https://api-telegram.ehtudo.app/api'

// Tipos
export interface TelegramSession {
  session_id: string
  phone: string
  webhook_url?: string
  active: boolean
  created_at: string
}

export interface SendCodeResponse {
  success: boolean
  session_id: string
  phone_code_hash: string
  expires: number
}

export interface VerifyCodeResponse {
  success: boolean
  session_id: string
  message: string
}

/**
 * Payload do webhook (enviado pelo backend quando chega mensagem Telegram).
 * Inclui campos enriquecidos pra permitir responder via /api/send-message.
 */
export interface WebhookPayload {
  session_id: string
  message_id: number
  chat_id: number
  chat_type: 'private' | 'group' | 'supergroup' | 'channel' | 'unknown'
  chat_title: string | null
  /** true se foi enviada pela própria conta (via celular/desktop/web), false se recebida */
  outgoing: boolean
  text: string
  sender_id: number | null
  sender_name: string | null
  sender_username: string | null
  is_reply: boolean
  reply_to_message_id: number | null
  has_media: boolean
  media_type: string | null
  media_mime_type: string | null
  timestamp: string
}

export interface SendMessageResponse {
  success: boolean
  message_id: number
  chat_id: number
  timestamp: string
  is_reply: boolean
}

// Helper único: injeta o token PB no header `Authorization` em toda chamada.
// O backend valida via dependency `verify_pb_auth` (consulta /auth-refresh
// no PB e cacheia por 5 min).
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string> | undefined),
  }

  if (pb.authStore.token) {
    headers['Authorization'] = pb.authStore.token
  }

  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    let message = `HTTP ${response.status}`
    try {
      const err = await response.json()
      if (err && typeof err.detail === 'string') {
        message = err.detail
      }
    } catch {
      // body não era JSON — mantém a mensagem genérica
    }
    throw new Error(message)
  }

  return (await response.json()) as T
}

// API Service
export const telegramApi = {
  /**
   * Envia código de verificação para o telefone
   */
  async sendCode(phone: string): Promise<SendCodeResponse> {
    return request<SendCodeResponse>('/send-code', {
      method: 'POST',
      body: JSON.stringify({ phone_number: phone }),
    })
  },

  /**
   * Verifica o código e cria sessão
   */
  async verifyCode(phone: string, code: string): Promise<VerifyCodeResponse> {
    return request<VerifyCodeResponse>('/verify-code', {
      method: 'POST',
      body: JSON.stringify({
        phone_number: phone,
        code,
      }),
    })
  },

  /**
   * Lista todas as sessões
   */
  async getSessions(): Promise<{ sessions: TelegramSession[] }> {
    return request<{ sessions: TelegramSession[] }>('/sessions')
  },

  /**
   * Configura webhook para uma sessão
   */
  async setWebhook(sessionId: string, webhookUrl: string): Promise<{ success: boolean; webhook_url: string }> {
    return request<{ success: boolean; webhook_url: string }>('/set-webhook', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        webhook_url: webhookUrl,
      }),
    })
  },

  /**
   * Remove uma sessão
   */
  async deleteSession(sessionId: string): Promise<{ success: boolean }> {
    return request<{ success: boolean }>(`/session/${sessionId}`, {
      method: 'DELETE',
    })
  },

  /**
   * Testa um webhook
   */
  async testWebhook(webhookUrl: string): Promise<{ success: boolean; status: number }> {
    const data = await request<{ success: boolean; status_code: number }>('/test-webhook', {
      method: 'POST',
      body: JSON.stringify({ webhook_url: webhookUrl }),
    })
    return { success: data.success, status: data.status_code }
  },

  /**
   * Envia uma mensagem via uma sessão Telegram.
   * Aceita chat_id numérico ou @username; reply_to_message_id opcional.
   */
  async sendMessage(
    sessionId: string,
    chatId: number | string,
    text: string,
    replyToMessageId?: number,
  ): Promise<SendMessageResponse> {
    return request<SendMessageResponse>('/send-message', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        chat_id: chatId,
        text,
        ...(replyToMessageId ? { reply_to_message_id: replyToMessageId } : {}),
      }),
    })
  },
}