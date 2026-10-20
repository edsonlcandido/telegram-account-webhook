import pb from './pocketbase'

// URL do backend Telegram API. O frontend chama DIRETO (cross-origin), sem
// passar por hook do PocketBase. O JSVM do PB 0.40.5 tem bug onde
// e.string/e.json perde o body apos chamar $http.send, o que impossibilita
// proxy via hook. CORS no FastAPI ja aceita o dominio publico do frontend.
// Inclui o prefixo /api porque as rotas do FastAPI sao /api/send-code,
// /api/sessions, etc.
const apiUrl = 'https://api-telegram.ehtudo.app/api'

// =============================================================================
// Tipos
// =============================================================================

export interface TelegramSession {
  session_id: string
  phone: string
  /** Alias amigável definido pelo usuário. Vazio = UI cai pro telefone. */
  name: string
  active: boolean
  created_at: string
  /** Número de webhooks ativos dessa sessão (precomputed no backend). */
  webhook_count: number
}

export type FilterDirection = 'all' | 'incoming' | 'outgoing'
export type FilterChatType = 'all' | 'private' | 'group' | 'supergroup' | 'channel'
export type FilterTextMatchOperator = 'none' | 'equals' | 'contains'

export interface Webhook {
  id: string
  session_id: string
  name: string
  url: string
  enabled: boolean
  filter_direction: FilterDirection
  filter_chat_type: FilterChatType
  filter_text_match_operator: FilterTextMatchOperator
  filter_text_match_value: string
  created: string
  updated: string
}

export interface CreateWebhookInput {
  name?: string
  url: string
  enabled?: boolean
  filter_direction?: FilterDirection
  filter_chat_type?: FilterChatType
  filter_text_match_operator?: FilterTextMatchOperator
  filter_text_match_value?: string
}

export interface UpdateWebhookInput {
  name?: string
  url?: string
  enabled?: boolean
  filter_direction?: FilterDirection
  filter_chat_type?: FilterChatType
  filter_text_match_operator?: FilterTextMatchOperator
  filter_text_match_value?: string
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

export interface SendMessageResponse {
  success: boolean
  message_id: number
  chat_id: number
  timestamp: string
  is_reply: boolean
  parse_mode: ParseMode | null
  has_media: boolean
  media_type: string | null
}

export type ParseMode = 'plain' | 'html'

/**
 * Resposta do POST /api/integration-token.
 *
 * O `token` é um JWT do PocketBase gerado via endpoint `impersonate` — estático
 * (não renova, não tem revogação individual) e de escopo equivalente ao do
 * usuário que o gerou. `expires_at` é epoch em SEGUNDOS (claim `exp` do JWT).
 */
export interface IntegrationTokenResponse {
  success: boolean
  token: string
  /** Epoch em segundos. 0 = o backend não conseguiu ler o `exp`. */
  expires_at: number
  /** Duração efetivamente aplicada, em segundos (já com clamp do servidor). */
  duration: number
  user: {
    id: string
    email: string
  }
}

/** Body do POST /api/integration-token. */
export interface IntegrationTokenInput {
  /** Validade em segundos. Ausente = default do servidor (30 dias). */
  duration?: number
}

/**
 * Body do POST /api/send-message.
 *
 * `text` e `image_url` são mutuamente complementares: o endpoint aceita
 * (a) só texto, (b) só imagem, (c) imagem com caption. Mandar os dois
 * ausentes retorna 400.
 */
export interface SendMessageInput {
  session_id: string
  chat_id: number | string
  text?: string
  parse_mode?: ParseMode
  image_url?: string
  reply_to_message_id?: number
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

// =============================================================================
// HTTP helper
// =============================================================================

/** Helper único: injeta o token PB no header `Authorization` em toda chamada. */
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
    let code = ''
    try {
      const err = await response.json()
      const detail = err?.detail
      if (typeof detail === 'string') {
        message = detail
      } else if (detail && typeof detail === 'object') {
        // Erro estruturado: { detail: { error, message } }
        // `error` = código estável (ex: "two_factor_required") que o caller
        // usa pra decidir o próximo passo; `message` = texto pro usuário.
        if (typeof detail.message === 'string') message = detail.message
        if (typeof detail.error === 'string') code = detail.error
      }
    } catch {
      // body não era JSON — mantém a mensagem genérica
    }
    const error = new Error(message) as Error & { code?: string }
    if (code) error.code = code
    throw error
  }

