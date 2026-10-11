<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-purple-50 to-pink-50 py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8">
      <div class="text-center">
        <div class="inline-block mb-4">
          <div class="w-20 h-20 bg-gradient-to-br from-blue-600 to-purple-600 rounded-2xl flex items-center justify-center mx-auto shadow-2xl transform hover:scale-110 transition-transform">
            <span class="text-4xl">🔐</span>
          </div>
        </div>
        <h2 class="mt-6 text-center text-4xl font-extrabold text-gray-900">
          {{ isRegistering ? '✨ Criar conta' : '👋 Bem-vindo de volta' }}
        </h2>
        <p class="mt-3 text-center text-base text-gray-600">
          {{ isRegistering ? 'Preencha os dados para criar sua conta' : 'Entre com suas credenciais para continuar' }}
        </p>
        <p class="mt-2 text-center text-sm">
          <a href="/" class="font-semibold text-blue-600 hover:text-purple-600 transition-colors inline-flex items-center">
            <svg class="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"></path>
            </svg>
            Voltar para a landing page
          </a>
        </p>
      </div>
      
      <div class="bg-white py-10 px-6 shadow-2xl rounded-2xl sm:px-12 border border-gray-100">
        <form class="space-y-6" @submit.prevent="handleSubmit">
          <div v-if="error" class="rounded-xl bg-red-50 p-4 border-l-4 border-red-500 shadow-sm">
            <div class="flex">
              <div class="flex-shrink-0">
                <svg class="h-5 w-5 text-red-400" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
                </svg>
              </div>
              <div class="ml-3">
                <h3 class="text-sm font-semibold text-red-800">
                  {{ error }}
                </h3>
              </div>
            </div>
          </div>

          <div v-if="isRegistering">
            <label for="name" class="block text-sm font-semibold text-gray-700 mb-2">
              Nome Completo
            </label>
            <div class="mt-1">
              <input
                id="name"
                v-model="formData.name"
                type="text"
                autocomplete="name"
                class="appearance-none block w-full px-4 py-3 border-2 border-gray-300 rounded-xl shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all sm:text-sm hover:border-gray-400"
                placeholder="João Silva"
              />
            </div>
          </div>

          <div>
            <label for="email" class="block text-sm font-semibold text-gray-700 mb-2">
              E-mail
            </label>
            <div class="mt-1">
              <input
                id="email"
                v-model="formData.email"
                type="email"
                autocomplete="email"
                required
                class="appearance-none block w-full px-4 py-3 border-2 border-gray-300 rounded-xl shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all sm:text-sm hover:border-gray-400"
                placeholder="seu@email.com"
              />
            </div>
          </div>

          <div>
            <label for="password" class="block text-sm font-semibold text-gray-700 mb-2">
              Senha
            </label>
            <div class="mt-1">
              <input
                id="password"
                v-model="formData.password"
                type="password"
                autocomplete="current-password"
                required
                class="appearance-none block w-full px-4 py-3 border-2 border-gray-300 rounded-xl shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all sm:text-sm hover:border-gray-400"
                placeholder="••••••••"
              />
            </div>
          </div>

          <div v-if="isRegistering">
            <label for="passwordConfirm" class="block text-sm font-semibold text-gray-700 mb-2">
              Confirmar Senha
            </label>
            <div class="mt-1">
              <input
                id="passwordConfirm"
                v-model="formData.passwordConfirm"
                type="password"
                autocomplete="new-password"
                required
                class="appearance-none block w-full px-4 py-3 border-2 border-gray-300 rounded-xl shadow-sm placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all sm:text-sm hover:border-gray-400"
                placeholder="••••••••"
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              :disabled="loading"
              class="group w-full flex justify-center items-center py-3 px-4 border border-transparent rounded-xl shadow-lg text-base font-semibold text-white bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all transform hover:scale-[1.02]"
            >
              <span v-if="loading" class="flex items-center">
                <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Carregando...
              </span>
              <span v-else class="flex items-center">
                {{ isRegistering ? '✨ Criar conta' : '🚀 Entrar' }}
                <svg class="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"></path>
                </svg>
              </span>
            </button>
          </div>
        </form>

        <div class="mt-8">
          <div class="relative">
            <div class="absolute inset-0 flex items-center">
              <div class="w-full border-t-2 border-gray-200" />
            </div>
            <div class="relative flex justify-center text-sm">
              <span class="px-4 bg-white text-gray-600 font-medium">
                {{ isRegistering ? '🔑 Já tem uma conta?' : '🆕 Não tem uma conta?' }}
              </span>
            </div>
          </div>

          <div class="mt-6">
            <button
              type="button"
              @click="toggleMode"
              class="w-full flex justify-center items-center py-3 px-4 border-2 border-gray-300 rounded-xl shadow-sm text-base font-semibold text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-all transform hover:scale-[1.02]"
            >
              {{ isRegistering ? '👋 Fazer Login' : '✨ Criar Nova Conta' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const isRegistering = ref(false)
const loading = ref(false)
const error = ref('')

const formData = ref({
  name: '',
  email: '',
  password: '',
  passwordConfirm: '',
})

function toggleMode() {
  isRegistering.value = !isRegistering.value
  error.value = ''
  formData.value = {
    name: '',
    email: '',
    password: '',
    passwordConfirm: '',
  }
}

async function handleSubmit() {
  error.value = ''
  loading.value = true

  try {
    let result

    if (isRegistering.value) {
      result = await authStore.register(
        formData.value.email,
        formData.value.password,
        formData.value.passwordConfirm,
        formData.value.name
      )
    } else {
      result = await authStore.login(
        formData.value.email,
        formData.value.password
      )
    }

    if (result.success) {
      // Aguarda o próximo tick do Vue para garantir que o estado foi atualizado
      await nextTick()
      await router.push('/dashboard')
    } else {
      error.value = result.error || 'Ocorreu um erro'
    }
  } catch (e: any) {
    error.value = e?.message || 'Ocorreu um erro'
  } finally {
    loading.value = false
  }
}
</script>
