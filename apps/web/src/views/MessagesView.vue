<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useTelegramStore } from '../stores/telegram'
import { messagesForChat, type TelegramMessage, type ChatGroup } from '../services/messages'
import { telegramApi } from '../services/telegram'
import {
  ArrowLeftIcon,
  ArrowPathIcon,
  ChatBubbleLeftRightIcon,
  PaperAirplaneIcon,
  PhotoIcon,
  XMarkIcon,
  UserIcon,
  UserGroupIcon,
  MegaphoneIcon,
  QuestionMarkCircleIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps<{ sessionId?: string }>()
const router = useRouter()
const telegramStore = useTelegramStore()

// =============================================================================
// Estado
// =============================================================================

const currentSessionId = ref<string>('')
const selectedChatId = ref<number | null>(null)
const searchText = ref('')
const directionFilter = ref<'all' | 'incoming' | 'outgoing'>('all')
const autoRefresh = ref(true)
const showImageInput = ref(false)
const composerText = ref('')
const composerImageUrl = ref('')
const composerParseMode = ref<'plain' | 'html'>('plain')
const composerSending = ref(false)
const composerError = ref('')
const composerSuccess = ref('')
const messagesListEl = ref<HTMLElement | null>(null)
const refreshLoading = ref(false)

let pollInterval: number | null = null
let visibilityHandler: (() => void) | null = null

// =============================================================================
// Computed
// =============================================================================

const currentSession = computed(() =>
  telegramStore.sessions.find(s => s.session_id === currentSessionId.value),
)

const accountLabel = computed(() => {
  const s = currentSession.value
  if (!s) return ''
  return s.name || formatPhone(s.phone) || s.session_id
})

const allMessages = computed<TelegramMessage[]>(
  () => telegramStore.messagesBySession[currentSessionId.value] || [],
)

const chats = computed<ChatGroup[]>(() => {
  const list = telegramStore.chatsBySession[currentSessionId.value] || []
  let filtered = list
  if (searchText.value.trim()) {
    const q = searchText.value.toLowerCase()
    filtered = filtered.filter(c => c.chat_title.toLowerCase().includes(q))
  }
  if (directionFilter.value !== 'all') {
    const all = allMessages.value
    const dir = directionFilter.value
    filtered = filtered.filter(c =>
      all.some(m => m.chat_id === c.chat_id && m.direction === dir),
    )
  }
  return filtered
})

const chatMessages = computed<TelegramMessage[]>(() => {
  if (selectedChatId.value === null) return []
  const dir = directionFilter.value
  return messagesForChat(allMessages.value, selectedChatId.value)
    .filter(m => dir === 'all' || m.direction === dir)
})

const selectedChat = computed<ChatGroup | null>(() => {
  if (selectedChatId.value === null) return null
  return (telegramStore.chatsBySession[currentSessionId.value] || [])
    .find(c => c.chat_id === selectedChatId.value) || null
})

const canSend = computed(() => {
  if (selectedChatId.value === null) return false
  const hasText = composerText.value.trim() !== ''
  const hasImage = composerImageUrl.value.trim() !== ''
  return (hasText || hasImage) && !composerSending.value
})

// =============================================================================
// Lifecycle
// =============================================================================

onMounted(async () => {
  if (telegramStore.sessions.length === 0) {
    await telegramStore.fetchSessions()
  }
  resolveSession()
  if (currentSessionId.value) {
    await loadMessages(true)
  }
  startAutoRefresh()
})

onUnmounted(() => {
  stopAutoRefresh()
})

watch(
  () => props.sessionId,
  () => {
    resolveSession()
    if (currentSessionId.value) {
      void loadMessages(true)
    } else {
      selectedChatId.value = null
    }
  },
)

watch(autoRefresh, () => {
  if (autoRefresh.value) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

// =============================================================================
// Session / messages
// =============================================================================

function resolveSession() {
  const wanted = props.sessionId
  if (wanted && telegramStore.sessions.find(s => s.session_id === wanted)) {
    currentSessionId.value = wanted
    return
  }
  const active = telegramStore.activeSessions()
  if (active.length > 0) {
    currentSessionId.value = active[0].session_id
  } else if (telegramStore.sessions.length > 0) {
    currentSessionId.value = telegramStore.sessions[0].session_id
  } else {
    currentSessionId.value = ''
  }
}

async function loadMessages(force: boolean) {
  if (!currentSessionId.value) return
  if (force) {
    telegramStore.invalidateMessages(currentSessionId.value)
  }
  refreshLoading.value = true
  try {
    await telegramStore.fetchMessages(currentSessionId.value, { perPage: 200 })
    selectedChatId.value = null
  } catch {
    // erro fica em telegramStore.messagesError
  } finally {
    refreshLoading.value = false
  }
  scrollMessagesToBottom()
}

async function pollOnce() {
  if (!currentSessionId.value) return
  if (telegramStore.messagesInFlight[currentSessionId.value]) return
  await telegramStore.prependMessages(currentSessionId.value)
  scrollMessagesToBottom()
}

// =============================================================================
// Auto-refresh
// =============================================================================

function startAutoRefresh() {
  stopAutoRefresh()
  if (!autoRefresh.value) return
  pollInterval = window.setInterval(() => {
    if (document.visibilityState !== 'visible') return
    if (!autoRefresh.value) return
    void pollOnce()
  }, 15000)
  visibilityHandler = () => {
    if (document.visibilityState === 'visible' && autoRefresh.value) {
      void pollOnce()
    }
  }
  document.addEventListener('visibilitychange', visibilityHandler)
}

function stopAutoRefresh() {
  if (pollInterval !== null) {
    window.clearInterval(pollInterval)
    pollInterval = null
  }
  if (visibilityHandler) {
    document.removeEventListener('visibilitychange', visibilityHandler)
    visibilityHandler = null
  }
}

// =============================================================================
// Chat selection
// =============================================================================

function selectChat(chat: ChatGroup) {
  selectedChatId.value = chat.chat_id
  composerText.value = ''
  composerImageUrl.value = ''
  composerParseMode.value = 'plain'
  showImageInput.value = false
  composerError.value = ''
  composerSuccess.value = ''
  scrollMessagesToBottom()
}

// =============================================================================
// Composer / send
// =============================================================================

async function sendMessage() {
  if (!canSend.value || selectedChatId.value === null) return
  const chatId = selectedChatId.value
  const text = composerText.value.trim()
  const imageUrl = composerImageUrl.value.trim()
  const parseMode = composerParseMode.value

  composerSending.value = true
  composerError.value = ''
  composerSuccess.value = ''

  try {
    await telegramApi.sendMessage({
      session_id: currentSessionId.value,
      chat_id: chatId,
      text: text || undefined,
      parse_mode: parseMode,
      image_url: imageUrl || undefined,
    })
    composerText.value = ''
    composerImageUrl.value = ''
    showImageInput.value = false
    composerSuccess.value = 'Mensagem enviada! Vai aparecer aqui no próximo refresh.'
    // Refresh imediato (handler do Telethon grava no PB em ~100-500ms)
    setTimeout(() => {
      void pollOnce()
    }, 800)
  } catch (e) {
    const err = e as { message?: string }
    composerError.value = err?.message || 'Erro ao enviar mensagem'
  } finally {
    composerSending.value = false
  }
}

// =============================================================================
// Helpers
// =============================================================================

function formatPhone(phone: string): string {
  const cleaned = phone.replace(/\D/g, '')
  if (cleaned.length === 12) {
    return `(${cleaned.slice(2, 4)}) ${cleaned.slice(4, 9)}-${cleaned.slice(9)}`
  }
  if (cleaned.length === 13) {
    return `+${cleaned.slice(0, 2)} (${cleaned.slice(2, 4)}) ${cleaned.slice(4, 9)}-${cleaned.slice(9)}`
  }
  return phone
}

function formatRelative(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const sec = Math.floor(diffMs / 1000)
  if (sec < 60) return 'agora'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}min`
  const h = Math.floor(min / 60)
  if (h < 24) return `${h}h`
  const days = Math.floor(h / 24)
  if (days === 1) return 'ontem'
  if (days < 7) return `${days}d`
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

function formatTimestamp(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  return d.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function scrollMessagesToBottom() {
  // Espera Vue renderizar a nova lista antes de scrollar
  setTimeout(() => {
    if (messagesListEl.value) {
      messagesListEl.value.scrollTop = messagesListEl.value.scrollHeight
    }
  }, 60)
}

function chatTypeIcon(type: string) {
  switch (type) {
    case 'private':
      return UserIcon
    case 'group':
    case 'supergroup':
      return UserGroupIcon
    case 'channel':
      return MegaphoneIcon
    default:
      return QuestionMarkCircleIcon
  }
}

function chatTypeLabel(type: string): string {
  switch (type) {
    case 'private':
      return 'Privado'
    case 'group':
      return 'Grupo'
    case 'supergroup':
      return 'Supergrupo'
    case 'channel':
      return 'Canal'
    default:
      return 'Desconhecido'
  }
}

function goBack() {
  router.push('/dashboard')
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50 flex flex-col">
    <!-- Header -->
    <nav class="bg-white/80 backdrop-blur-lg shadow-lg sticky top-0 z-50 border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16 gap-2">
          <div class="flex items-center gap-3 min-w-0">
            <button
              @click="goBack"
              class="flex items-center text-gray-600 hover:text-gray-900 flex-shrink-0"
            >
              <ArrowLeftIcon class="w-5 h-5" />
              <span class="ml-1 font-semibold hidden sm:inline">Voltar</span>
            </button>
            <span class="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent truncate">
              Mensagens
            </span>
            <span v-if="accountLabel" class="text-sm text-gray-600 truncate hidden md:inline">
              · {{ accountLabel }}
            </span>
          </div>
          <div class="flex items-center gap-2">
            <select
              v-if="telegramStore.sessions.length > 1"
              v-model="currentSessionId"
              class="px-2 py-1.5 text-sm border border-gray-300 rounded-lg bg-white max-w-[180px]"
              @change="loadMessages(true)"
            >
              <option
                v-for="s in telegramStore.sessions"
                :key="s.session_id"
                :value="s.session_id"
              >
                {{ s.name || formatPhone(s.phone) || s.session_id }}
              </option>
            </select>
            <button
              @click="loadMessages(true)"
              :disabled="refreshLoading || !currentSessionId"
              class="inline-flex items-center px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              title="Atualizar agora"
            >
              <ArrowPathIcon
                class="h-4 w-4"
                :class="{ 'animate-spin': refreshLoading }"
              />
            </button>
          </div>
        </div>
      </div>
    </nav>

    <!-- Empty state: sem conta -->
    <main
      v-if="!currentSessionId"
      class="flex-1 flex items-center justify-center p-4"
    >
      <div class="bg-white rounded-2xl shadow-xl p-12 text-center max-w-md">
        <div class="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <ChatBubbleLeftRightIcon class="w-10 h-10 text-gray-400" />
        </div>
        <h4 class="text-lg font-semibold text-gray-900 mb-2">
          Nenhuma conta Telegram
        </h4>
        <p class="text-gray-500 mb-6">
          Adicione uma conta pra começar a ver as mensagens.
        </p>
        <button
          @click="router.push('/add-telegram')"
          class="inline-flex items-center px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-500 text-white font-bold rounded-xl hover:from-blue-600 hover:to-purple-600"
        >
          Adicionar conta
        </button>
      </div>
    </main>

    <!-- Layout principal: sidebar + painel -->
    <main
      v-else
      class="flex-1 max-w-7xl w-full mx-auto p-2 sm:p-4"
    >
      <div
        class="bg-white rounded-2xl shadow-xl overflow-hidden grid grid-cols-1 md:grid-cols-[320px_1fr] h-[calc(100vh-7rem)] min-h-[500px]"
      >
        <!-- Sidebar: lista de chats -->
        <aside class="border-r border-gray-200 flex flex-col min-h-0">
          <div class="p-3 border-b border-gray-200 space-y-2">
            <input
              v-model="searchText"
              type="text"
              placeholder="Buscar chat..."
              class="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:border-blue-500 focus:outline-none"
            />
            <div class="flex gap-1">
              <button
                v-for="opt in (['all', 'incoming', 'outgoing'] as const)"
                :key="opt"
                @click="directionFilter = opt"
                class="flex-1 px-2 py-1 text-xs font-medium rounded-md transition-colors"
                :class="directionFilter === opt ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'"
              >
                {{
                  opt === 'all'
                    ? 'Todas'
                    : opt === 'incoming'
                      ? 'Recebidas'
                      : 'Enviadas'
                }}
              </button>
            </div>
          </div>

          <div class="flex-1 overflow-y-auto">
            <div
              v-if="chats.length === 0"
              class="p-6 text-center text-sm text-gray-500"
            >
              <p v-if="refreshLoading">Carregando...</p>
              <p v-else-if="searchText">Nenhum chat encontrado.</p>
              <p v-else>Nenhuma mensagem ainda.</p>
            </div>
            <button
              v-for="chat in chats"
              :key="chat.chat_id"
              @click="selectChat(chat)"
              class="w-full px-3 py-3 flex items-start gap-2 hover:bg-gray-50 text-left border-b border-gray-100"
              :class="{ 'bg-blue-50': selectedChatId === chat.chat_id }"
            >
              <div
                class="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center flex-shrink-0 text-white"
              >
                <component
                  :is="chatTypeIcon(chat.chat_type)"
                  class="h-5 w-5"
                />
              </div>
              <div class="min-w-0 flex-1">
                <div class="flex items-baseline justify-between gap-2">
                  <p class="font-semibold text-sm text-gray-900 truncate">
                    {{ chat.chat_title }}
                  </p>
                  <span class="text-xs text-gray-400 flex-shrink-0">
                    {{ formatRelative(chat.lastMessage.created) }}
                  </span>
                </div>
                <p class="text-xs text-gray-500 truncate mt-0.5">
                  <span
                    v-if="chat.lastMessage.direction === 'outgoing'"
                    class="text-blue-600"
                  >Você: </span>
                  {{ chat.lastMessage.text || '(sem texto)' }}
                </p>
                <div class="flex items-center gap-2 mt-0.5">
                  <span
                    class="text-[10px] text-gray-400 uppercase tracking-wide"
                  >
                    {{ chatTypeLabel(chat.chat_type) }}
                  </span>
                  <span
                    v-if="chat.count > 1"
                    class="text-[10px] bg-gray-200 text-gray-600 px-1.5 rounded-full"
                  >
                    {{ chat.count }}
                  </span>
                </div>
              </div>
            </button>
          </div>

          <div
            class="px-3 py-2 border-t border-gray-200 flex items-center justify-between text-xs text-gray-500"
          >
            <span>
              {{ chats.length }} {{ chats.length === 1 ? 'chat' : 'chats' }}
            </span>
            <label class="flex items-center gap-1 cursor-pointer select-none">
              <input
                v-model="autoRefresh"
                type="checkbox"
                class="w-3 h-3"
              />
              <span>Auto-refresh</span>
            </label>
          </div>
        </aside>

        <!-- Painel principal -->
        <section class="flex flex-col min-h-0">
          <div
            v-if="!selectedChat"
            class="flex-1 flex items-center justify-center text-center p-6"
          >
            <div>
              <ChatBubbleLeftRightIcon class="h-16 w-16 text-gray-300 mx-auto mb-3" />
              <p class="text-gray-500">
                Selecione um chat à esquerda pra ver as mensagens.
              </p>
            </div>
          </div>

          <template v-else>
            <!-- Header do chat -->
            <div
              class="px-4 py-3 border-b border-gray-200 flex items-center gap-3"
            >
              <div
                class="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center flex-shrink-0 text-white"
              >
                <component
                  :is="chatTypeIcon(selectedChat.chat_type)"
                  class="h-5 w-5"
                />
              </div>
              <div class="min-w-0 flex-1">
                <h2 class="font-semibold text-gray-900 truncate">
                  {{ selectedChat.chat_title }}
                </h2>
                <p class="text-xs text-gray-500">
                  {{ chatTypeLabel(selectedChat.chat_type) }} ·
                  {{ selectedChat.count }} mensagens
                </p>
              </div>
            </div>

            <!-- Lista de mensagens -->
            <div
              ref="messagesListEl"
              class="flex-1 overflow-y-auto p-4 space-y-2 bg-gray-50"
            >
              <div
                v-if="chatMessages.length === 0"
                class="text-center text-sm text-gray-500 py-8"
              >
                Nenhuma mensagem neste chat.
              </div>
              <div
                v-for="msg in chatMessages"
                :key="msg.id"
                class="flex"
                :class="msg.direction === 'outgoing' ? 'justify-end' : 'justify-start'"
              >
                <div
                  class="max-w-[75%] rounded-2xl px-4 py-2 shadow-sm"
                  :class="msg.direction === 'outgoing'
                    ? 'bg-gradient-to-br from-blue-500 to-purple-500 text-white'
                    : 'bg-white text-gray-900 border border-gray-200'"
                >
                  <p
                    v-if="msg.direction === 'incoming' && msg.sender_name"
                    class="text-xs font-semibold mb-1 text-blue-600"
                  >
                    {{ msg.sender_name }}
                  </p>
                  <p class="text-sm whitespace-pre-wrap break-words">
                    {{ msg.text || '(sem texto)' }}
                  </p>
                  <p
                    class="text-[10px] mt-1"
                    :class="msg.direction === 'outgoing' ? 'text-blue-100' : 'text-gray-400'"
                  >
                    {{ formatTimestamp(msg.created) }}
                  </p>
                </div>
              </div>
            </div>

            <!-- Composer -->
            <div class="border-t border-gray-200 p-3 bg-white space-y-2">
              <div
                v-if="composerError"
                class="p-2 bg-red-50 border border-red-200 rounded-lg"
              >
                <p class="text-xs text-red-700">{{ composerError }}</p>
              </div>
              <div
                v-if="composerSuccess"
                class="p-2 bg-green-50 border border-green-200 rounded-lg"
              >
                <p class="text-xs text-green-700">{{ composerSuccess }}</p>
              </div>
              <div v-if="showImageInput" class="flex items-center gap-2">
                <input
                  v-model="composerImageUrl"
                  type="url"
                  placeholder="https://exemplo.com/foto.jpg"
                  class="flex-1 px-3 py-1.5 text-sm border border-gray-200 rounded-lg focus:border-blue-500 focus:outline-none"
                  :disabled="composerSending"
                />
                <button
                  @click="showImageInput = false; composerImageUrl = ''"
                  class="p-1 text-gray-400 hover:text-gray-600"
                  :disabled="composerSending"
                  title="Remover imagem"
                >
                  <XMarkIcon class="h-4 w-4" />
                </button>
              </div>
              <div class="flex items-end gap-2">
                <button
                  @click="showImageInput = !showImageInput"
                  class="p-2 text-gray-500 hover:text-blue-600 rounded-lg flex-shrink-0"
                  :class="{ 'text-blue-600 bg-blue-50': showImageInput }"
                  :disabled="composerSending"
                  title="Anexar imagem (URL)"
                >
                  <PhotoIcon class="h-5 w-5" />
                </button>
                <textarea
                  v-model="composerText"
                  rows="1"
                  :placeholder="composerImageUrl
                    ? 'Caption (opcional)...'
                    : 'Digite uma mensagem...'"
                  class="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:border-blue-500 focus:outline-none resize-none max-h-32"
                  :disabled="composerSending"
                  @keydown.enter.exact.prevent="sendMessage"
                ></textarea>
                <select
                  v-model="composerParseMode"
                  class="px-2 py-2 text-xs border border-gray-200 rounded-lg bg-white flex-shrink-0"
                  :disabled="composerSending"
                >
                  <option value="plain">Texto</option>
                  <option value="html">HTML</option>
                </select>
                <button
                  @click="sendMessage"
                  :disabled="!canSend"
                  class="px-3 py-2 bg-gradient-to-r from-blue-500 to-purple-500 text-white font-medium rounded-lg hover:from-blue-600 hover:to-purple-600 disabled:opacity-50 flex-shrink-0"
                  title="Enviar"
                >
                  <PaperAirplaneIcon class="h-4 w-4" />
                </button>
              </div>
              <p
                v-if="composerParseMode === 'html'"
                class="text-[10px] text-gray-500"
              >
                Tags aceitas: &lt;b&gt;, &lt;i&gt;, &lt;u&gt;, &lt;s&gt;,
                &lt;code&gt;, &lt;pre&gt;, &lt;a href="..."&gt;.
              </p>
            </div>
          </template>
        </section>
      </div>
    </main>

    <div
      v-if="telegramStore.messagesError"
      class="max-w-7xl w-full mx-auto px-4 pb-4"
    >
      <div class="bg-red-50 border border-red-200 rounded-xl p-3">
        <p class="text-red-700 text-sm">{{ telegramStore.messagesError }}</p>
      </div>
    </div>
  </div>
</template>
