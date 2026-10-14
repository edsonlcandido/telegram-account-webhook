<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useTelegramStore } from '../stores/telegram'
import { telegramApi, type Webhook, type CreateWebhookInput, type UpdateWebhookInput, type FilterDirection, type FilterChatType, type FilterTextMatchOperator } from '../services/telegram'

const router = useRouter()
const telegramStore = useTelegramStore()

// Path param: /webhooks/:sessionId
const props = defineProps<{ sessionId: string }>()

// Estado
const webhooks = ref<Webhook[]>([])
const loading = ref(false)
const error = ref('')

// Sessão atual (cruza store local com fetch)
const currentSession = computed(() =>
  telegramStore.sessions.find(s => s.session_id === props.sessionId),
)

const accountLabel = computed(() => {
  if (currentSession.value?.name) return currentSession.value.name
  return formatPhone(currentSession.value?.phone || props.sessionId)
})

// Modal de criar/editar
interface FormState {
  open: boolean
  webhookId: string | null
  name: string
  url: string
  enabled: boolean
  filter_direction: FilterDirection
  filter_chat_type: FilterChatType
  filter_text_match_operator: FilterTextMatchOperator
  filter_text_match_value: string
  saving: boolean
  testing: boolean
  testResult: { ok: boolean; status: number } | null
}
const form = reactive<FormState>({
  open: false,
  webhookId: null,
  name: '',
  url: '',
  enabled: true,
  filter_direction: 'all',
  filter_chat_type: 'all',
  filter_text_match_operator: 'none',
  filter_text_match_value: '',
  saving: false,
  testing: false,
  testResult: null,
})

// Modal de confirmar remover
const confirmRemove = reactive<{
  show: boolean
  webhook: Webhook | null
  loading: boolean
}>({ show: false, webhook: null, loading: false })

// Toggle (pausar/retomar) — id da webhook sendo alternada
const togglingId = ref<string | null>(null)

// =============================================================================
// Lifecycle
// =============================================================================

onMounted(async () => {
  if (!props.sessionId) {
    router.push('/dashboard')
    return
  }
  // Garante que o store tem as sessions (caso o user tenha deep-link)
  if (telegramStore.sessions.length === 0) {
    await telegramStore.fetchSessions()
  }
  await refresh()
})

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    webhooks.value = await telegramStore.fetchWebhooks(props.sessionId)
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// =============================================================================
// Helpers de UI
// =============================================================================

function formatPhone(phone: string) {
  const cleaned = phone.replace(/\D/g, '')
  if (cleaned.length === 12) {
    return `(${cleaned.slice(2, 4)}) ${cleaned.slice(4, 9)}-${cleaned.slice(9)}`
  }
  return phone
}

function filterSummary(wh: Webhook): string {
  const parts: string[] = []
  if (wh.filter_direction === 'incoming') parts.push('incoming')
  else if (wh.filter_direction === 'outgoing') parts.push('outgoing')
  if (wh.filter_chat_type !== 'all') parts.push(wh.filter_chat_type)
  if (wh.filter_text_match_operator !== 'none' && wh.filter_text_match_value) {
    const op = wh.filter_text_match_operator === 'equals' ? '=' : 'contém'
    parts.push(`texto ${op} "${wh.filter_text_match_value}"`)
  }
  return parts.length ? parts.join(' · ') : 'todos os eventos'
}

function openCreateModal() {
  form.webhookId = null
  form.name = ''
  form.url = ''
  form.enabled = true
  form.filter_direction = 'all'
  form.filter_chat_type = 'all'
  form.filter_text_match_operator = 'none'
  form.filter_text_match_value = ''
  form.testResult = null
  form.open = true
}

function openEditModal(wh: Webhook) {
  form.webhookId = wh.id
  form.name = wh.name
  form.url = wh.url
  form.enabled = wh.enabled
  form.filter_direction = wh.filter_direction
  form.filter_chat_type = wh.filter_chat_type
  form.filter_text_match_operator = wh.filter_text_match_operator
  form.filter_text_match_value = wh.filter_text_match_value
  form.testResult = null
  form.open = true
}

function closeForm() {
  if (form.saving) return
  form.open = false
}

const canSave = computed(() => {
  return form.url.trim().length > 0 && form.url.startsWith('http') && !form.saving
})

