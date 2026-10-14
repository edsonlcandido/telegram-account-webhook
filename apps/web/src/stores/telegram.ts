import { defineStore } from 'pinia'
import { ref } from 'vue'
import { telegramApi, type TelegramSession, type Webhook } from '../services/telegram'

export const useTelegramStore = defineStore('telegram', () => {
  // Estado
  const sessions = ref<TelegramSession[]>([])
  // webhooks agrupados por session_id — preenche on-demand quando abre
  // a página de webhooks (evita N+1 no dashboard)
  const webhooksBySession = ref<Record<string, Webhook[]>>({})
  const loading = ref(false)
  const error = ref('')

  // Getters
  const activeSessions = () => sessions.value.filter(s => s.active)
  const totalSessions = () => sessions.value.length

  // Ações
  async function fetchSessions() {
    loading.value = true
    error.value = ''

    try {
      const result = await telegramApi.getSessions()
      sessions.value = result.sessions
    } catch (e: any) {
      error.value = e.message
      console.error('Erro ao buscar sessões:', e)
    } finally {
      loading.value = false
    }
  }

  async function deleteSession(sessionId: string) {
    loading.value = true
    error.value = ''

    try {
      await telegramApi.deleteSession(sessionId)
      sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
      delete webhooksBySession.value[sessionId]
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  /** Atualiza o nome (alias) da sessão, tanto no PB quanto no state local. */
  async function setSessionName(sessionId: string, name: string) {
    try {
      await telegramApi.updateSessionName(sessionId, name)
      const s = sessions.value.find(s => s.session_id === sessionId)
      if (s) s.name = name
    } catch (e: any) {
      error.value = e.message
      throw e
    }
  }

  /** Busca e cacheia os webhooks da sessão. */
  async function fetchWebhooks(sessionId: string) {
    const res = await telegramApi.getWebhooks(sessionId)
    webhooksBySession.value[sessionId] = res.webhooks
    return res.webhooks
  }

  function invalidateWebhooks(sessionId: string) {
    delete webhooksBySession.value[sessionId]
  }

  async function createWebhook(sessionId: string, input: Parameters<typeof telegramApi.createWebhook>[1]) {
    const wh = await telegramApi.createWebhook(sessionId, input)
    invalidateWebhooks(sessionId)
    return wh
  }

  async function updateWebhook(webhookId: string, sessionId: string, input: Parameters<typeof telegramApi.updateWebhook>[1]) {
    const wh = await telegramApi.updateWebhook(webhookId, input)
    invalidateWebhooks(sessionId)
    return wh
  }

  async function deleteWebhook(webhookId: string, sessionId: string) {
    await telegramApi.deleteWebhook(webhookId)
    invalidateWebhooks(sessionId)
  }

  async function toggleWebhook(webhookId: string, sessionId: string, enabled: boolean) {
    const wh = await telegramApi.toggleWebhook(webhookId, enabled)
    invalidateWebhooks(sessionId)
    return wh
  }

  return {
    sessions,
    webhooksBySession,
    loading,
    error,
    activeSessions,
    totalSessions,
    fetchSessions,
    deleteSession,
    setSessionName,
    fetchWebhooks,
    invalidateWebhooks,
    createWebhook,
    updateWebhook,
    deleteWebhook,
    toggleWebhook,
  }
})
