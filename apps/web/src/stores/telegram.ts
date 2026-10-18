import { defineStore } from 'pinia'
import { ref } from 'vue'
import { telegramApi, type TelegramSession, type Webhook } from '../services/telegram'
import {
  listMessagesByPbId,
  getSessionPbId,
  groupByChat,
  oldestCreated,
  sortByCreatedAsc,
  type TelegramMessage,
  type ChatGroup,
  type ListMessagesParams,
} from '../services/messages'

/**
 * Estado de paginação de `telegram_messages` por sessão.
 *
 * A paginação é por CURSOR (`created < oldestCreated`), não por offset
 * (`page=N`). Com `-created` + offset, cada mensagem nova que chega
 * desloca as páginas e o usuário pula mensagens ao clicar duas vezes.
 * O cursor é estável mesmo com tráfego chegando.
 */
export interface MessagesPaging {
  perPage: number
  loadedPages: number
  /** `totalItems` reportado pelo PB na primeira página (0 se não vier). */
  totalItems: number
  hasMore: boolean
  loadingMore: boolean
}

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
  // Paginação por session_id — alimenta o botão "carregar mais" da
  // sidebar. Criado no 1º fetch e consumido por `loadMoreMessages`.
  const messagesPaging = ref<Record<string, MessagesPaging>>({})
  const messagesError = ref('')
  // Mapeamento `session.session_id` (texto) → `pb_id` (record id em
  // `telegram_sessions`). Cacheado pra não resolver a cada poll.
  // Necessário pq o filter do PB não suporta `relation.field = value`
  // inline (erro 400) — só equality direto no id do relation
  // (`session = "pb_id"`).
  const sessionPbIds = ref<Record<string, string>>({})

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
      delete sessionPbIds.value[sessionId]
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
   * Resolve `session_id` (texto) → `pb_id` (record id em
   * `telegram_sessions`). Cacheado em `sessionPbIds` pra não bater no
   * PB a cada poll.
   *
   * Necessário pq o filter do PB NÃO suporta
   * `session.session_id = "..."` (relation field inline = erro 400).
   * Só funciona `session = "pb_id"` (relation equality direto).
   */
  async function resolveSessionPbId(sessionId: string): Promise<string> {
    const cached = sessionPbIds.value[sessionId]
    if (cached) return cached
    const pbId = await getSessionPbId(sessionId)
    sessionPbIds.value[sessionId] = pbId
    return pbId
  }

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
      const pbId = await resolveSessionPbId(sessionId)
      const result = await listMessagesByPbId(pbId, params)
      const items = sortByCreatedAsc(result.items)
      messagesBySession.value[sessionId] = items
      chatsBySession.value[sessionId] = groupByChat(items)
      messagesPaging.value[sessionId] = {
        perPage: result.perPage,
        loadedPages: 1,
        totalItems: result.totalItems,
        // Página cheia E com pelo menos uma data real = ainda tem coisa
        // mais antiga. Página cheia só com `created = ''` é o fim da
        // lista (não existe nada mais velho que string vazia).
        hasMore: items.length === result.perPage && items.some((m) => !!m.created),
        loadingMore: false,
      }
      return items
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
      const pbId = await resolveSessionPbId(sessionId)
      const result = await listMessagesByPbId(pbId, {
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
      const merged = sortByCreatedAsc([...existing, ...fresh])
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

  /**
   * Carrega a página imediatamente mais antiga (cursor
   * `created < oldestCreated`), mergeia no cache, dedupe por `id` e
   * recomputa o group-by-chat.
   *
   * Por que isso recupera as conversas que sumiram: registros legados
   * (pré-migration 1792126938) têm `created = ''`, que ordena antes de
   * qualquer data — então eles ficam no FUNDO do `-created` e nunca
   * entram na primeira página. O cursor `created<"..."` caminha até eles
   * e traz o chat de volta.
   *
   * Não mexe no scroll: quem chamou decide (a view preserva o offset).
   */
  async function loadMoreMessages(
    sessionId: string,
    perPage?: number,
  ): Promise<TelegramMessage[]> {
    const existing = messagesBySession.value[sessionId] || []
    const paging = messagesPaging.value[sessionId]
    if (!paging || paging.loadingMore || !paging.hasMore) return existing
    // Serializa com o poll incremental — os dois escrevem no mesmo cache.
    if (messagesInFlight.value[sessionId]) return existing

    const before = oldestCreated(existing)
    if (!before) {
      // Só tem registro legado em cache — não há cursor possível.
      paging.hasMore = false
      return existing
    }
    const size = perPage || paging.perPage
    paging.loadingMore = true
    messagesInFlight.value[sessionId] = true
    try {
      const pbId = await resolveSessionPbId(sessionId)
      const result = await listMessagesByPbId(pbId, { before, perPage: size })
      const known = new Set(existing.map((m) => m.id))
      const fresh = result.items.filter((m) => !known.has(m.id))
      const merged = sortByCreatedAsc([...existing, ...fresh])
      messagesBySession.value[sessionId] = merged
      chatsBySession.value[sessionId] = groupByChat(merged)
      paging.loadedPages += 1
      // Página cheia E com data real = tem mais. Cheia só com `''` = fim.
      paging.hasMore =
        result.items.length === size && result.items.some((m) => !!m.created)
      return merged
    } catch (e: any) {
      messagesError.value = e?.message || 'Erro ao carregar mais mensagens'
      throw e
    } finally {
      paging.loadingMore = false
      delete messagesInFlight.value[sessionId]
    }
  }

  function invalidateMessages(sessionId: string) {
    delete messagesBySession.value[sessionId]
    delete chatsBySession.value[sessionId]
    delete messagesInFlight.value[sessionId]
    delete messagesPaging.value[sessionId]
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
    messagesPaging,
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
    loadMoreMessages,
    invalidateMessages,
  }
})
