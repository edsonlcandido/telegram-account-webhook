<template>
  <nav class="bg-white/80 backdrop-blur-lg shadow-lg sticky top-0 z-50 border-b border-gray-200">
    <div class="app-container">
      <div class="flex justify-between h-16 gap-2">
        <!-- Esquerda: Voltar + título da página -->
        <div class="flex items-center gap-3 min-w-0">
          <button
            v-if="backTo !== null"
            @click="onBack"
            class="flex items-center text-gray-600 hover:text-gray-900 flex-shrink-0"
            title="Voltar"
          >
            <ArrowLeftIcon class="w-5 h-5" />
            <span class="ml-1 font-semibold hidden sm:inline">Voltar</span>
          </button>
          <span class="text-xl sm:text-2xl font-bold text-brand-600 truncate">
            {{ title }}
          </span>
          <span v-if="subtitle" class="text-sm text-gray-600 truncate hidden md:inline">
            · {{ subtitle }}
          </span>
        </div>

        <!-- Direita: ações da página (slot) + cluster global -->
        <div class="flex items-center gap-2 sm:gap-3">
          <slot name="actions" />

          <router-link
            to="/docs"
            class="inline-flex items-center px-2 py-2 sm:px-3 text-sm font-medium text-gray-600 hover:text-brand-600 transition-colors"
            title="Documentação da API"
          >
            <svg class="h-5 w-5 sm:mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span class="hidden sm:inline">Docs</span>
          </router-link>

          <div class="flex items-center gap-2 sm:gap-3 px-2 sm:px-4 py-1.5 sm:py-2 bg-brand-50 rounded-full">
            <div class="w-7 h-7 sm:w-8 sm:h-8 bg-brand-600 rounded-full flex items-center justify-center flex-shrink-0">
              <UserCircleIcon class="h-4 w-4 sm:h-5 sm:w-5 text-white" />
            </div>
            <span class="hidden sm:inline text-sm font-semibold text-gray-700 truncate max-w-[8rem]">{{ userName }}</span>
          </div>

          <button
            @click="handleLogout"
            class="group inline-flex items-center px-2 py-2 sm:px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-red-500 hover:bg-red-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 transition-all transform hover:scale-105 shadow-lg"
            title="Sair"
          >
            <ArrowRightOnRectangleIcon class="h-5 w-5 sm:mr-2 group-hover:translate-x-1 transition-transform" />
            <span class="hidden sm:inline">Sair</span>
          </button>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import {
  ArrowLeftIcon,
  ArrowRightOnRectangleIcon,
  UserCircleIcon,
} from '@heroicons/vue/24/outline'

const props = withDefaults(
  defineProps<{
    /** Título da página (esquerda do menu) */
    title: string
    /** Complemento opcional do título (ex.: nome da conta) */
    subtitle?: string
    /** Destino do botão "Voltar". `null` esconde o botão. */
    backTo?: string | null
  }>(),
  { subtitle: undefined, backTo: '/dashboard' },
)

const emit = defineEmits<{ back: [] }>()

const router = useRouter()
const authStore = useAuthStore()

const userName = computed(() => {
  return authStore.user?.name || authStore.user?.email || 'Usuário'
})

/**
 * Emite `back` antes de navegar, para a página poder interceptar
 * (ex.: o wizard de Adicionar Conta, que volta um passo em vez de sair).
 */
function onBack() {
  emit('back')
  if (props.backTo) router.push(props.backTo)
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>