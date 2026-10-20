<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import AppNav from '../components/AppNav.vue'
import { telegramApi } from '../services/telegram'

const router = useRouter()

// Estados: 'phone' | 'code' | 'loading' | 'success' | 'error'
const step = ref<'phone' | 'code' | 'loading' | 'success' | 'error'>('phone')

// Dados
const phone = ref('')
const code = ref('')
const name = ref('')  // alias amigável (opcional)
const phoneCodeHash = ref('')
const sessionId = ref('')
const errorMessage = ref('')
const countdown = ref(0)
// 2FA: o backend responde `two_factor_required` quando a conta tem
// verificação em duas etapas. Aí o front pede a SENHA de 2FA (o código do
// SMS/app sozinho não basta).
const requires2fa = ref(false)
const password2fa = ref('')

// Normaliza telefone pro formato E.164 (+DDI+DDD+número).
// Aceita entrada com espaços/traços/parênteses pra facilitar digitação,
// mas mantém só `+` e dígitos no resultado. Se não começar com `+`,
// prepende `+55` (assume Brasil) pra cobrir o caso comum.
const sanitizePhone = (value: string): string => {
  let cleaned = value.replace(/[^\d+]/g, '')
  // garante só um `+` no início
  if (cleaned.includes('+')) {
    cleaned = '+' + cleaned.replace(/\+/g, '')
  }
  // se o user esqueceu o `+`, prepende `+55` (Brasil)
  if (!cleaned.startsWith('+') && cleaned.length >= 10) {
    cleaned = '+55' + cleaned
  }
  return cleaned
}

// Validação E.164: + seguido de 10-15 dígitos (sem zero à esquerda depois do DDI)
const isValidPhone = computed(() => {
  return /^\+[1-9]\d{9,14}$/.test(phone.value)
})

const isValidCode = computed(() => {
  return code.value.replace(/\D/g, '').length >= 4
})

const isValidName = computed(() => {
  return name.value.length <= 60
})

// Com 2FA, a senha é obrigatória pra concluir a verificação.
const canVerify = computed(() => {
  if (!isValidCode.value || !isValidName.value) return false
  if (requires2fa.value && !password2fa.value.trim()) return false
  return true
})

const handlePhoneInput = (e: Event) => {
  const input = e.target as HTMLInputElement
  phone.value = sanitizePhone(input.value)
}

