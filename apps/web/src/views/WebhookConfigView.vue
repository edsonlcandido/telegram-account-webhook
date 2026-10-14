<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { telegramApi } from '../services/telegram'

const router = useRouter()

// Path param via props: true no router (/webhook/:sessionId)
// Não desestruturar para preservar reatividade (compatível com qualquer Vue 3.x)
const props = defineProps<{ sessionId: string }>()

// Estado
const webhookUrl = ref('')
const loading = ref(false)
const testing = ref(false)

// Payload completo (igual ao do /docs, seção 1) pra mostrar pro usuário o que
// vai chegar no endpoint dele. Mantido aqui em vez de importado do /docs pra
// essa tela ser auto-contida.
const INCOMING_PAYLOAD = JSON.stringify(
  {
    session_id: 'account_5511999998888',
    message_id: 1234,
    chat_id: 5511988887777,
    chat_type: 'private',
    chat_title: 'Maria Silva',
    outgoing: false,
    text: 'oi, tudo bem?',
    sender_id: 5511988887777,
    sender_name: 'Maria Silva',
    sender_username: 'maria',
    is_reply: false,
    reply_to_message_id: null,
    has_media: false,
    media_type: null,
    media_mime_type: null,
    timestamp: '2026-10-13T20:51:03.123456',
  },
  null,
  2,
)

const copiedPayload = ref(false)
async function copyPayload() {
  try {
    await navigator.clipboard.writeText(INCOMING_PAYLOAD)
    copiedPayload.value = true
    setTimeout(() => {
      copiedPayload.value = false
    }, 1500)
  } catch {
    // fallback silencioso
  }
}
const testResult = ref<{ success: boolean; status: number } | null>(null)
const saved = ref(false)
const error = ref('')

onMounted(() => {
  if (!props.sessionId) {
    router.push('/dashboard')
  }
})

const testWebhook = async () => {
  if (!webhookUrl.value) return
  
  testing.value = true
  testResult.value = null
  error.value = ''
  
  try {
    testResult.value = await telegramApi.testWebhook(webhookUrl.value)
  } catch (e: any) {
    error.value = e.message
    testResult.value = { success: false, status: 0 }
  } finally {
    testing.value = false
  }
}

const saveWebhook = async () => {
  if (!webhookUrl.value || !props.sessionId) return

  loading.value = true
  error.value = ''

  try {
    await telegramApi.setWebhook(props.sessionId, webhookUrl.value)
    saved.value = true
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push('/dashboard')
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50">
    <!-- Navigation -->
    <nav class="bg-white/80 backdrop-blur-lg shadow-lg sticky top-0 z-50 border-b border-gray-200">
      <div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          <div class="flex items-center">
            <button @click="goBack" class="flex items-center text-gray-600 hover:text-gray-900">
              <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
              </svg>
              <span class="font-semibold">Voltar</span>
            </button>
          </div>
          <div class="flex items-center gap-4">
            <span class="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              Configurar Webhook
            </span>
            <router-link
              to="/docs"
              class="inline-flex items-center px-3 py-1.5 text-xs font-medium text-gray-600 hover:text-blue-600 bg-gray-100 hover:bg-blue-50 rounded-lg transition-colors"
              title="Ver documentação completa"
            >
              <svg class="h-4 w-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Ver docs
            </router-link>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-2xl mx-auto py-12 px-4">
      <div class="bg-white rounded-2xl shadow-xl p-8">
        <!-- Header -->
        <div class="text-center mb-8">
          <div class="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
          <h2 class="text-2xl font-bold text-gray-900 mb-2">Webhook para Receber Mensagens</h2>
          <p class="text-gray-600">
            Configure a URL que receberá as mensagens desta conta Telegram
          </p>
        </div>

        <!-- Session ID (info) -->
        <div class="bg-gray-50 rounded-xl p-4 mb-8">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 bg-gradient-to-br from-green-400 to-emerald-500 rounded-lg flex items-center justify-center">
              <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <p class="text-sm text-gray-500">Conta configurada</p>
              <p class="font-mono text-sm text-gray-700">{{ props.sessionId }}</p>
            </div>
          </div>
        </div>

        <!-- Webhook URL Input -->
        <div class="space-y-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              URL do Webhook
            </label>
            <input
              v-model="webhookUrl"
              type="url"
              placeholder="https://seu-servico.com/webhook"
              class="w-full px-4 py-4 text-lg border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:outline-none transition-colors"
              :class="{ 'border-red-300': error }"
              @keyup.enter="testWebhook"
            />
            <p class="mt-2 text-sm text-gray-500">
              Endereço que receberá POST requests com as mensagens
            </p>
          </div>

          <!-- Error -->
          <div v-if="error" class="p-4 bg-red-50 border border-red-200 rounded-xl">
            <p class="text-red-600 text-sm">{{ error }}</p>
          </div>

          <!-- Test Result -->
          <div v-if="testResult" class="p-4 rounded-xl" :class="testResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'">
            <div class="flex items-center gap-3">
              <div v-if="testResult.success" class="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div v-else class="w-8 h-8 bg-red-500 rounded-full flex items-center justify-center">
                <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <div>
                <p v-if="testResult.success" class="font-medium text-green-700">
                  Webhook respondendo corretamente
                </p>
                <p v-else class="font-medium text-red-700">
                  Webhook não está respondendo
                </p>
                <p class="text-sm text-gray-500">
                  Status: {{ testResult.status || 'Sem resposta' }}
                </p>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex gap-4">
            <button
              @click="testWebhook"
              :disabled="!webhookUrl || testing"
              class="flex-1 py-4 px-6 border-2 border-blue-500 text-blue-600 font-bold rounded-xl hover:bg-blue-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {{ testing ? 'Testando...' : 'Testar Webhook' }}
            </button>
            <button
              @click="saveWebhook"
              :disabled="!webhookUrl || loading"
              class="flex-1 py-4 px-6 bg-gradient-to-r from-blue-500 to-purple-500 text-white font-bold rounded-xl hover:from-blue-600 hover:to-purple-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all transform hover:scale-[1.02] active:scale-[0.98] shadow-lg"
            >
              {{ loading ? 'Salvando...' : 'Salvar' }}
            </button>
          </div>

          <!-- Success Message -->
          <div v-if="saved" class="p-4 bg-green-50 border border-green-200 rounded-xl">
            <p class="text-green-700 font-medium">✓ Webhook configurado com sucesso!</p>
          </div>
        </div>

        <!-- Info Box -->
        <div class="mt-8 p-4 bg-blue-50 rounded-xl border border-blue-200">
          <h4 class="font-semibold text-blue-900 mb-2">O que é um Webhook?</h4>
          <p class="text-sm text-blue-700">
            Um webhook é uma URL que recebe notificações quando chega uma mensagem na sua conta Telegram.
            Configure o endpoint do seu sistema para receber os dados em tempo real.
          </p>
          <div class="mt-4 bg-white rounded-lg p-4">
            <div class="flex items-center justify-between mb-2">
              <p class="text-gray-600 text-xs">Exemplo do payload recebido (POST JSON):</p>
              <button
                @click="copyPayload"
                class="text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 font-medium"
              >
                {{ copiedPayload ? '✓ Copiado' : 'Copiar' }}
              </button>
            </div>
            <pre class="font-mono text-xs text-gray-800 overflow-x-auto leading-relaxed"><code>{{ INCOMING_PAYLOAD }}</code></pre>
            <p class="text-xs text-gray-500 mt-2">
              <a href="/app/docs" class="text-blue-600 hover:underline">Ver documentação completa →</a>
            </p>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