async function saveForm() {
  if (!canSave.value) return
  form.saving = true
  form.testResult = null
  try {
    const payload = {
      name: form.name.trim() || undefined,
      url: form.url.trim(),
      enabled: form.enabled,
      filter_direction: form.filter_direction,
      filter_chat_type: form.filter_chat_type,
      filter_text_match_operator: form.filter_text_match_operator,
      filter_text_match_value: form.filter_text_match_operator === 'none' ? '' : form.filter_text_match_value.trim(),
    }
    if (form.webhookId) {
      const updatePayload: UpdateWebhookInput = payload
      await telegramStore.updateWebhook(form.webhookId, props.sessionId, updatePayload)
    } else {
      const createPayload: CreateWebhookInput = payload
      await telegramStore.createWebhook(props.sessionId, createPayload)
    }
    form.open = false
    await refresh()
  } catch (e: any) {
    error.value = e.message
  } finally {
    form.saving = false
  }
}

async function testForm() {
  if (!form.url.trim().startsWith('http')) return
  form.testing = true
  form.testResult = null
  try {
    // Pra testar antes de salvar, mandamos direto na URL (sem auth no PB)
    const r = await fetch(form.url.trim(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        type: 'test',
        message: 'Conexão OK!',
        timestamp: new Date().toISOString(),
      }),
    })
    form.testResult = { ok: r.ok, status: r.status }
  } catch {
    form.testResult = { ok: false, status: 0 }
  } finally {
    form.testing = false
  }
}

async function testExisting(wh: Webhook) {
  if (togglingId.value) return
  togglingId.value = wh.id
  try {
    const r = await telegramApi.testWebhook(wh.id)
    alert(
      r.success
        ? `Webhook OK! Status: ${r.status_code}`
        : `Falhou. Status: ${r.status_code || 'sem resposta'}`,
    )
  } catch (e: any) {
    alert(`Erro: ${e.message}`)
  } finally {
    togglingId.value = null
  }
}

async function togglePause(wh: Webhook) {
  if (togglingId.value) return
  togglingId.value = wh.id
  try {
    await telegramStore.toggleWebhook(wh.id, props.sessionId, !wh.enabled)
    await refresh()
  } catch (e: any) {
    error.value = e.message
  } finally {
    togglingId.value = null
  }
}

function promptRemove(wh: Webhook) {
  confirmRemove.webhook = wh
  confirmRemove.show = true
}

async function executeRemove() {
  if (!confirmRemove.webhook) return
  confirmRemove.loading = true
  try {
    await telegramStore.deleteWebhook(confirmRemove.webhook.id, props.sessionId)
    confirmRemove.show = false
    confirmRemove.webhook = null
    await refresh()
  } catch (e: any) {
    error.value = e.message
  } finally {
    confirmRemove.loading = false
  }
}

