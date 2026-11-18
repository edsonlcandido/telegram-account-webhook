<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AppNav from '../components/AppNav.vue'
import { telegramApi } from '../services/telegram'

const router = useRouter()

const botToken = ref('')
const name = ref('')
const loading = ref(false)
const error = ref('')

const submit = async () => {
  if (!botToken.value.trim()) {
    error.value = 'Informe o token do bot'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await telegramApi.addBot(botToken.value.trim(), name.value.trim())
    router.push('/dashboard')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Erro ao adicionar bot'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-gray-50">
    <AppNav title="Adicionar Bot" back-to="/dashboard" />

    <main class="app-container py-12">
      <div class="max-w-2xl mx-auto bg-white rounded-2xl shadow-xl p-8">
        <div class="text-center mb-8">
          <h2 class="text-2xl font-bold text-gray-900 mb-2">Token do bot</h2>
          <p class="text-gray-600">
            Crie um bot com o @BotFather e cole aqui o token recebido.
          </p>
        </div>

        <div class="space-y-6">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">Token do BotFather</label>
            <input
              v-model="botToken"
              type="password"
              autocomplete="off"
              placeholder="123456789:AAH..."
              class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-2">Apelido (opcional)</label>
            <input
              v-model="name"
              type="text"
              placeholder="Meu bot"
              class="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent"
            />
          </div>

          <p v-if="error" class="text-sm text-red-600">{{ error }}</p>

          <button
            @click="submit"
            :disabled="loading"
            class="w-full px-6 py-3 bg-brand-500 text-white font-bold rounded-xl hover:bg-brand-600 transition-all disabled:opacity-50"
          >
            {{ loading ? 'Adicionando...' : 'Adicionar Bot' }}
          </button>
        </div>
      </div>
    </main>
  </div>
</template>
