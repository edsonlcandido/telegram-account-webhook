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
                  Seja bem-vindo de volta ao seu painel de controle
                </p>
              </div>
              <div class="hidden md:block">
                <div class="w-24 h-24 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center">
                  <span class="text-6xl">🎉</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Stats Grid -->
      <div class="px-4 py-6 sm:px-0">
        <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          <!-- Stat Card 1 -->
          <div class="group bg-white overflow-hidden shadow-xl rounded-2xl hover:shadow-2xl transition-all transform hover:-translate-y-1 border-2 border-transparent hover:border-blue-200">
            <div class="p-6">
              <div class="flex items-center">
                <div class="flex-shrink-0">
                  <div class="w-14 h-14 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg">
                    <ChartBarIcon class="h-7 w-7 text-white" />
                  </div>
                </div>
                <div class="ml-5 w-0 flex-1">
                  <dl>
                    <dt class="text-sm font-medium text-gray-500 truncate mb-1">
                      Total de Usuários
                    </dt>
                    <dd class="text-2xl font-bold text-gray-900">
                      1
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
            <div class="bg-gradient-to-r from-blue-50 to-blue-100 px-6 py-3">
              <p class="text-xs text-blue-700 font-medium">↗ Sistema ativo</p>
            </div>
          </div>

          <!-- Stat Card 2 -->
          <div class="group bg-white overflow-hidden shadow-xl rounded-2xl hover:shadow-2xl transition-all transform hover:-translate-y-1 border-2 border-transparent hover:border-green-200">
            <div class="p-6">
              <div class="flex items-center">
                <div class="flex-shrink-0">
                  <div class="w-14 h-14 bg-gradient-to-br from-green-500 to-green-600 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg">
                    <DocumentTextIcon class="h-7 w-7 text-white" />
                  </div>
                </div>
                <div class="ml-5 w-0 flex-1">
                  <dl>
                    <dt class="text-sm font-medium text-gray-500 truncate mb-1">
                      Documentos
                    </dt>
                    <dd class="text-2xl font-bold text-gray-900">
                      0
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
            <div class="bg-gradient-to-r from-green-50 to-green-100 px-6 py-3">
              <p class="text-xs text-green-700 font-medium">📄 Pronto para começar</p>
            </div>
          </div>

          <!-- Stat Card 3 -->
          <div class="group bg-white overflow-hidden shadow-xl rounded-2xl hover:shadow-2xl transition-all transform hover:-translate-y-1 border-2 border-transparent hover:border-purple-200">
            <div class="p-6">
              <div class="flex items-center">
                <div class="flex-shrink-0">
                  <div class="w-14 h-14 bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg">
                    <CheckCircleIcon class="h-7 w-7 text-white" />
                  </div>
                </div>
                <div class="ml-5 w-0 flex-1">
                  <dl>
                    <dt class="text-sm font-medium text-gray-500 truncate mb-1">
                      Status
                    </dt>
                    <dd class="text-2xl font-bold text-gray-900">
                      Ativo
                    </dd>
                  </dl>
                </div>
              </div>
            </div>
            <div class="bg-gradient-to-r from-purple-50 to-purple-100 px-6 py-3">
              <p class="text-xs text-purple-700 font-medium">✓ Tudo funcionando</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="px-4 py-6 sm:px-0">
        <div class="bg-white shadow-2xl rounded-2xl border border-gray-100">
          <div class="px-6 py-6 border-b border-gray-100">
            <h3 class="text-2xl font-bold text-gray-900 flex items-center">
              <span class="mr-3">⚡</span>
              Ações Rápidas
            </h3>
            <p class="text-gray-500 text-sm mt-1">Execute tarefas comuns rapidamente</p>
          </div>
          <div class="p-6">
            <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <button class="group relative flex items-center space-x-4 rounded-xl border-2 border-gray-200 bg-gradient-to-br from-white to-blue-50 px-6 py-6 shadow-lg hover:shadow-xl hover:border-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all transform hover:-translate-y-1">
                <div class="flex-shrink-0">
                  <div class="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-md">
                    <PlusCircleIcon class="h-6 w-6 text-white" />
                  </div>
                </div>
                <div class="min-w-0 flex-1 text-left">
                  <span class="text-base font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">Novo Item</span>
                  <p class="text-xs text-gray-500 mt-1">Criar um novo registro</p>
                </div>
              </button>

              <button class="group relative flex items-center space-x-4 rounded-xl border-2 border-gray-200 bg-gradient-to-br from-white to-purple-50 px-6 py-6 shadow-lg hover:shadow-xl hover:border-purple-300 focus:outline-none focus:ring-2 focus:ring-purple-500 transition-all transform hover:-translate-y-1">
                <div class="flex-shrink-0">
                  <div class="w-12 h-12 bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-md">
                    <CogIcon class="h-6 w-6 text-white" />
                  </div>
                </div>
                <div class="min-w-0 flex-1 text-left">
                  <span class="text-base font-semibold text-gray-900 group-hover:text-purple-600 transition-colors">Configurações</span>
                  <p class="text-xs text-gray-500 mt-1">Ajustar preferências</p>
                </div>
              </button>

              <a
                href="/"
                class="group relative flex items-center space-x-4 rounded-xl border-2 border-gray-200 bg-gradient-to-br from-white to-green-50 px-6 py-6 shadow-lg hover:shadow-xl hover:border-green-300 focus:outline-none focus:ring-2 focus:ring-green-500 transition-all transform hover:-translate-y-1"
              >
                <div class="flex-shrink-0">
                  <div class="w-12 h-12 bg-gradient-to-br from-green-500 to-green-600 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-md">
                    <HomeIcon class="h-6 w-6 text-white" />
                  </div>
                </div>
                <div class="min-w-0 flex-1 text-left">
                  <span class="text-base font-semibold text-gray-900 group-hover:text-green-600 transition-colors">Ir para Home</span>
                  <p class="text-xs text-gray-500 mt-1">Voltar à página inicial</p>
                </div>
              </a>
            </div>
          </div>
        </div>
      </div>

      <!-- Info Section -->
      <div class="px-4 py-6 sm:px-0">
        <div class="bg-gradient-to-r from-blue-50 via-purple-50 to-pink-50 border-l-4 border-blue-500 p-6 rounded-xl shadow-lg">
          <div class="flex">
            <div class="flex-shrink-0">
              <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-500 rounded-lg flex items-center justify-center">
                <InformationCircleIcon class="h-6 w-6 text-white" />
              </div>
            </div>
            <div class="ml-4 flex-1">
              <h4 class="text-lg font-semibold text-gray-900 mb-2">💡 Sobre este Template</h4>
              <p class="text-sm text-gray-700 leading-relaxed">
                Este é um template completo de dashboard usando <strong class="text-blue-600">PocketBase</strong> + 
                <strong class="text-green-600">Vue 3</strong> + 
                <strong class="text-purple-600">TypeScript</strong> + 
                <strong class="text-pink-600">Tailwind CSS</strong>.
                Você pode personalizar este dashboard de acordo com suas necessidades e criar aplicações incríveis! 🚀
              </p>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import {
  UserCircleIcon,
  ArrowRightOnRectangleIcon,
  ChartBarIcon,
  DocumentTextIcon,
  CheckCircleIcon,
  PlusCircleIcon,
  CogIcon,
  HomeIcon,
  InformationCircleIcon,
} from '@heroicons/vue/24/outline'

const router = useRouter()
const authStore = useAuthStore()

const userName = computed(() => {
  return authStore.user?.name || authStore.user?.email || 'Usuário'
})

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>
