<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { telegramApi, type TelegramSession } from '../services/telegram'

const route = useRoute()
const router = useRouter()

const sessionId = computed(() => route.query.session as string || '')

// Estado
const webhookUrl = ref('')
const loading = ref(false)
const testing = ref(false)
const testResult = ref<{ success: boolean; status: number } | null>(null)
const saved = ref(false)
const error = ref('')

onMounted(() => {
  if (!sessionId.value) {
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
  if (!webhookUrl.value || !sessionId.value) return
  
  loading.value = true
  error.value = ''
  
  try {
    await telegramApi.setWebhook(sessionId.value, webhookUrl.value)
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
          <div class="flex items-center">
            <span class="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              Configurar Webhook
            </span>
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
              <p class="font-mono text-sm text-gray-700">{{ sessionId }}</p>
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
          <div class="mt-4 bg-white rounded-lg p-4 font-mono text-xs">
            <p class="text-gray-600">Exemplo do payload recebido:</p>
            <pre class="mt-2 text-gray-800">{{ JSON.stringify({
              "session_id": "account_...",
              "chat_id": 123456789,
              "message_id": 1,
              "text": "Olá!",
              "sender_id": 987654321,
              "sender_name": "João Silva",
              "timestamp": "2024-01-01T00:00:00Z"
            }, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>
