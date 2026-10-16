import { defineStore } from 'pinia'
import { ref } from 'vue'
import { telegramApi, type TelegramSession, type Webhook } from '../services/telegram'
import {
  listMessagesBySession,
  groupByChat,
  type TelegramMessage,
  type ChatGroup,
  type ListMessagesParams,
} from '../services/messages'

export const useTelegramStore = defineStore('telegram', () => {
  // Estado
  const sessions = ref<TelegramSession[]>([])
  // webhooks agrupados por session_id — preenche on-demand quando abre
  // a página de webhooks (evita N+1 no dashboard)
  const webhooksBySession = ref<Record<string, Webhook[]>>({})
  const loading = ref(false)
  const error = ref('')

  // Mensagens cacheadas por `session.session_id` (não pb_id). Cada entry
  // é o array completo de mensagens já fetched (full replace, não
  // incremental). O incremental é responsabilidade do caller (poll
  // chama `prependMessages`).
  const messagesBySession = ref<Record<string, TelegramMessage[]>>({})
  // Chats derivados (group-by-chat_id), pré-computados pra evitar
  // recomputar a cada render. Recomputado em `fetchMessages`/
  // `prependMessages`/`invalidateMessages`.
  const chatsBySession = ref<Record<string, ChatGroup[]>>({})
  // Flag `inFlight` por session_id — evita fetch concorrente.
  const messagesInFlight = ref<Record<string, boolean>>({})
  const messagesError = ref('')

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
      invalidateMessages(sessionId)
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

  // =============================================================================
  // Mensagens (telegram_messages collection)
  // =============================================================================

  /**
   * Fetch inicial (ou refresh) de mensagens de uma sessão. Substitui o
   * cache inteiro e recomputa o group-by-chat.
   *
   * Se o caller quiser poll incremental, usa `prependMessages`.
   */
  async function fetchMessages(
    sessionId: string,
    params: ListMessagesParams = {},
  ): Promise<TelegramMessage[]> {
    if (messagesInFlight.value[sessionId]) {
      // Caller concorrente — retorna o que já tem em cache.
      return messagesBySession.value[sessionId] || []
    }
    messagesInFlight.value[sessionId] = true
    messagesError.value = ''
    try {
      const result = await listMessagesBySession(sessionId, params)
      messagesBySession.value[sessionId] = result.items
      chatsBySession.value[sessionId] = groupByChat(result.items)
      return result.items
    } catch (e: any) {
      messagesError.value = e?.message || 'Erro ao buscar mensagens'
      throw e
    } finally {
      delete messagesInFlight.value[sessionId]
    }
  }

  /**
   * Poll incremental: busca mensagens com `created > since` (geralmente
   * o `created` da msg mais recente em cache) e prepend no array.
   * Dedupe por `id`. Recomputa group-by-chat.
   *
   * Se o cache estiver vazio pra essa session, faz fallback pro
   * `fetchMessages` full.
   */
  async function prependMessages(
    sessionId: string,
    options: { since?: string; directionFilter?: ListMessagesParams['directionFilter'] } = {},
  ): Promise<TelegramMessage[]> {
    if (messagesInFlight.value[sessionId]) {
      return messagesBySession.value[sessionId] || []
    }
    const existing = messagesBySession.value[sessionId]
    if (!existing || existing.length === 0) {
      return fetchMessages(sessionId)
    }
    const since = options.since || existing[existing.length - 1]?.created
    if (!since) {
      return existing
    }
    messagesInFlight.value[sessionId] = true
    try {
      const result = await listMessagesBySession(sessionId, {
        since,
        directionFilter: options.directionFilter,
        perPage: 100,
      })
      if (result.items.length === 0) {
        return existing
      }
      const knownIds = new Set(existing.map((m) => m.id))
      const fresh = result.items.filter((m) => !knownIds.has(m.id))
      if (fresh.length === 0) {
        return existing
      }
      const merged = [...existing, ...fresh].sort((a, b) =>
        a.created.localeCompare(b.created),
      )
      messagesBySession.value[sessionId] = merged
      chatsBySession.value[sessionId] = groupByChat(merged)
      return merged
    } catch (e: any) {
      // Poll incremental falhou — não derruba a UI; loga só.
      console.warn('[prependMessages] poll falhou:', e?.message || e)
      return existing
    } finally {
      delete messagesInFlight.value[sessionId]
    }
  }

  function invalidateMessages(sessionId: string) {
    delete messagesBySession.value[sessionId]
    delete chatsBySession.value[sessionId]
    delete messagesInFlight.value[sessionId]
  }

  return {
    sessions,
    webhooksBySession,
    loading,
    error,
    messagesBySession,
    chatsBySession,
    messagesError,
    messagesInFlight,
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
    fetchMessages,
    prependMessages,
    invalidateMessages,
  }
})
