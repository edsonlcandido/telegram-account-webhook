<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50">
    <!-- Navigation -->
    <nav class="bg-white/80 backdrop-blur-lg shadow-lg sticky top-0 z-50 border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          <div class="flex items-center">
            <h1 class="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              Dashboard
            </h1>
          </div>
          <div class="flex items-center gap-4">
            <router-link
              to="/docs"
              class="inline-flex items-center px-3 py-2 text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors"
              title="Documentação da API"
            >
              <svg class="h-5 w-5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Docs
            </router-link>
            <div class="flex items-center gap-3 px-4 py-2 bg-gradient-to-r from-blue-50 to-purple-50 rounded-full">
              <div class="w-8 h-8 bg-gradient-to-r from-blue-600 to-purple-600 rounded-full flex items-center justify-center">
                <UserCircleIcon class="h-5 w-5 text-white" />
              </div>
              <span class="text-sm font-semibold text-gray-700">{{ userName }}</span>
            </div>
            <button
              @click="handleLogout"
              class="group inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg text-white bg-gradient-to-r from-red-500 to-pink-500 hover:from-red-600 hover:to-pink-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 transition-all transform hover:scale-105 shadow-lg"
            >
              <ArrowRightOnRectangleIcon class="h-5 w-5 mr-2 group-hover:translate-x-1 transition-transform" />
              Sair
            </button>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto py-8 sm:px-6 lg:px-8">
      <!-- Welcome Section -->
      <div class="px-4 py-6 sm:px-0">
        <div class="bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 overflow-hidden shadow-2xl rounded-2xl transform hover:scale-[1.02] transition-all">
          <div class="p-8 text-white">
            <div class="flex items-center justify-between">
              <div>
                <h2 class="text-3xl md:text-4xl font-bold mb-3">
                  Olá, {{ userName }}! 👋
                </h2>
                <p class="text-blue-100 text-lg">
                  Gerencie suas contas Telegram e webhooks
                </p>
              </div>
              <div class="hidden md:block">
                <div class="w-24 h-24 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center">
                  <span class="text-6xl">📱</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Stats Grid -->
      <div class="px-4 py-6 sm:px-0">
        <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <!-- Stat Card: Contas -->
          <div class="group bg-white overflow-hidden shadow-xl rounded-2xl hover:shadow-2xl transition-all transform hover:-translate-y-1 border-2 border-transparent hover:border-blue-200">
            <div class="p-6">
              <div class="flex items-center">
                <div class="flex-shrink-0">
                  <div class="w-14 h-14 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg">
                    <svg class="h-7 w-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                    </svg>
                  </div>
                </div>
                <div class="ml-5 w-0 flex-1">
                  <dl>
                    <dt class="text-sm font-medium text-gray-500 truncate mb-1">
                      Contas Telegram
                    </dt>
                    <dd class="text-2xl font-bold text-gray-900">
                      {{ telegramStore.totalSessions() }}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
            <div class="bg-gradient-to-r from-blue-50 to-blue-100 px-6 py-3">
              <p class="text-xs text-blue-700 font-medium">
                {{ telegramStore.activeSessions().length }} ativa(s)
              </p>
            </div>
          </div>

          <!-- Stat Card: Webhooks -->
          <div class="group bg-white overflow-hidden shadow-xl rounded-2xl hover:shadow-2xl transition-all transform hover:-translate-y-1 border-2 border-transparent hover:border-green-200">
            <div class="p-6">
              <div class="flex items-center">
                <div class="flex-shrink-0">
                  <div class="w-14 h-14 bg-gradient-to-br from-green-500 to-green-600 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg">
                    <svg class="h-7 w-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                  </div>
                </div>
                <div class="ml-5 w-0 flex-1">
                  <dl>
                    <dt class="text-sm font-medium text-gray-500 truncate mb-1">
                      Webhooks Config
                    </dt>
                    <dd class="text-2xl font-bold text-gray-900">
                      {{ configuredWebhooks }}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
            <div class="bg-gradient-to-r from-green-50 to-green-100 px-6 py-3">
              <p class="text-xs text-green-700 font-medium">
                {{ telegramStore.sessions.length - configuredWebhooks }} pendente(s)
              </p>
            </div>
          </div>

          <!-- Stat Card: Status -->
          <div class="group bg-white overflow-hidden shadow-xl rounded-2xl hover:shadow-2xl transition-all transform hover:-translate-y-1 border-2 border-transparent hover:border-purple-200">
            <div class="p-6">
              <div class="flex items-center">
                <div class="flex-shrink-0">
                  <div class="w-14 h-14 bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg">
                    <svg class="h-7 w-7 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                </div>
                <div class="ml-5 w-0 flex-1">
                  <dl>
                    <dt class="text-sm font-medium text-gray-500 truncate mb-1">
                      Status
                    </dt>
                    <dd class="text-2xl font-bold text-gray-900">
                      {{ telegramStore.loading ? '...' : 'OK' }}
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
            <div class="bg-gradient-to-r from-purple-50 to-purple-100 px-6 py-3">
              <p class="text-xs text-purple-700 font-medium">
                Sistema {{ telegramStore.error ? '⚠️' : '✓' }} ativo
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Accounts Section -->
      <div class="px-4 py-6 sm:px-0">
        <div class="bg-white shadow-2xl rounded-2xl border border-gray-100">
          <div class="px-6 py-6 border-b border-gray-100 flex items-center justify-between">
            <div>
              <h3 class="text-2xl font-bold text-gray-900 flex items-center">
                <span class="mr-3">📱</span>
                Contas Telegram
              </h3>
              <p class="text-gray-500 text-sm mt-1">Gerencie suas contas vinculadas</p>
            </div>
            <button
              @click="router.push('/add-telegram')"
              class="inline-flex items-center px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-500 text-white font-bold rounded-xl hover:from-blue-600 hover:to-purple-600 transition-all transform hover:scale-105 shadow-lg"
            >
              <PlusIcon class="h-5 w-5 mr-2" />
              Adicionar Conta
            </button>
          </div>

          <!-- Loading -->
          <div v-if="telegramStore.loading && telegramStore.sessions.length === 0" class="p-12 flex justify-center">
            <div class="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          </div>

          <!-- Empty State -->
          <div v-else-if="telegramStore.sessions.length === 0" class="p-12 text-center">
            <div class="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg class="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
            </div>
            <h4 class="text-lg font-semibold text-gray-900 mb-2">Nenhuma conta vinculada</h4>
            <p class="text-gray-500 mb-6">Vincule sua primeira conta Telegram para começar</p>
            <button
              @click="router.push('/add-telegram')"
              class="inline-flex items-center px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-500 text-white font-bold rounded-xl hover:from-blue-600 hover:to-purple-600 transition-all"
            >
              <PlusIcon class="h-5 w-5 mr-2" />
              Adicionar Conta
            </button>
          </div>

          <!-- Accounts List -->
          <div v-else class="divide-y divide-gray-100">
            <div
              v-for="session in telegramStore.sessions"
              :key="session.session_id"
              class="p-6 hover:bg-gray-50 transition-colors"
            >
              <div class="flex items-center justify-between">
                <!-- Account Info -->
                <div class="flex items-center gap-4">
                  <!-- Avatar -->
                  <div class="w-14 h-14 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center text-white text-xl font-bold">
                    {{ session.phone.slice(-4) }}
                  </div>

                  <div>
                    <p class="font-semibold text-gray-900">{{ formatPhone(session.phone) }}</p>
                    <div class="flex items-center gap-2 mt-1">
                      <!-- Status Badge -->
                      <span
                        class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                        :class="session.active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'"
                      >
                        <span class="w-1.5 h-1.5 rounded-full mr-1" :class="session.active ? 'bg-green-500' : 'bg-red-500'"></span>
                        {{ session.active ? 'Online' : 'Offline' }}
                      </span>

                      <!-- Webhook Status -->
                      <span
                        class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                        :class="session.webhook_url ? 'bg-blue-100 text-blue-800' : 'bg-yellow-100 text-yellow-800'"
                      >
                        {{ session.webhook_url ? 'Webhook OK' : 'Sem webhook' }}
                      </span>
                    </div>
                  </div>
                </div>

                <!-- Actions -->
                <div class="flex items-center gap-3">
                  <button
                    @click="router.push(`/webhook/${session.session_id}`)"
                    class="inline-flex items-center px-4 py-2 border border-blue-300 text-blue-600 font-medium rounded-lg hover:bg-blue-50 transition-colors"
                    :title="session.webhook_url ? 'Alterar webhook' : 'Configurar webhook'"
                  >
                    <svg class="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                    Webhook
                  </button>

                  <button
                    @click="openSendModal(session)"
                    class="inline-flex items-center px-4 py-2 border border-green-300 text-green-600 font-medium rounded-lg hover:bg-green-50 transition-colors"
                    :disabled="!session.active"
                    :title="session.active ? 'Enviar mensagem' : 'Sessão offline'"
                    :class="{ 'opacity-50 cursor-not-allowed': !session.active }"
                  >
                    <svg class="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                    Mensagem
                  </button>

                  <button
                    @click="toggleWebhook(session)"
                    :disabled="togglingId === session.session_id || !session.webhook_url"
                    :title="!session.webhook_url
                      ? 'Configure o webhook primeiro'
                      : (session.webhook_enabled ? 'Pausar envio ao webhook' : 'Retomar envio ao webhook')"
                    :class="session.webhook_enabled
                      ? 'border-purple-300 text-purple-600 hover:bg-purple-50'
                      : 'border-orange-300 text-orange-600 hover:bg-orange-50'"
                    class="inline-flex items-center px-4 py-2 border font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <svg v-if="session.webhook_enabled" class="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <svg v-else class="h-4 w-4 mr-2" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                    {{ togglingId === session.session_id ? '...' : (session.webhook_enabled ? 'Pausar' : 'Retomar') }}
                  </button>

                  <button
                    @click="confirmDelete(session)"
                    class="inline-flex items-center px-4 py-2 border border-red-300 text-red-600 font-medium rounded-lg hover:bg-red-50 transition-colors"
                    title="Remover conta"
                  >
                    <svg class="h-4 w-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    Remover
                  </button>
                </div>
              </div>

              <!-- Webhook URL if configured -->
              <div v-if="session.webhook_url" class="mt-3 ml-18">
                <p class="text-xs text-gray-500">
                  <span class="font-medium">Webhook:</span>
                  <code class="ml-2 px-2 py-0.5 bg-gray-100 rounded text-gray-600">{{ session.webhook_url }}</code>
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Error Message -->
      <div v-if="telegramStore.error" class="px-4 py-6 sm:px-0">
        <div class="bg-red-50 border border-red-200 rounded-xl p-4">
          <p class="text-red-700">{{ telegramStore.error }}</p>
          <button @click="telegramStore.fetchSessions()" class="mt-2 text-sm text-red-600 hover:text-red-800 font-medium">
            Tentar novamente
          </button>
        </div>
      </div>
    </main>

    <!-- Delete Confirmation Modal -->
    <Teleport to="body">
      <div v-if="deleteModal.show" class="fixed inset-0 z-50 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <!-- Backdrop -->
          <div class="fixed inset-0 bg-black/50 transition-opacity" @click="deleteModal.show = false"></div>

          <!-- Modal -->
          <div class="relative bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <div class="text-center">
              <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg class="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>

              <h3 class="text-xl font-bold text-gray-900 mb-2">Remover conta?</h3>
              <p class="text-gray-600 mb-6">
                Tem certeza que deseja remover a conta <strong>{{ deleteModal.session?.phone }}</strong>? 
                Esta ação não pode ser desfeita.
              </p>

              <div class="flex gap-4">
                <button
                  @click="deleteModal.show = false"
                  class="flex-1 px-4 py-3 border border-gray-300 text-gray-700 font-medium rounded-xl hover:bg-gray-50 transition-colors"
                >
                  Cancelar
                </button>
                <button
                  @click="executeDelete"
                  :disabled="deleteModal.loading"
                  class="flex-1 px-4 py-3 bg-gradient-to-r from-red-500 to-pink-500 text-white font-medium rounded-xl hover:from-red-600 hover:to-pink-600 disabled:opacity-50 transition-all"
                >
                  {{ deleteModal.loading ? 'Removendo...' : 'Remover' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Send Message Modal -->
    <Teleport to="body">
      <div v-if="sendModal.show" class="fixed inset-0 z-50 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <div class="fixed inset-0 bg-black/50 transition-opacity" @click="closeSendModal"></div>
          <div class="relative bg-white rounded-2xl shadow-xl max-w-lg w-full p-6">
            <h3 class="text-xl font-bold text-gray-900 mb-1">Enviar Mensagem</h3>
            <p class="text-sm text-gray-500 mb-6">
              via {{ sendModal.session?.phone }}
            </p>

            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Chat ID ou @username</label>
                <input
                  v-model="sendModal.chatId"
                  type="text"
                  placeholder="123456789 ou @username"
                  class="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:outline-none"
                  :disabled="sendModal.loading"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Reply to (message_id, opcional)
                </label>
                <input
                  v-model.number="sendModal.replyTo"
                  type="number"
                  placeholder="ex: 12345"
                  class="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:outline-none"
                  :disabled="sendModal.loading"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Mensagem</label>
                <textarea
                  v-model="sendModal.text"
                  rows="4"
                  placeholder="Digite a mensagem..."
                  class="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:outline-none resize-none"
                  :disabled="sendModal.loading"
                ></textarea>
              </div>

              <div
                v-if="sendModal.result"
                class="p-3 rounded-xl"
                :class="sendModal.result.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'"
              >
                <p v-if="sendModal.result.success" class="text-sm text-green-700">
                  ✓ Mensagem enviada (msg #{{ sendModal.result.message_id }})
                </p>
                <p v-else class="text-sm text-red-700">{{ sendModal.result.message }}</p>
              </div>
            </div>

            <div class="flex gap-3 mt-6">
              <button
                @click="closeSendModal"
                class="flex-1 px-4 py-3 border border-gray-300 text-gray-700 font-medium rounded-xl hover:bg-gray-50 transition-colors"
                :disabled="sendModal.loading"
              >
                Cancelar
              </button>
              <button
                @click="executeSend"
                :disabled="!canSend || sendModal.loading"
                class="flex-1 px-4 py-3 bg-gradient-to-r from-blue-500 to-purple-500 text-white font-medium rounded-xl hover:from-blue-600 hover:to-purple-600 disabled:opacity-50 transition-all"
              >
                {{ sendModal.loading ? 'Enviando...' : 'Enviar' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useTelegramStore } from '../stores/telegram'
import { telegramApi, type TelegramSession } from '../services/telegram'
import {
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
  PlusIcon,
} from '@heroicons/vue/24/outline'

const router = useRouter()
const authStore = useAuthStore()
const telegramStore = useTelegramStore()

// User name
const userName = computed(() => {
  return authStore.user?.name || authStore.user?.email || 'Usuário'
})

// Stats
const configuredWebhooks = computed(() => {
  return telegramStore.sessions.filter(s => s.webhook_url).length
})

// Format phone for display
const formatPhone = (phone: string) => {
  const cleaned = phone.replace(/\D/g, '')
  if (cleaned.length === 12) {
    return `(${cleaned.slice(2, 4)}) ${cleaned.slice(4, 9)}-${cleaned.slice(9)}`
  }
  return phone
}

// Delete modal
const deleteModal = reactive({
  show: false,
  session: null as TelegramSession | null,
  loading: false,
})

const confirmDelete = (session: TelegramSession) => {
  deleteModal.session = session
  deleteModal.show = true
}

const executeDelete = async () => {
  if (!deleteModal.session) return

  deleteModal.loading = true
  try {
    await telegramStore.deleteSession(deleteModal.session.session_id)
    deleteModal.show = false
    deleteModal.session = null
  } catch (error) {
    console.error('Erro ao remover sessão:', error)
  } finally {
    deleteModal.loading = false
  }
}

// Toggle webhook dispatch (play/pause) — não mexe na URL, só liga/desliga o envio
const togglingId = ref<string | null>(null)
async function toggleWebhook(session: TelegramSession) {
  togglingId.value = session.session_id
  try {
    await telegramApi.toggleWebhook(session.session_id, !session.webhook_enabled)
    await telegramStore.fetchSessions()
  } catch (error) {
    console.error('Erro ao alternar webhook:', error)
    alert('Erro ao alternar webhook. Tente novamente.')
  } finally {
    togglingId.value = null
  }
}

// Logout
function handleLogout() {
  authStore.logout()
  router.push('/login')
}

// Send message modal
const sendModal = reactive({
  show: false,
  session: null as TelegramSession | null,
  chatId: '',
  text: '',
  replyTo: null as number | null,
  loading: false,
  result: null as { success: boolean; message_id?: number; message?: string } | null,
})

const canSend = computed(() => {
  return sendModal.chatId.trim() !== '' && sendModal.text.trim() !== ''
})

function openSendModal(session: TelegramSession) {
  sendModal.session = session
  sendModal.chatId = ''
  sendModal.text = ''
  sendModal.replyTo = null
  sendModal.result = null
  sendModal.show = true
}

function closeSendModal() {
  if (sendModal.loading) return
  sendModal.show = false
  sendModal.session = null
}

async function executeSend() {
  if (!sendModal.session || !canSend.value) return

  sendModal.loading = true
  sendModal.result = null
  try {
    // chat_id aceita numérico OU @username (string começa com @ ou letras)
    const trimmed = sendModal.chatId.trim()
    const isNumeric = /^\d+$/.test(trimmed)
    const chatId: number | string = isNumeric ? Number(trimmed) : trimmed

    const res = await telegramApi.sendMessage(
      sendModal.session.session_id,
      chatId,
      sendModal.text.trim(),
      sendModal.replyTo ?? undefined,
    )
    sendModal.result = { success: res.success, message_id: res.message_id }
  } catch (error: any) {
    sendModal.result = { success: false, message: error?.message || 'Erro ao enviar' }
  } finally {
    sendModal.loading = false
  }
}

// Load sessions on mount
onMounted(() => {
  telegramStore.fetchSessions()
})
</script>
