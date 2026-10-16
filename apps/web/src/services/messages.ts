import pb from './pocketbase'

// =============================================================================
// Tipos
// =============================================================================

export type ChatType = 'private' | 'group' | 'supergroup' | 'channel' | 'unknown'
export type MessageDirection = 'incoming' | 'outgoing'

/**
 * Record de `telegram_messages` (subset do que o PB devolve). Os campos
 * `raw`, `delivered_count`, `delivery_error` são debug-only e ficam fora
 * do type pra não vazar pra UI.
 */
export interface TelegramMessage {
  id: string
  collectionId: string
  collectionName: string
  /** pb_id do record em `telegram_sessions` (relation). */
  session: string
  chat_id: number
  chat_type: ChatType
  chat_title: string
  direction: MessageDirection
  sender_id: number
  sender_name: string
  sender_username: string
  text: string
  /** ISO 8601 (UTC). PB gera no INSERT. */
  created: string
  updated: string
}

export interface ListMessagesParams {
  page?: number
  perPage?: number
  sort?: string
  /** ISO 8601. Se setado, retorna só msgs com `created > since` (poll incremental). */
  since?: string
  /** all | incoming | outgoing */
  directionFilter?: 'all' | MessageDirection
  /** all | private | group | supergroup | channel */
  chatTypeFilter?: 'all' | ChatType
  /** Busca em `text` (LIKE case-insensitive). */
  textSearch?: string
}

export interface ListMessagesResult {
  items: TelegramMessage[]
  page: number
  perPage: number
  totalItems: number
  totalPages: number
}

// =============================================================================
// API
// =============================================================================

/**
 * Resolve o `session_id` textual (tipo "account_5511...") pro `pb_id`
 * (id do record em `telegram_sessions`). Cacheável no caller — 1 request
 * por sessão por sessão de browser.
 *
 * Necessário porque o frontend recebe `session_id` (string amigável) do
 * `telegramStore.sessions`, mas a relation em `telegram_messages` aponta
 * pro `pb_id`. E o filter do PB **não** suporta `session.session_id =
 * "..."` (erro 400) — só equality direto no relation (`session = "pb_id"`).
 */
export async function getSessionPbId(sessionId: string): Promise<string> {
  const result = await pb.collection('telegram_sessions').getList<{
    id: string
    session_id: string
  }>(1, 1, {
    filter: `session_id = "${escapeFilterValue(sessionId)}"`,
  })
  if (result.items.length === 0) {
    throw new Error(`Sessão não encontrada: ${sessionId}`)
  }
  return result.items[0].id
}

/**
 * Lista mensagens da collection `telegram_messages` filtrando pelo
 * `pb_id` da sessão (relation equality: `session = "pb_id"`).
 *
 * Por que pb_id e não session_id: PocketBase não suporta filtro em
 * campo de relation expandida (sintaxe `relation.field = value`) — só
 * equality direto no id do record relacionado. O caller resolve
 * `session_id → pb_id` via `getSessionPbId()` e cacheia.
 *
 * Auth: o `pb` (PocketBase SDK) já injeta o user JWT em todo request
 * via `pb.authStore.token`. A `listRule` da collection é
 * `"@request.auth.id != ''"` (permissiva — qualquer user autenticado lê).
 */
export async function listMessagesByPbId(
  sessionPbId: string,
  params: ListMessagesParams = {},
): Promise<ListMessagesResult> {
  const {
    page = 1,
    perPage = 200,
    sort = '-created',
    since,
    directionFilter = 'all',
    chatTypeFilter = 'all',
    textSearch,
  } = params

  const filterParts: string[] = [
    `session = "${escapeFilterValue(sessionPbId)}"`,
  ]
  if (since) {
    filterParts.push(`created > "${escapeFilterValue(since)}"`)
  }
  if (directionFilter !== 'all') {
    filterParts.push(`direction = "${directionFilter}"`)
  }
  if (chatTypeFilter !== 'all') {
    filterParts.push(`chat_type = "${chatTypeFilter}"`)
  }
  if (textSearch && textSearch.trim()) {
    filterParts.push(`text ~ "${escapeFilterValue(textSearch.trim())}"`)
  }

  const filter = filterParts.join(' && ')

  const result = await pb.collection('telegram_messages').getList<TelegramMessage>(
    page,
    perPage,
    { filter, sort },
  )

  return {
    items: result.items,
    page: result.page,
    perPage: result.perPage,
    totalItems: result.totalItems,
    totalPages: result.totalPages,
  }
}

/**
 * Escapa aspas duplas num valor pra ser seguro dentro de um filter PB.
 * Defense-in-depth: o caller já controla os valores, mas é trivial.
 */
function escapeFilterValue(value: string): string {
  return value.replace(/"/g, '\\"')
}

// =============================================================================
// Grouping
// =============================================================================

export interface ChatGroup {
  chat_id: number
  /** Título mais recente não-vazio. Fallback `#<chat_id>` se nunca teve. */
  chat_title: string
  chat_type: ChatType
  /** Última mensagem do chat (já ordenada por `created` asc internamente). */
  lastMessage: TelegramMessage
  /** Total de mensagens no chat (dentro do range filtrado). */
  count: number
}

/**
 * Agrupa mensagens por `chat_id` e retorna lista de chats ordenada pela
 * mensagem mais recente desc. Adequado pra popular a sidebar estilo
 * Telegram Web.
 */
export function groupByChat(messages: TelegramMessage[]): ChatGroup[] {
  const byChatId = new Map<number, TelegramMessage[]>()
  for (const m of messages) {
    const arr = byChatId.get(m.chat_id)
    if (arr) {
      arr.push(m)
    } else {
      byChatId.set(m.chat_id, [m])
    }
  }

  const groups: ChatGroup[] = []
  for (const msgs of byChatId.values()) {
    msgs.sort((a, b) => a.created.localeCompare(b.created))
    const last = msgs[msgs.length - 1]
    // Pega o título mais recente não-vazio (se o chat mudou de nome).
    let title = ''
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].chat_title && msgs[i].chat_title.trim()) {
        title = msgs[i].chat_title.trim()
        break
      }
    }
    groups.push({
      chat_id: last.chat_id,
      chat_title: title || `#${last.chat_id}`,
      chat_type: last.chat_type,
      lastMessage: last,
      count: msgs.length,
    })
  }

  // Última mensagem desc
  groups.sort((a, b) => b.lastMessage.created.localeCompare(a.lastMessage.created))
  return groups
}

/**
 * Filtra mensagens por `chat_id` e retorna em ordem cronológica asc.
 */
export function messagesForChat(
  messages: TelegramMessage[],
  chatId: number,
): TelegramMessage[] {
  return messages
    .filter((m) => m.chat_id === chatId)
    .sort((a, b) => a.created.localeCompare(b.created))
}