  return (await response.json()) as T
}

// =============================================================================
// API
// =============================================================================

export const telegramApi = {
  // ---- Sessões ----
  async sendCode(phone: string): Promise<SendCodeResponse> {
    return request<SendCodeResponse>('/send-code', {
      method: 'POST',
      body: JSON.stringify({ phone_number: phone }),
    })
  },

  async verifyCode(
    phone: string,
    code: string,
    name?: string,
    password?: string,
  ): Promise<VerifyCodeResponse> {
    return request<VerifyCodeResponse>('/verify-code', {
      method: 'POST',
      body: JSON.stringify({
        phone_number: phone,
        code,
        name: name || undefined,
        // Só enviado quando a conta tem 2FA (o backend responde
        // `two_factor_required` na 1ª tentativa).
        password: password || undefined,
      }),
    })
  },

  async getSessions(): Promise<{ sessions: TelegramSession[] }> {
    return request<{ sessions: TelegramSession[] }>('/sessions')
  },

  async updateSessionName(sessionId: string, name: string): Promise<unknown> {
    return request(`/sessions/${sessionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ name }),
    })
  },

  async deleteSession(sessionId: string): Promise<{ success: boolean }> {
    return request<{ success: boolean }>(`/session/${sessionId}`, {
      method: 'DELETE',
    })
  },

  // ---- Webhooks ----
  async getWebhooks(sessionId: string): Promise<{ webhooks: Webhook[] }> {
    return request<{ webhooks: Webhook[] }>(`/sessions/${sessionId}/webhooks`)
  },

  async createWebhook(sessionId: string, input: CreateWebhookInput): Promise<Webhook> {
    return request<Webhook>(`/sessions/${sessionId}/webhooks`, {
      method: 'POST',
      body: JSON.stringify({
        enabled: true,
        filter_direction: 'all',
        filter_chat_type: 'all',
        filter_text_match_operator: 'none',
        filter_text_match_value: '',
        ...input,
      }),
    })
  },

  async updateWebhook(webhookId: string, input: UpdateWebhookInput): Promise<Webhook> {
    return request<Webhook>(`/webhooks/${webhookId}`, {
      method: 'PATCH',
      body: JSON.stringify(input),
    })
  },

  async deleteWebhook(webhookId: string): Promise<{ success: boolean }> {
    return request<{ success: boolean }>(`/webhooks/${webhookId}`, {
      method: 'DELETE',
    })
  },

  async toggleWebhook(webhookId: string, enabled: boolean): Promise<Webhook> {
    return request<Webhook>(`/webhooks/${webhookId}/toggle`, {
      method: 'POST',
      body: JSON.stringify({ enabled }),
    })
  },

  async testWebhook(webhookId: string): Promise<{ success: boolean; status_code: number }> {
    const data = await request<{ success: boolean; status_code: number }>(
      `/webhooks/${webhookId}/test`,
      { method: 'POST' },
    )
    return { success: data.success, status_code: data.status_code }
  },

  async refreshWebhookCache(): Promise<{ success: boolean }> {
    return request<{ success: boolean }>('/webhooks/refresh-cache', {
      method: 'POST',
    })
  },

  // ---- Mensagens ----
  async sendMessage(input: SendMessageInput): Promise<SendMessageResponse> {
    return request<SendMessageResponse>('/send-message', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  },

  // ---- Token de integração ----
  /**
   * Gera um token do PocketBase pro usuário logado, pra usar como
   * `Authorization: <token>` em OUTRO sistema (n8n, Make, backend próprio)
   * ao chamar o `/api/send-message`.
   *
   * O token é exibido uma única vez e não é persistido em lugar nenhum —
   * nem no PB, nem no navegador. Se a página recarregar, ele se perde.
   */
  async createIntegrationToken(
    input: IntegrationTokenInput = {},
  ): Promise<IntegrationTokenResponse> {
    return request<IntegrationTokenResponse>('/integration-token', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  },
}
