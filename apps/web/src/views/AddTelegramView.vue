<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { telegramApi } from '../services/telegram'

const router = useRouter()

// Estados: 'phone' | 'code' | 'loading' | 'success' | 'error'
const step = ref<'phone' | 'code' | 'loading' | 'success' | 'error'>('phone')

// Dados
const phone = ref('')
const code = ref('')
const phoneCodeHash = ref('')
const sessionId = ref('')
const errorMessage = ref('')
const countdown = ref(0)

// Validação
const isValidPhone = computed(() => {
  const cleaned = phone.value.replace(/\D/g, '')
  return cleaned.length >= 10 && cleaned.length <= 15
})

const isValidCode = computed(() => {
  return code.value.replace(/\D/g, '').length >= 4
})

// Formatar telefone
const formatPhone = (value: string) => {
  const cleaned = value.replace(/\D/g, '')
  if (cleaned.length <= 2) return cleaned
  if (cleaned.length <= 7) return `(${cleaned.slice(0, 2)}) ${cleaned.slice(2)}`
  return `(${cleaned.slice(0, 2)}) ${cleaned.slice(2, 7)}-${cleaned.slice(7, 11)}`
}

const handlePhoneInput = (e: Event) => {
  const input = e.target as HTMLInputElement
  phone.value = formatPhone(input.value)
}

// Enviar código
const sendCode = async () => {
  if (!isValidPhone.value) return
  
  step.value = 'loading'
  errorMessage.value = ''
  
  // Adiciona + se não tiver
  let fullPhone = phone.value
  if (!fullPhone.startsWith('+')) {
    fullPhone = '+55' + fullPhone.replace(/\D/g, '')
  }
  if (!fullPhone.startsWith('+')) {
    fullPhone = '+' + fullPhone
  }
  
  try {
    const result = await telegramApi.sendCode(fullPhone)
    phoneCodeHash.value = result.phone_code_hash
    sessionId.value = result.session_id
    step.value = 'code'
    
    // Countdown de reenvio (baseado no expire_interval da API)
    countdown.value = result.expires || 60
    const timer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) clearInterval(timer)
    }, 1000)
    
  } catch (error: any) {
    step.value = 'error'
    errorMessage.value = error.message || 'Erro ao enviar código'
  }
}

// Verificar código
const verifyCode = async () => {
  if (!isValidCode.value) return
  
  step.value = 'loading'
  errorMessage.value = ''
  
  let fullPhone = phone.value
  if (!fullPhone.startsWith('+')) {
    fullPhone = '+' + fullPhone.replace(/\D/g, '')
  }
  
  try {
    await telegramApi.verifyCode(fullPhone, code.value, phoneCodeHash.value)
    step.value = 'success'
    
    // Redireciona após 2 segundos
    setTimeout(() => {
      router.push('/dashboard')
    }, 2000)
    
  } catch (error: any) {
    step.value = 'error'
    errorMessage.value = error.message || 'Código inválido'
    // Volta pro input de código
    setTimeout(() => {
      step.value = 'code'
      code.value = ''
    }, 2000)
  }
}