function goBack() {
  router.push('/dashboard')
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50">
    <!-- Navigation -->
    <nav class="bg-white/80 backdrop-blur-lg shadow-lg sticky top-0 z-50 border-b border-gray-200">
      <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          <div class="flex items-center">
            <button @click="goBack" class="flex items-center text-gray-600 hover:text-gray-900">
              <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
              </svg>
              <span class="font-semibold">Voltar</span>
            </button>
          </div>
          <div class="flex items-center gap-3">
            <span class="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              Webhooks
            </span>
          </div>
        </div>
      </div>
    </nav>

    <main class="max-w-4xl mx-auto py-8 px-4 space-y-6">
      <!-- Header da conta -->
      <div class="bg-white rounded-2xl shadow-xl p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-xs text-gray-500">Conta</p>
            <h1 class="text-2xl font-bold text-gray-900">{{ accountLabel }}</h1>
            <p v-if="currentSession?.name" class="text-sm text-gray-500 mt-1">
              {{ formatPhone(currentSession.phone) }}
            </p>
          </div>
          <button
            @click="openCreateModal"
            class="inline-flex items-center px-4 py-2 bg-gradient-to-r from-blue-500 to-purple-500 text-white font-bold rounded-xl hover:from-blue-600 hover:to-purple-600 transition-all transform hover:scale-105 shadow-lg"
          >
            <svg class="h-5 w-5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
            Novo webhook
          </button>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading && webhooks.length === 0" class="p-12 flex justify-center">
        <div class="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
      </div>

      <!-- Empty state -->
      <div v-else-if="!loading && webhooks.length === 0" class="bg-white rounded-2xl shadow-xl p-12 text-center">
        <div class="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg class="w-10 h-10 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
          </svg>
        </div>
        <h4 class="text-lg font-semibold text-gray-900 mb-2">Nenhum webhook configurado</h4>
        <p class="text-gray-500 mb-6">Cada webhook pode ter filtros próprios (direção, tipo de chat, texto).</p>
        <button
          @click="openCreateModal"
          class="inline-flex items-center px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-500 text-white font-bold rounded-xl hover:from-blue-600 hover:to-purple-600 transition-all"
        >
          Criar primeiro webhook
        </button>
      </div>

      <!-- Lista de webhooks -->
      <div v-else class="space-y-3">
        <div
          v-for="wh in webhooks"
          :key="wh.id"
          class="bg-white rounded-2xl shadow-xl p-5"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 mb-1">
                <h3 class="font-semibold text-gray-900 truncate">{{ wh.name || 'Sem nome' }}</h3>
                <span
                  class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                  :class="wh.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'"
                >
                  <span class="w-1.5 h-1.5 rounded-full mr-1" :class="wh.enabled ? 'bg-green-500' : 'bg-gray-400'"></span>
                  {{ wh.enabled ? 'Ativo' : 'Pausado' }}
                </span>
              </div>
              <p class="text-xs text-gray-500 font-mono truncate">{{ wh.url }}</p>
              <p class="text-xs text-gray-600 mt-2">
                <span class="font-medium">Filtro:</span> {{ filterSummary(wh) }}
              </p>
            </div>
            <div class="flex flex-col gap-2 flex-shrink-0">
              <button
                @click="openEditModal(wh)"
                class="text-xs px-3 py-1.5 border border-blue-300 text-blue-600 rounded-lg hover:bg-blue-50 font-medium"
              >
                Editar
              </button>
              <button
                @click="testExisting(wh)"
                :disabled="togglingId === wh.id"
                class="text-xs px-3 py-1.5 border border-green-300 text-green-600 rounded-lg hover:bg-green-50 font-medium disabled:opacity-50"
              >
                Testar
              </button>
              <button
                @click="togglePause(wh)"
                :disabled="togglingId === wh.id"
                :class="wh.enabled
                  ? 'border-orange-300 text-orange-600 hover:bg-orange-50'
                  : 'border-purple-300 text-purple-600 hover:bg-purple-50'"
                class="text-xs px-3 py-1.5 border rounded-lg font-medium disabled:opacity-50"
              >
                {{ togglingId === wh.id ? '...' : (wh.enabled ? 'Pausar' : 'Retomar') }}
              </button>
              <button
                @click="promptRemove(wh)"
                class="text-xs px-3 py-1.5 border border-red-300 text-red-600 rounded-lg hover:bg-red-50 font-medium"
              >
                Remover
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Erro -->
      <div v-if="error" class="bg-red-50 border border-red-200 rounded-xl p-4">
        <p class="text-red-700 text-sm">{{ error }}</p>
        <button @click="refresh" class="mt-2 text-sm text-red-600 hover:text-red-800 font-medium">
          Tentar novamente
        </button>
      </div>
    </main>

    <!-- Modal: criar/editar webhook -->
    <Teleport to="body">
      <div v-if="form.open" class="fixed inset-0 z-50 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <div class="fixed inset-0 bg-black/50 transition-opacity" @click="closeForm"></div>
          <div class="relative bg-white rounded-2xl shadow-xl max-w-2xl w-full p-6">
            <h3 class="text-xl font-bold text-gray-900 mb-1">
              {{ form.webhookId ? 'Editar webhook' : 'Novo webhook' }}
            </h3>
            <p class="text-sm text-gray-500 mb-6">Configura URL e filtros.</p>

            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Nome (opcional)</label>
                <input
                  v-model="form.name"
                  type="text"
                  maxlength="60"
                  placeholder="ex.: Ativação de plugin"
                  class="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:outline-none"
                  :disabled="form.saving"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">URL *</label>
                <input
                  v-model="form.url"
                  type="url"
                  placeholder="https://seu-servico.com/webhook"
                  class="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:outline-none font-mono text-sm"
                  :class="{ 'border-red-300': form.url && !form.url.startsWith('http') }"
                  :disabled="form.saving"
                />
                <p v-if="form.url && !form.url.startsWith('http')" class="mt-1 text-xs text-red-500">
                  URL deve começar com http:// ou https://
                </p>
              </div>

              <div class="flex items-center gap-2">
                <input
                  id="enabled"
                  v-model="form.enabled"
                  type="checkbox"
                  class="w-4 h-4 text-blue-600 rounded"
                  :disabled="form.saving"
                />
                <label for="enabled" class="text-sm text-gray-700">Webhook ativo</label>
              </div>

              <div class="border-t border-gray-200 pt-4">
                <p class="text-sm font-semibold text-gray-700 mb-3">Filtros</p>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <label class="block text-xs font-medium text-gray-600 mb-1">Direção</label>
                    <select
                      v-model="form.filter_direction"
                      class="w-full px-3 py-2 border-2 border-gray-200 rounded-lg text-sm"
                      :disabled="form.saving"
                    >
                      <option value="all">Todos</option>
                      <option value="incoming">Só recebidas</option>
                      <option value="outgoing">Só enviadas</option>
                    </select>
                  </div>

                  <div>
                    <label class="block text-xs font-medium text-gray-600 mb-1">Tipo de chat</label>
                    <select
                      v-model="form.filter_chat_type"
                      class="w-full px-3 py-2 border-2 border-gray-200 rounded-lg text-sm"
                      :disabled="form.saving"
                    >
                      <option value="all">Todos</option>
                      <option value="private">Privado</option>
                      <option value="group">Grupo</option>
                      <option value="supergroup">Supergrupo</option>
                      <option value="channel">Canal</option>
                    </select>
                  </div>

                  <div>
                    <label class="block text-xs font-medium text-gray-600 mb-1">Texto</label>
                    <select
                      v-model="form.filter_text_match_operator"
                      class="w-full px-3 py-2 border-2 border-gray-200 rounded-lg text-sm"
                      :disabled="form.saving"
                    >
                      <option value="none">Sem filtro</option>
                      <option value="equals">Igual a</option>
                      <option value="contains">Contém</option>
                    </select>
                  </div>
                </div>

                <div v-if="form.filter_text_match_operator !== 'none'" class="mt-3">
                  <label class="block text-xs font-medium text-gray-600 mb-1">
                    {{ form.filter_text_match_operator === 'equals' ? 'Texto exato' : 'Texto a buscar' }}
                  </label>
                  <input
                    v-model="form.filter_text_match_value"
                    type="text"
                    maxlength="200"
                    :placeholder="form.filter_text_match_operator === 'equals' ? 'ex.: ATIVAR-PLUGIN' : 'ex.: plugin'"
                    class="w-full px-3 py-2 border-2 border-gray-200 rounded-lg text-sm font-mono"
                    :disabled="form.saving"
                  />
                </div>
              </div>

              <div v-if="form.testResult" class="p-3 rounded-lg" :class="form.testResult.ok ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'">
                <p class="text-sm" :class="form.testResult.ok ? 'text-green-700' : 'text-red-700'">
                  {{ form.testResult.ok ? '✓ Webhook respondeu' : '✗ Webhook não respondeu' }}
                  — status: {{ form.testResult.status || 'sem resposta' }}
                </p>
              </div>
            </div>

            <div class="flex gap-3 mt-6">
              <button
                v-if="form.url.startsWith('http')"
                @click="testForm"
                :disabled="form.testing || form.saving"
                class="px-4 py-3 border border-green-300 text-green-600 font-medium rounded-xl hover:bg-green-50 disabled:opacity-50"
              >
                {{ form.testing ? 'Testando...' : 'Testar' }}
              </button>
              <button
                @click="closeForm"
                :disabled="form.saving"
                class="flex-1 px-4 py-3 border border-gray-300 text-gray-700 font-medium rounded-xl hover:bg-gray-50 disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                @click="saveForm"
                :disabled="!canSave"
                class="flex-1 px-4 py-3 bg-gradient-to-r from-blue-500 to-purple-500 text-white font-medium rounded-xl hover:from-blue-600 hover:to-purple-600 disabled:opacity-50"
              >
                {{ form.saving ? 'Salvando...' : (form.webhookId ? 'Salvar' : 'Criar') }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Modal: confirmar remover -->
    <Teleport to="body">
      <div v-if="confirmRemove.show" class="fixed inset-0 z-50 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <div class="fixed inset-0 bg-black/50 transition-opacity" @click="confirmRemove.show = false"></div>
          <div class="relative bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <div class="text-center">
              <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg class="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h3 class="text-xl font-bold text-gray-900 mb-2">Remover webhook?</h3>
              <p class="text-gray-600 mb-6">
                <strong>{{ confirmRemove.webhook?.name }}</strong> ({{ confirmRemove.webhook?.url }})
                — esta ação não pode ser desfeita.
              </p>
              <div class="flex gap-4">
                <button
                  @click="confirmRemove.show = false"
                  class="flex-1 px-4 py-3 border border-gray-300 text-gray-700 font-medium rounded-xl hover:bg-gray-50"
                >
                  Cancelar
                </button>
                <button
                  @click="executeRemove"
                  :disabled="confirmRemove.loading"
                  class="flex-1 px-4 py-3 bg-gradient-to-r from-red-500 to-pink-500 text-white font-medium rounded-xl hover:from-red-600 hover:to-pink-600 disabled:opacity-50"
                >
                  {{ confirmRemove.loading ? 'Removendo...' : 'Remover' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>
