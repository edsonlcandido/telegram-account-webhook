<template>
  <div class="min-h-screen bg-gray-50">
    <!-- Navigation -->
    <nav class="bg-white/80 backdrop-blur-lg shadow-lg sticky top-0 z-50 border-b border-gray-200">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16 gap-2">
          <div class="flex items-center min-w-0">
            <h1 class="text-xl sm:text-2xl font-bold text-brand-600 truncate">
              Dashboard
            </h1>
          </div>
          <div class="flex items-center gap-2 sm:gap-3">
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

    <!-- Main Content -->
    <main class="max-w-7xl mx-auto py-8 sm:px-6 lg:px-8">
      <!-- Welcome Section -->
      <div class="px-4 py-6 sm:px-0">
        <div class="bg-brand-500 overflow-hidden shadow-2xl rounded-2xl transform hover:scale-[1.02] transition-all">
          <div class="p-5 sm:p-8 text-white">
            <div class="flex items-center justify-between gap-4">
              <div class="min-w-0">
                <h2 class="text-2xl sm:text-3xl md:text-4xl font-bold mb-2 sm:mb-3 truncate">
                  Olá, {{ userName }}! 👋
                </h2>
                <p class="text-brand-100 text-sm sm:text-base md:text-lg">
                  Gerencie suas contas Telegram e webhooks
                </p>
              </div>
              <div class="hidden md:block flex-shrink-0">
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
          <div class="group bg-white overflow-hidden shadow-xl rounded-2xl hover:shadow-2xl transition-all transform hover:-translate-y-1 border-2 border-transparent hover:border-brand-200">
            <div class="p-6">
              <div class="flex items-center">
                <div class="flex-shrink-0">
                  <div class="w-14 h-14 bg-brand-500 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg">
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
            <div class="bg-brand-50 px-6 py-3">
              <p class="text-xs text-brand-700 font-medium">
                {{ telegramStore.activeSessions().length }} ativa(s)
              </p>
            </div>
          </div>

          <!-- Stat Card: Webhooks -->
          <div class="group bg-white overflow-hidden shadow-xl rounded-2xl hover:shadow-2xl transition-all transform hover:-translate-y-1 border-2 border-transparent hover:border-green-200">
            <div class="p-6">
              <div class="flex items-center">
                <div class="flex-shrink-0">
                  <div class="w-14 h-14 bg-accent-500 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg">
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
            <div class="bg-accent-50 px-6 py-3">
              <p class="text-xs text-accent-700 font-medium">
                {{ telegramStore.sessions.length - configuredWebhooks }} pendente(s)
              </p>
            </div>
          </div>

          <!-- Stat Card: Status -->
          <div class="group bg-white overflow-hidden shadow-xl rounded-2xl hover:shadow-2xl transition-all transform hover:-translate-y-1 border-2 border-transparent hover:border-accent-200">
            <div class="p-6">
              <div class="flex items-center">
                <div class="flex-shrink-0">
                  <div class="w-14 h-14 bg-green-500 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform shadow-lg">
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
            <div class="bg-accent-50 px-6 py-3">
              <p class="text-xs text-accent-700 font-medium">
                Sistema {{ telegramStore.error ? '⚠️' : '✓' }} ativo
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- Accounts Section -->
      <div class="px-4 py-6 sm:px-0">
        <div class="bg-white shadow-2xl rounded-2xl border border-gray-100">
          <div class="px-4 py-5 sm:px-6 sm:py-6 border-b border-gray-100 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div class="min-w-0">
              <h3 class="text-xl sm:text-2xl font-bold text-gray-900 flex items-center">
                <span class="mr-3">📱</span>
                Contas Telegram
              </h3>
              <p class="text-gray-500 text-sm mt-1">Gerencie suas contas vinculadas</p>
            </div>
            <button
              @click="router.push('/add-telegram')"
              class="w-full sm:w-auto inline-flex items-center justify-center px-5 py-2.5 sm:px-6 sm:py-3 bg-brand-500 text-white font-bold rounded-xl hover:bg-brand-600 transition-all transform hover:scale-105 shadow-lg text-sm sm:text-base"
            >
              <PlusIcon class="h-5 w-5 mr-2" />
              Adicionar Conta
            </button>
          </div>

          <!-- Loading -->
          <div v-if="telegramStore.loading && telegramStore.sessions.length === 0" class="p-12 flex justify-center">
            <div class="w-12 h-12 border-4 border-brand-500 border-t-transparent rounded-full animate-spin"></div>
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
              class="inline-flex items-center px-6 py-3 bg-brand-500 text-white font-bold rounded-xl hover:bg-brand-600 transition-all"
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
              class="p-4 sm:p-6 hover:bg-gray-50 transition-colors"
            >
              <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <!-- Account Info -->
                <div class="flex items-center gap-3 sm:gap-4 min-w-0 flex-1">
                  <!-- Avatar (sempre últimos 4 dígitos do telefone) -->
                  <div class="w-12 h-12 sm:w-14 sm:h-14 bg-brand-500 rounded-full flex items-center justify-center text-white text-base sm:text-xl font-bold flex-shrink-0">
                    {{ session.phone.slice(-4) }}
                  </div>

                  <div class="min-w-0 flex-1">
                    <div class="flex items-center gap-2 min-w-0">
                      <p class="font-semibold text-gray-900 truncate text-sm sm:text-base">
                        {{ session.name || formatPhone(session.phone) }}
                      </p>
                      <button
                        @click="openRenameModal(session)"
                        class="text-gray-400 hover:text-brand-600 flex-shrink-0"
                        :title="session.name ? 'Editar apelido' : 'Definir apelido'"
                      >
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                        </svg>
                      </button>
                    </div>
                    <p v-if="session.name" class="text-xs text-gray-500 mt-0.5 truncate">{{ formatPhone(session.phone) }}</p>
                    <div class="flex items-center gap-2 mt-1 flex-wrap">
                      <span
                        class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                        :class="session.active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'"
                      >
                        <span class="w-1.5 h-1.5 rounded-full mr-1" :class="session.active ? 'bg-green-500' : 'bg-red-500'"></span>
                        {{ session.active ? 'Online' : 'Offline' }}
                      </span>
                      <span
                        class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
                        :class="session.webhook_count > 0 ? 'bg-brand-100 text-brand-800' : 'bg-yellow-100 text-yellow-800'"
                      >
                        {{ session.webhook_count > 0 ? `${session.webhook_count} webhook${session.webhook_count > 1 ? 's' : ''}` : 'Sem webhook' }}
                      </span>
                    </div>
                  </div>
                </div>

                <!-- Actions — empilha no mobile, inline no sm+ -->
                <div class="grid grid-cols-2 gap-2 sm:flex sm:items-center sm:gap-3 sm:flex-shrink-0">
                  <button
                    @click="router.push(`/webhooks/${session.session_id}`)"
                    class="inline-flex items-center justify-center px-2 py-2 sm:px-4 sm:py-2 border border-brand-300 text-brand-600 font-medium rounded-lg hover:bg-brand-50 transition-colors text-xs sm:text-sm"
                    :title="session.webhook_count > 0 ? 'Gerenciar webhooks' : 'Configurar primeiro webhook'"
                  >
                    <svg class="h-4 w-4 sm:mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                    <span class="hidden sm:inline">Webhooks</span>
                  </button>

                  <button
                    @click="router.push(`/messages/${session.session_id}`)"
                    class="inline-flex items-center justify-center px-2 py-2 sm:px-4 sm:py-2 border border-accent-300 text-accent-600 font-medium rounded-lg hover:bg-accent-50 transition-colors text-xs sm:text-sm"
                    title="Ver mensagens"
                  >
                    <svg class="h-4 w-4 sm:mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                    <span class="hidden sm:inline">Mensagens</span>
                  </button>

                  <button
                    @click="confirmDelete(session)"
                    class="inline-flex items-center justify-center px-2 py-2 sm:px-4 sm:py-2 border border-red-300 text-red-600 font-medium rounded-lg hover:bg-red-50 transition-colors text-xs sm:text-sm"
                    title="Remover conta"
                  >
                    <svg class="h-4 w-4 sm:mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    <span class="hidden sm:inline">Remover</span>
                  </button>
                </div>
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
              <p class="text-gray-600 mb-3">
                Tem certeza que deseja remover a conta <strong>{{ deleteModal.session?.phone }}</strong>?
                Esta ação não pode ser desfeita.
              </p>
              <p class="text-xs text-left text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-6 leading-relaxed">
                A conta é desconectada e apagada do servidor. No PocketBase o
                registro da sessão também é removido, e isso apaga
                <strong>todos os webhooks</strong> e
                <strong>todas as mensagens</strong> do histórico.
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
                  class="flex-1 px-4 py-3 bg-red-500 text-white font-medium rounded-xl hover:bg-red-600 disabled:opacity-50 transition-all"
                >
                  {{ deleteModal.loading ? 'Removendo...' : 'Remover' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Rename (alias) Modal -->
    <Teleport to="body">
      <div v-if="renameModal.show" class="fixed inset-0 z-50 overflow-y-auto">
        <div class="flex min-h-full items-center justify-center p-4">
          <div class="fixed inset-0 bg-black/50 transition-opacity" @click="closeRenameModal"></div>
          <div class="relative bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <h3 class="text-xl font-bold text-gray-900 mb-1">
              {{ renameModal.session?.name ? 'Editar apelido' : 'Definir apelido' }}
            </h3>
            <p class="text-sm text-gray-500 mb-6">
              Identifica a conta na dashboard. Se vazio, o número é usado.
            </p>

            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Apelido</label>
                <input
                  v-model="renameModal.name"
                  type="text"
                  maxlength="60"
                  placeholder="ex.: Suporte, Vendas, Pessoal"
                  class="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-brand-500 focus:outline-none"
                  :disabled="renameModal.saving"
                  @keyup.enter="saveRename"
                />
                <p class="mt-1 text-xs text-gray-500">
                  {{ renameModal.name.length }} / 60 caracteres
                </p>
              </div>
              <div v-if="renameModal.error" class="p-3 rounded-lg bg-red-50 border border-red-200">
                <p class="text-sm text-red-700">{{ renameModal.error }}</p>
              </div>
            </div>

            <div class="flex gap-3 mt-6">
              <button
                @click="closeRenameModal"
                :disabled="renameModal.saving"
                class="flex-1 px-4 py-3 border border-gray-300 text-gray-700 font-medium rounded-xl hover:bg-gray-50 disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                @click="saveRename"
                :disabled="renameModal.saving"
                class="flex-1 px-4 py-3 bg-brand-500 text-white font-medium rounded-xl hover:bg-brand-600 disabled:opacity-50"
              >
                {{ renameModal.saving ? 'Salvando...' : 'Salvar' }}
              </button>
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
                  class="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-brand-500 focus:outline-none"
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
                  class="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-brand-500 focus:outline-none"
                  :disabled="sendModal.loading"
                />
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Formato</label>
                <select
                  v-model="sendModal.parseMode"
                  class="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-brand-500 focus:outline-none bg-white"
                  :disabled="sendModal.loading"
                >
                  <option value="plain">Texto simples</option>
                  <option value="html">HTML básico (negrito, itálico, links...)</option>
                </select>
                <p class="mt-1 text-xs text-gray-500" v-if="sendModal.parseMode === 'html'">
                  Tags aceitas: &lt;b&gt;, &lt;i&gt;, &lt;u&gt;, &lt;s&gt;, &lt;code&gt;, &lt;pre&gt; e &lt;a href="..."&gt;.
                </p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">
                  Imagem (URL, opcional)
                </label>
                <input
                  v-model="sendModal.imageUrl"
                  type="url"
                  placeholder="https://exemplo.com/foto.jpg"
                  class="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-brand-500 focus:outline-none"
                  :disabled="sendModal.loading"
                />
                <p class="mt-1 text-xs text-gray-500">
                  Se preenchida, vira foto. Com texto junto, o texto vira caption.
                </p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-700 mb-2">Mensagem</label>
                <textarea
                  v-model="sendModal.text"
                  rows="4"
                  placeholder="Digite a mensagem..."
                  class="w-full px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-brand-500 focus:outline-none resize-none"
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
                class="flex-1 px-4 py-3 bg-brand-500 text-white font-medium rounded-xl hover:bg-brand-600 disabled:opacity-50 transition-all"
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
import { computed, onMounted, reactive } from 'vue'
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
  return telegramStore.sessions.reduce((acc, s) => acc + (s.webhook_count || 0), 0)
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

// Modal de renomear (alias)
const renameModal = reactive({
  show: false,
  session: null as TelegramSession | null,
  name: '',
  saving: false,
  error: '',
})

function openRenameModal(session: TelegramSession) {
  renameModal.session = session
  renameModal.name = session.name || ''
  renameModal.error = ''
  renameModal.show = true
}

function closeRenameModal() {
  if (renameModal.saving) return
  renameModal.show = false
  renameModal.session = null
  renameModal.error = ''
}

async function saveRename() {
  if (!renameModal.session) return
  const newName = renameModal.name.trim()
  if (newName.length > 60) {
    renameModal.error = 'Máximo 60 caracteres'
    return
  }
  renameModal.saving = true
  renameModal.error = ''
  try {
    await telegramStore.setSessionName(renameModal.session.session_id, newName)
    renameModal.show = false
    renameModal.session = null
  } catch (e: any) {
    renameModal.error = e?.message || 'Erro ao renomear'
  } finally {
    renameModal.saving = false
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
  parseMode: 'plain' as 'plain' | 'html',
  imageUrl: '',
  replyTo: null as number | null,
  loading: false,
  result: null as { success: boolean; message_id?: number; message?: string } | null,
})

const canSend = computed(() => {
  const hasText = sendModal.text.trim() !== ''
  const hasImage = sendModal.imageUrl.trim() !== ''
  return sendModal.chatId.trim() !== '' && (hasText || hasImage)
})

function openSendModal(session: TelegramSession) {
  sendModal.session = session
  sendModal.chatId = ''
  sendModal.text = ''
  sendModal.parseMode = 'plain'
  sendModal.imageUrl = ''
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

    const res = await telegramApi.sendMessage({
      session_id: sendModal.session.session_id,
      chat_id: chatId,
      text: sendModal.text.trim() || undefined,
      parse_mode: sendModal.parseMode,
      image_url: sendModal.imageUrl.trim() || undefined,
      reply_to_message_id: sendModal.replyTo ?? undefined,
    })
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
