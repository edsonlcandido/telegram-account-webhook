import pb from './pocketbase'

// URL do Telegram API - usa variável de ambiente ou relativa (mesma origem do frontend que é proxyado)
const getTelegramApiUrl = (): string => {
  // Em produção no Easypanel, o PocketBase proxy para /api/*
  if (import.meta.env.PROD) {
    return ''
  }
  // Em dev, usa localhost:8000
  return import.meta.env.VITE_TELEGRAM_API_URL || 'http://localhost:8000'
}

const apiUrl = getTelegramApiUrl()

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

// API Service
export const telegramApi = {
  /**
   * Envia código de verificação para o telefone
   */
  async sendCode(phone: string): Promise<SendCodeResponse> {
    const response = await fetch(`${apiUrl}/api/send-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone_number: phone }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Erro ao enviar código')
    }

    return response.json()
  },

  /**
   * Verifica o código e cria sessão
   */
  async verifyCode(
    phone: string,
    code: string,
    phoneCodeHash: string
  ): Promise<VerifyCodeResponse> {
    const response = await fetch(`${apiUrl}/api/verify-code`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        phone_number: phone,
        code: code,
      }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Erro ao verificar código')
    }

    return response.json()
  },

  /**
   * Lista todas as sessões
   */
  async getSessions(): Promise<{ sessions: TelegramSession[] }> {
    const response = await fetch(`${apiUrl}/api/sessions`)
    
    if (!response.ok) {
      throw new Error('Erro ao buscar sessões')
    }

    return response.json()
  },

  /**
   * Configura webhook para uma sessão
   */
  async setWebhook(sessionId: string, webhookUrl: string): Promise<{ success: boolean; webhook_url: string }> {
    const response = await fetch(`${apiUrl}/api/set-webhook`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        webhook_url: webhookUrl,
      }),
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Erro ao configurar webhook')
    }

    return response.json()
  },

  /**
   * Remove uma sessão
   */
  async deleteSession(sessionId: string): Promise<{ success: boolean }> {
    const response = await fetch(`${apiUrl}/api/session/${sessionId}`, {
      method: 'DELETE',
    })

    if (!response.ok) {
      throw new Error('Erro ao remover sessão')
    }

    return response.json()
  },

  /**
   * Testa um webhook
   */
  async testWebhook(webhookUrl: string): Promise<{ success: boolean; status_code: number }> {
    const response = await fetch(`${apiUrl}/api/test-webhook?webhook_url=${encodeURIComponent(webhookUrl)}`, {
      method: 'POST',
    })

    if (!response.ok) {
      throw new Error('Erro ao testar webhook')
    }

    return response.json()
  },
}