// Voltar
const goBack = () => {
  if (step.value === 'code') {
    step.value = 'phone'
    code.value = ''
    countdown.value = 0
  } else {
    router.push('/dashboard')
  }
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
              Adicionar Conta
            </span>
          </div>
        </div>
      </div>
    </nav>

    <!-- Main Content -->
    <main class="max-w-2xl mx-auto py-12 px-4">
      <!-- Progress Steps -->
      <div class="flex items-center justify-center mb-12">
        <div class="flex items-center">
          <!-- Step 1 -->
          <div class="flex items-center">
            <div 
              class="w-10 h-10 rounded-full flex items-center justify-center font-bold transition-all"
              :class="step === 'phone' || step === 'code' || step === 'success' 
                ? 'bg-gradient-to-r from-blue-500 to-purple-500 text-white' 
                : 'bg-gray-200 text-gray-500'"
            >
              1
            </div>
            <span class="ml-3 font-medium text-gray-700">Telefone</span>
          </div>
          
          <div class="w-16 h-0.5 mx-4" :class="step === 'code' || step === 'success' ? 'bg-gradient-to-r from-blue-500 to-purple-500' : 'bg-gray-200'"></div>
          
          <!-- Step 2 -->
          <div class="flex items-center">
            <div 
              class="w-10 h-10 rounded-full flex items-center justify-center font-bold transition-all"
              :class="step === 'code' || step === 'success' 
                ? 'bg-gradient-to-r from-blue-500 to-purple-500 text-white' 
                : 'bg-gray-200 text-gray-500'"
            >
              2
            </div>
            <span class="ml-3 font-medium text-gray-700">Verificação</span>
          </div>
        </div>
      </div>

      <!-- Phone Step -->
      <div v-if="step === 'phone'" class="bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center mb-8">
          <div class="w-20 h-20 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
          </div>
          <h2 class="text-2xl font-bold text-gray-900 mb-2">Digite seu número</h2>
          <p class="text-gray-600">Enviaremos um código de verificação via SMS</p>
        </div>

        <div class="space-y-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">Número de telefone</label>
            <input
              type="tel"
              :value="phone"
              @input="handlePhoneInput"
              placeholder="(00) 00000-0000"
              class="w-full px-4 py-4 text-lg border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:outline-none transition-colors"
              :class="{ 'border-red-300': phone && !isValidPhone }"
            />
            <p v-if="phone && !isValidPhone" class="mt-2 text-sm text-red-500">
              Digite um número válido com DDD
            </p>
          </div>

          <button
            @click="sendCode"
            :disabled="!isValidPhone"
            class="w-full py-4 px-6 bg-gradient-to-r from-blue-500 to-purple-500 text-white font-bold rounded-xl hover:from-blue-600 hover:to-purple-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all transform hover:scale-[1.02] active:scale-[0.98] shadow-lg"
          >
            Enviar código
          </button>
        </div>
      </div>

      <!-- Code Step -->
      <div v-if="step === 'code'" class="bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center mb-8">
          <div class="w-20 h-20 bg-gradient-to-br from-green-500 to-emerald-500 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h2 class="text-2xl font-bold text-gray-900 mb-2">Código enviado!</h2>
          <p class="text-gray-600">
            Enviamos um código de 5 dígitos para<br />
            <span class="font-semibold text-gray-900">{{ phone }}</span>
          </p>
        </div>

        <div class="space-y-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">Código de verificação</label>
            <input
              v-model="code"
              type="text"
              inputmode="numeric"
              pattern="[0-9]*"
              maxlength="10"
              placeholder="00000"
              class="w-full px-4 py-4 text-3xl text-center tracking-widest border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:outline-none transition-colors"
              :class="{ 'border-red-300': code && !isValidCode }"
              @keyup.enter="verifyCode"
            />
            <p v-if="code && !isValidCode" class="mt-2 text-sm text-red-500">
              Digite o código completo
            </p>
          </div>

          <button
            @click="verifyCode"
            :disabled="!isValidCode"
            class="w-full py-4 px-6 bg-gradient-to-r from-green-500 to-emerald-500 text-white font-bold rounded-xl hover:from-green-600 hover:to-emerald-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all transform hover:scale-[1.02] active:scale-[0.98] shadow-lg"
          >
            Verificar código
          </button>

          <div class="text-center">
            <p v-if="countdown > 0" class="text-sm text-gray-500">
              Reenviar código em {{ countdown }}s
            </p>
            <button 
              v-else
              @click="sendCode"
              class="text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              Não recebeu? Reenviar código
            </button>
          </div>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="step === 'loading'" class="bg-white rounded-2xl shadow-xl p-12">
        <div class="flex flex-col items-center justify-center">
          <div class="w-16 h-16 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <p class="mt-6 text-lg font-medium text-gray-700">Processando...</p>
        </div>
      </div>

      <!-- Success -->
      <div v-if="step === 'success'" class="bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center">
          <div class="w-20 h-20 bg-gradient-to-br from-green-400 to-emerald-500 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 class="text-2xl font-bold text-gray-900 mb-2">Conta vinculada!</h2>
          <p class="text-gray-600">Redirecionando para o dashboard...</p>
        </div>
      </div>

      <!-- Error -->
      <div v-if="step === 'error'" class="bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center">
          <div class="w-20 h-20 bg-gradient-to-br from-red-400 to-pink-500 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h2 class="text-2xl font-bold text-gray-900 mb-2">Erro</h2>
          <p class="text-red-600">{{ errorMessage }}</p>
          <button
            @click="step = 'phone'; phone = ''; code = ''"
            class="mt-6 px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-500 text-white font-bold rounded-xl hover:from-blue-600 hover:to-purple-600 transition-all"
          >
            Tentar novamente
          </button>
        </div>
      </div>
    </main>
  </div>
</template>