// Enviar código
const sendCode = async () => {
  if (!isValidPhone.value) return

  step.value = 'loading'
  errorMessage.value = ''

  const fullPhone = phone.value

  try {
    const result = await telegramApi.sendCode(fullPhone)
    phoneCodeHash.value = result.phone_code_hash
    sessionId.value = result.session_id
    step.value = 'code'
    // Código novo => recomeça o estado de 2FA
    requires2fa.value = false
    password2fa.value = ''
    
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
  if (!isValidCode.value || !isValidName.value) return

  step.value = 'loading'
  errorMessage.value = ''

  const fullPhone = phone.value

  try {
    // O 3º argumento (`name`) é o "Apelido da conta" preenchido no passo
    // anterior. Sem ele o backend recebia `name=None` e criava o record
    // no PB com o apelido vazio — o usuario preenchia o campo e ele
    // simplesmente sumia (so aparecia depois de editar a sessao).
    // O 4º (`password`) é a senha de 2FA, só usada quando o backend
    // pediu (`two_factor_required`).
    await telegramApi.verifyCode(
      fullPhone,
      code.value,
      name.value,
      requires2fa.value ? password2fa.value : undefined,
    )
    step.value = 'success'

    // Redireciona após 2 segundos
    setTimeout(() => {
      router.push('/dashboard')
    }, 2000)

  } catch (error: any) {
    // Conta com 2FA: o backend pediu a senha. Fica no passo de código
    // (não perde o que o usuario já digitou) e mostra o campo de senha.
    if (error?.code === 'two_factor_required') {
      requires2fa.value = true
      step.value = 'code'
      errorMessage.value = error.message || 'Esta conta usa verificação em duas etapas (2FA).'
      return
    }

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
  // No passo do código, o "Voltar" volta UM passo do cadastro (tratado
  // aqui). Nos demais passos o AppNav navega pro dashboard (destino em
  // `backTo`) — por isso o `router.push` saiu daqui.
  if (step.value === 'code') {
    step.value = 'phone'
    code.value = ''
    countdown.value = 0
    requires2fa.value = false
    password2fa.value = ''
  }
}

// Destino do botão "Voltar" do AppNav:
//  - no passo do código → `''` (string vazia): o AppNav mostra o botão mas
//    NÃO navega, porque o clique só volta um passo do cadastro
//  - nos demais passos → `/dashboard`, igual às outras páginas do app
const backTo = computed(() => (step.value === 'code' ? '' : '/dashboard'))
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Navigation -->
    <AppNav title="Adicionar Conta" :back-to="backTo" @back="goBack" />

    <!-- Main Content -->
    <main class="app-container py-12">
      <!-- Container do formulário: mantém a largura estreita (672px)
           dentro do container padrão de 1216px das demais páginas -->
      <div class="max-w-2xl mx-auto">
      <!-- Progress Steps -->
      <div class="flex items-center justify-center mb-12">
        <div class="flex items-center">
          <!-- Step 1 -->
          <div class="flex items-center">
            <div 
              class="w-10 h-10 rounded-full flex items-center justify-center font-bold transition-all"
              :class="step === 'phone' || step === 'code' || step === 'success' 
                ? 'bg-brand-500 text-white' 
                : 'bg-gray-200 text-gray-500'"
            >
              1
            </div>
            <span class="ml-3 font-medium text-gray-700">Telefone</span>
          </div>
          
          <div class="w-16 h-0.5 mx-4" :class="step === 'code' || step === 'success' ? 'bg-brand-500' : 'bg-gray-200'"></div>
          
          <!-- Step 2 -->
          <div class="flex items-center">
            <div 
              class="w-10 h-10 rounded-full flex items-center justify-center font-bold transition-all"
              :class="step === 'code' || step === 'success' 
                ? 'bg-brand-500 text-white' 
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
          <div class="w-20 h-20 bg-brand-500 rounded-full flex items-center justify-center mx-auto mb-4">
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
              placeholder="+5511999999999"
              inputmode="tel"
              autocomplete="tel"
              class="w-full px-4 py-4 text-lg border-2 border-gray-200 rounded-xl focus:border-brand-500 focus:outline-none transition-colors"
              :class="{ 'border-red-300': phone && !isValidPhone }"
            />
            <p v-if="phone && !isValidPhone" class="mt-2 text-sm text-red-500">
              Use o formato internacional com + (ex.: +5511981184099)
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">
              Apelido da conta <span class="text-gray-400 font-normal">(opcional)</span>
            </label>
            <input
              v-model="name"
              type="text"
              maxlength="60"
              placeholder="ex.: Suporte, Vendas, Pessoal"
              class="w-full px-4 py-4 text-lg border-2 border-gray-200 rounded-xl focus:border-brand-500 focus:outline-none transition-colors"
              :class="{ 'border-red-300': !isValidName }"
            />
            <p v-if="!isValidName" class="mt-2 text-sm text-red-500">
              Máximo 60 caracteres.
            </p>
            <p v-else class="mt-2 text-sm text-gray-500">
              Ajuda a distinguir contas quando você tem mais de uma. Se vazio, o número é usado.
            </p>
          </div>

          <button
            @click="sendCode"
            :disabled="!isValidPhone"
            class="w-full py-4 px-6 bg-brand-500 text-white font-bold rounded-xl hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all transform hover:scale-[1.02] active:scale-[0.98] shadow-lg"
          >
            Enviar código
          </button>
        </div>
      </div>

      <!-- Code Step -->
      <div v-if="step === 'code'" class="bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center mb-8">
          <div class="w-20 h-20 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-4">
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
              class="w-full px-4 py-4 text-3xl text-center tracking-widest border-2 border-gray-200 rounded-xl focus:border-brand-500 focus:outline-none transition-colors"
              :class="{ 'border-red-300': code && !isValidCode }"
              @keyup.enter="verifyCode"
            />
            <p v-if="code && !isValidCode" class="mt-2 text-sm text-red-500">
              Digite o código completo
            </p>
          </div>

          <!-- 2FA: só aparece quando o backend responde two_factor_required -->
          <div v-if="requires2fa">
            <div class="rounded-xl bg-amber-50 border-2 border-amber-200 p-4 mb-4">
              <p class="text-sm text-amber-800">
                Esta conta tem <strong>verificação em duas etapas (2FA)</strong>.
                Informe a <strong>senha de 2FA</strong> (a senha de login do Telegram,
                não o código do app).
              </p>
            </div>
            <label class="block text-sm font-medium text-gray-700 mb-2">Senha de 2FA</label>
            <input
              v-model="password2fa"
              type="password"
              autocomplete="current-password"
              placeholder="sua senha de 2FA"
              class="w-full px-4 py-4 text-lg border-2 border-gray-200 rounded-xl focus:border-brand-500 focus:outline-none transition-colors"
              @keyup.enter="verifyCode"
            />
            <p v-if="errorMessage" class="mt-2 text-sm text-red-500">
              {{ errorMessage }}
            </p>
          </div>

          <button
            @click="verifyCode"
            :disabled="!canVerify"
            class="w-full py-4 px-6 bg-green-500 text-white font-bold rounded-xl hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all transform hover:scale-[1.02] active:scale-[0.98] shadow-lg"
          >
            {{ requires2fa ? 'Confirmar com a senha' : 'Verificar código' }}
          </button>

          <div class="text-center">
            <p v-if="countdown > 0" class="text-sm text-gray-500">
              Reenviar código em {{ countdown }}s
            </p>
            <button 
              v-else
              @click="sendCode"
              class="text-sm text-brand-600 hover:text-brand-700 font-medium"
            >
              Não recebeu? Reenviar código
            </button>
          </div>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="step === 'loading'" class="bg-white rounded-2xl shadow-xl p-12">
        <div class="flex flex-col items-center justify-center">
          <div class="w-16 h-16 border-4 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
          <p class="mt-6 text-lg font-medium text-gray-700">Processando...</p>
        </div>
      </div>

      <!-- Success -->
      <div v-if="step === 'success'" class="bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center">
          <div class="w-20 h-20 bg-green-400 rounded-full flex items-center justify-center mx-auto mb-4">
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
          <div class="w-20 h-20 bg-red-400 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg class="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </div>
          <h2 class="text-2xl font-bold text-gray-900 mb-2">Erro</h2>
          <p class="text-red-600">{{ errorMessage }}</p>
          <button
            @click="step = 'phone'; phone = ''; code = ''"
            class="mt-6 px-6 py-3 bg-brand-500 text-white font-bold rounded-xl hover:bg-brand-600 transition-all"
          >
            Tentar novamente
          </button>
        </div>
      </div>
      </div>
    </main>
  </div>
</template>
