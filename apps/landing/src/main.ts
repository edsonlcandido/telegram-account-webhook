import './style.css'

document.querySelector<HTMLDivElement>('#app')!.innerHTML = `
  <div class="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
    <!-- Navigation -->
    <nav class="bg-white/80 backdrop-blur-lg shadow-sm sticky top-0 z-50">
      <div class="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between items-center">
          <h1 class="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            PocketBase + Vue + Tailwind
          </h1>
          <a href="/app/" class="inline-flex items-center px-4 py-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white text-sm font-medium rounded-lg hover:from-blue-700 hover:to-purple-700 transition-all transform hover:scale-105 shadow-lg">
            Acessar App →
          </a>
        </div>
      </div>
    </nav>

    <main>
      <!-- Hero Section -->
      <div class="max-w-7xl mx-auto py-16 px-4 sm:px-6 lg:px-8">
        <div class="text-center mb-16">
          <div class="inline-block mb-6">
            <span class="px-4 py-2 bg-blue-100 text-blue-700 text-sm font-semibold rounded-full">
              ✨ Template Completo e Moderno
            </span>
          </div>
          <h2 class="text-5xl md:text-6xl font-extrabold text-gray-900 mb-6 leading-tight">
            Bem-vindo ao
            <span class="bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent">
              Futuro do Desenvolvimento
            </span>
          </h2>
          <p class="text-xl md:text-2xl text-gray-600 max-w-3xl mx-auto mb-10">
            Template completo para projetos com PocketBase + Vue 3 + TypeScript + Tailwind CSS.
            Tudo que você precisa para começar seu próximo projeto incrível! 🚀
          </p>
          
          <div class="flex flex-col sm:flex-row gap-4 justify-center">
            <a href="/app/" class="group inline-flex items-center justify-center px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white text-lg font-semibold rounded-xl hover:from-blue-700 hover:to-purple-700 transition-all transform hover:scale-105 shadow-2xl hover:shadow-blue-500/50">
              <span>Começar Agora</span>
              <svg class="ml-2 w-5 h-5 group-hover:translate-x-1 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"></path>
              </svg>
            </a>
            <a href="https://github.com/edsonlcandido/pocketbase-vue-tailwind-template" target="_blank" class="inline-flex items-center justify-center px-8 py-4 bg-white text-gray-800 text-lg font-semibold rounded-xl hover:bg-gray-50 transition-all transform hover:scale-105 shadow-xl border-2 border-gray-200">
              <svg class="w-6 h-6 mr-2" fill="currentColor" viewBox="0 0 24 24">
                <path fill-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clip-rule="evenodd"></path>
              </svg>
              Ver no GitHub
            </a>
          </div>
        </div>

        <!-- Feature Cards -->
        <div class="grid md:grid-cols-3 gap-8 mb-16">
          <div class="group p-8 bg-white rounded-2xl shadow-xl hover:shadow-2xl transition-all transform hover:-translate-y-2 border-2 border-transparent hover:border-blue-200">
            <div class="w-16 h-16 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center mb-5 group-hover:scale-110 transition-transform shadow-lg">
              <span class="text-4xl">🚀</span>
            </div>
            <h3 class="text-2xl font-bold mb-3 text-gray-900">PocketBase</h3>
            <p class="text-gray-600 leading-relaxed">Backend completo com autenticação, database e API RESTful. Tudo em um único executável!</p>
          </div>
          
          <div class="group p-8 bg-white rounded-2xl shadow-xl hover:shadow-2xl transition-all transform hover:-translate-y-2 border-2 border-transparent hover:border-green-200">
            <div class="w-16 h-16 bg-gradient-to-br from-green-500 to-green-600 rounded-2xl flex items-center justify-center mb-5 group-hover:scale-110 transition-transform shadow-lg">
              <span class="text-4xl">⚡</span>
            </div>
            <h3 class="text-2xl font-bold mb-3 text-gray-900">Vue 3 + TypeScript</h3>
            <p class="text-gray-600 leading-relaxed">Framework moderno e reativo com suporte completo a TypeScript para código type-safe.</p>
          </div>
          
          <div class="group p-8 bg-white rounded-2xl shadow-xl hover:shadow-2xl transition-all transform hover:-translate-y-2 border-2 border-transparent hover:border-purple-200">
            <div class="w-16 h-16 bg-gradient-to-br from-purple-500 to-purple-600 rounded-2xl flex items-center justify-center mb-5 group-hover:scale-110 transition-transform shadow-lg">
              <span class="text-4xl">🎨</span>
            </div>
            <h3 class="text-2xl font-bold mb-3 text-gray-900">Tailwind CSS v4</h3>
            <p class="text-gray-600 leading-relaxed">Estilização moderna, responsiva e performática com a última versão do Tailwind CSS.</p>
          </div>
        </div>

        <!-- Features List -->
        <div class="bg-white rounded-2xl shadow-2xl p-8 md:p-12 border border-gray-100">
          <div class="text-center mb-10">
            <h3 class="text-3xl font-bold text-gray-900 mb-3">Características Poderosas</h3>
            <p class="text-gray-600 text-lg">Tudo que você precisa para construir aplicações modernas</p>
          </div>
          
          <div class="grid md:grid-cols-2 gap-6">
            <div class="flex items-start space-x-4 p-4 rounded-xl hover:bg-blue-50 transition-colors">
              <div class="flex-shrink-0">
                <div class="w-8 h-8 bg-gradient-to-br from-green-400 to-green-500 rounded-lg flex items-center justify-center">
                  <span class="text-white text-xl font-bold">✓</span>
                </div>
              </div>
              <div>
                <h4 class="font-semibold text-gray-900 mb-1">Monorepo com Workspaces</h4>
                <p class="text-gray-600 text-sm">Landing Page + Web App em um único repositório organizado</p>
              </div>
            </div>
            
            <div class="flex items-start space-x-4 p-4 rounded-xl hover:bg-blue-50 transition-colors">
              <div class="flex-shrink-0">
                <div class="w-8 h-8 bg-gradient-to-br from-green-400 to-green-500 rounded-lg flex items-center justify-center">
                  <span class="text-white text-xl font-bold">✓</span>
                </div>
              </div>
              <div>
                <h4 class="font-semibold text-gray-900 mb-1">Autenticação Completa</h4>
                <p class="text-gray-600 text-sm">Sistema de auth pronto com PocketBase integrado</p>
              </div>
            </div>
            
            <div class="flex items-start space-x-4 p-4 rounded-xl hover:bg-blue-50 transition-colors">
              <div class="flex-shrink-0">
                <div class="w-8 h-8 bg-gradient-to-br from-green-400 to-green-500 rounded-lg flex items-center justify-center">
                  <span class="text-white text-xl font-bold">✓</span>
                </div>
              </div>
              <div>
                <h4 class="font-semibold text-gray-900 mb-1">Vue Router + Guards</h4>
                <p class="text-gray-600 text-sm">Rotas protegidas e navegação otimizada</p>
              </div>
            </div>
            
            <div class="flex items-start space-x-4 p-4 rounded-xl hover:bg-blue-50 transition-colors">
              <div class="flex-shrink-0">
                <div class="w-8 h-8 bg-gradient-to-br from-green-400 to-green-500 rounded-lg flex items-center justify-center">
                  <span class="text-white text-xl font-bold">✓</span>
                </div>
              </div>
              <div>
                <h4 class="font-semibold text-gray-900 mb-1">State Management</h4>
                <p class="text-gray-600 text-sm">Pinia para gerenciamento de estado moderno</p>
              </div>
            </div>
            
            <div class="flex items-start space-x-4 p-4 rounded-xl hover:bg-blue-50 transition-colors">
              <div class="flex-shrink-0">
                <div class="w-8 h-8 bg-gradient-to-br from-green-400 to-green-500 rounded-lg flex items-center justify-center">
                  <span class="text-white text-xl font-bold">✓</span>
                </div>
              </div>
              <div>
                <h4 class="font-semibold text-gray-900 mb-1">Vite Super Rápido</h4>
                <p class="text-gray-600 text-sm">Build tool moderno com proxy configurado</p>
              </div>
            </div>
            
            <div class="flex items-start space-x-4 p-4 rounded-xl hover:bg-blue-50 transition-colors">
              <div class="flex-shrink-0">
                <div class="w-8 h-8 bg-gradient-to-br from-green-400 to-green-500 rounded-lg flex items-center justify-center">
                  <span class="text-white text-xl font-bold">✓</span>
                </div>
              </div>
              <div>
                <h4 class="font-semibold text-gray-900 mb-1">Docker Ready</h4>
                <p class="text-gray-600 text-sm">Dockerfile multi-stage otimizado para produção</p>
              </div>
            </div>
            
            <div class="flex items-start space-x-4 p-4 rounded-xl hover:bg-blue-50 transition-colors">
              <div class="flex-shrink-0">
                <div class="w-8 h-8 bg-gradient-to-br from-green-400 to-green-500 rounded-lg flex items-center justify-center">
                  <span class="text-white text-xl font-bold">✓</span>
                </div>
              </div>
              <div>
                <h4 class="font-semibold text-gray-900 mb-1">Deploy Automatizado</h4>
                <p class="text-gray-600 text-sm">Scripts prontos para build e deploy</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- Footer -->
    <footer class="bg-white/80 backdrop-blur-lg border-t border-gray-200 mt-20">
      <div class="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        <div class="text-center">
          <p class="text-gray-600 mb-2">
            Feito com <span class="text-red-500">❤️</span> usando PocketBase, Vue 3 e Tailwind CSS
          </p>
          <p class="text-gray-500 text-sm">&copy; 2026 PocketBase Vue Tailwind Template. MIT License.</p>
        </div>
      </div>
    </footer>
  </div>
`
