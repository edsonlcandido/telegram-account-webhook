import './style.css'

document.querySelector<HTMLDivElement>('#app')!.innerHTML = `
  <!-- Navigation -->
  <nav class="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-lg border-b border-gray-100">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex justify-between items-center h-16">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 bg-brand-500 rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
            </svg>
          </div>
          <span class="text-xl font-bold text-gray-900">Telegram Webhook Hub</span>
        </div>
        <div class="flex items-center gap-4">
          <a href="#features" class="hidden sm:block text-gray-600 hover:text-gray-900 transition-colors">Recursos</a>
          <a href="#how" class="hidden sm:block text-gray-600 hover:text-gray-900 transition-colors">Como Funciona</a>
          <a href="#pricing" class="hidden sm:block text-gray-600 hover:text-gray-900 transition-colors">Preço</a>
          <a href="/app/" class="inline-flex items-center px-4 py-2 bg-brand-500 text-white text-sm font-semibold rounded-lg hover:opacity-90 transition-all shadow-lg">
            Acessar Painel
            <svg class="w-4 h-4 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
            </svg>
          </a>
        </div>
      </div>
    </div>
  </nav>

  <!-- Hero Section -->
  <section class="min-h-screen flex items-center justify-center pt-16 pb-20 px-4 bg-gray-50">
    <div class="max-w-5xl mx-auto text-center">
      <!-- Badge -->
      <div class="inline-flex items-center gap-2 px-4 py-2 bg-accent-50 border border-accent-200 rounded-full mb-8">
        <span class="relative flex h-2 w-2">
          <span class="absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75 animate-ping"></span>
          <span class="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
        </span>
        <span class="text-sm text-accent-700 font-medium">100% Auto-hospedado • Sem mensalidade</span>
      </div>

      <!-- Title -->
      <h1 class="text-5xl md:text-7xl font-black text-gray-900 mb-6 leading-tight">
        Conecte seu Telegram a
        <span class="text-brand-500">qualquer automação</span>
      </h1>

      <!-- Subtitle -->
      <p class="text-xl md:text-2xl text-gray-600 max-w-2xl mx-auto mb-10">
        Receba mensagens do Telegram diretamente no seu N8N, Make ou qualquer webhook. 
        <strong>Em 2 minutos.</strong>
      </p>

      <!-- CTA Buttons -->
      <div class="flex flex-col sm:flex-row gap-4 justify-center mb-16">
        <a href="/app/" class="inline-flex items-center justify-center px-8 py-4 bg-brand-500 text-white text-lg font-bold rounded-xl hover:opacity-90 transition-all shadow-xl hover:scale-105">
          Começar Agora
          <svg class="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
          </svg>
        </a>
        <a href="#how" class="inline-flex items-center justify-center px-8 py-4 bg-white text-gray-700 text-lg font-bold rounded-xl hover:bg-gray-50 transition-all shadow-lg border border-gray-200 hover:border-gray-300">
          Ver Como Funciona
        </a>
      </div>

      <!-- Hero Image/Mockup -->
      <div class="relative max-w-3xl mx-auto">
        <div class="bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden">
          <div class="bg-gray-100 px-4 py-3 border-b border-gray-200 flex items-center gap-2">
            <div class="flex gap-1.5">
              <div class="w-3 h-3 rounded-full bg-red-400"></div>
              <div class="w-3 h-3 rounded-full bg-yellow-400"></div>
              <div class="w-3 h-3 rounded-full bg-green-400"></div>
            </div>
            <span class="text-xs text-gray-500 ml-2">Configuração de Webhook</span>
          </div>
          <div class="p-6 bg-gray-50">
            <div class="flex items-center gap-4 mb-6">
              <div class="w-12 h-12 bg-brand-100 rounded-full flex items-center justify-center">
                <svg class="w-6 h-6 text-brand-600" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
                </svg>
              </div>
              <div>
                <p class="font-semibold text-gray-900">+55 11 99999-9999</p>
                <p class="text-sm text-green-600">● Conectado</p>
              </div>
            </div>
            <div class="space-y-3 mb-6">
              <div class="flex items-center gap-3 p-3 bg-green-50 rounded-lg border border-green-200">
                <svg class="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
                <span class="text-sm text-green-800">Webhook configurado</span>
              </div>
              <div class="flex items-center gap-3 p-3 bg-brand-50 rounded-lg border border-brand-200">
                <svg class="w-5 h-5 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
                </svg>
                <span class="text-sm text-brand-800">n8n.automation.com/webhook/telegram</span>
              </div>
            </div>
            <div class="text-xs text-gray-500 bg-gray-100 rounded-lg p-4 font-mono">
              { "chat_id": -1001234567890, "message": "Nova mensagem!", "sender": "João" }
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- How It Works -->
  <section id="how" class="py-24 px-4 bg-white">
    <div class="max-w-6xl mx-auto">
      <div class="text-center mb-16">
        <span class="text-sm font-semibold text-accent-600 uppercase tracking-wider">Simples assim</span>
        <h2 class="text-4xl md:text-5xl font-bold text-gray-900 mt-3">Como Funciona</h2>
        <p class="text-xl text-gray-600 mt-4">Três passos para automatizar seu Telegram</p>
      </div>

      <div class="grid md:grid-cols-3 gap-8">
        <!-- Step 1 -->
        <div class="relative">
          <div class="absolute -top-4 -left-4 w-12 h-12 bg-brand-500 rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg z-10">1</div>
          <div class="bg-gray-50 rounded-2xl p-8 pt-12 h-full border-2 border-transparent hover:border-accent-200 transition-all hover:-translate-y-2">
            <div class="w-16 h-16 bg-brand-100 rounded-2xl flex items-center justify-center mb-6">
              <svg class="w-8 h-8 text-brand-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"/>
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-3">Conecte sua conta</h3>
            <p class="text-gray-600">Digite seu número e autorize o acesso. Sem senha do Telegram, apenas o código de verificação.</p>
          </div>
        </div>

        <!-- Step 2 -->
        <div class="relative">
          <div class="absolute -top-4 -left-4 w-12 h-12 bg-brand-500 rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg z-10">2</div>
          <div class="bg-gray-50 rounded-2xl p-8 pt-12 h-full border-2 border-transparent hover:border-accent-200 transition-all hover:-translate-y-2">
            <div class="w-16 h-16 bg-accent-100 rounded-2xl flex items-center justify-center mb-6">
              <svg class="w-8 h-8 text-accent-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/>
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-3">Configure seu webhook</h3>
            <p class="text-gray-600">Informe a URL do seu N8N, Make ou qualquer endpoint que recebe POST requests.</p>
          </div>
        </div>

        <!-- Step 3 -->
        <div class="relative">
          <div class="absolute -top-4 -left-4 w-12 h-12 bg-brand-500 rounded-xl flex items-center justify-center text-white font-bold text-xl shadow-lg z-10">3</div>
          <div class="bg-gray-50 rounded-2xl p-8 pt-12 h-full border-2 border-transparent hover:border-accent-200 transition-all hover:-translate-y-2">
            <div class="w-16 h-16 bg-green-100 rounded-2xl flex items-center justify-center mb-6">
              <svg class="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
              </svg>
            </div>
            <h3 class="text-xl font-bold text-gray-900 mb-3">Receba mensagens</h3>
            <p class="text-gray-600">Toda mensagem nova no seu Telegram é enviada automaticamente para sua automação.</p>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Features -->
  <section id="features" class="py-24 px-4 bg-gray-900 text-white">
    <div class="max-w-6xl mx-auto">
      <div class="text-center mb-16">
        <span class="text-sm font-semibold text-accent-400 uppercase tracking-wider">Recursos</span>
        <h2 class="text-4xl md:text-5xl font-bold mt-3">Tudo que você precisa</h2>
        <p class="text-xl text-gray-400 mt-4">Simples, poderoso e sob seu controle</p>
      </div>

      <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div class="bg-white/5 backdrop-blur-lg rounded-2xl p-6 border border-white/10 hover:bg-white/10 transition-all">
          <div class="w-12 h-12 bg-brand-500 rounded-xl flex items-center justify-center mb-4">
            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
            </svg>
          </div>
          <h3 class="text-lg font-bold mb-2">Múltiplas Contas</h3>
          <p class="text-gray-400 text-sm">Gerencie quantas contas Telegram quiser, cada uma com seu próprio webhook.</p>
        </div>

        <div class="bg-white/5 backdrop-blur-lg rounded-2xl p-6 border border-white/10 hover:bg-white/10 transition-all">
          <div class="w-12 h-12 bg-accent-500 rounded-xl flex items-center justify-center mb-4">
            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
            </svg>
          </div>
          <h3 class="text-lg font-bold mb-2">Webhooks Personalizados</h3>
          <p class="text-gray-400 text-sm">Cada conta pode ter uma URL de webhook diferente para automações distintas.</p>
        </div>

        <div class="bg-white/5 backdrop-blur-lg rounded-2xl p-6 border border-white/10 hover:bg-white/10 transition-all">
          <div class="w-12 h-12 bg-green-500 rounded-xl flex items-center justify-center mb-4">
            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
            </svg>
          </div>
          <h3 class="text-lg font-bold mb-2">100% Seguro</h3>
          <p class="text-gray-400 text-sm">Suas credenciais ficam no seu servidor. Ninguém vê seus dados.</p>
        </div>

        <div class="bg-white/5 backdrop-blur-lg rounded-2xl p-6 border border-white/10 hover:bg-white/10 transition-all">
          <div class="w-12 h-12 bg-orange-500 rounded-xl flex items-center justify-center mb-4">
            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
            </svg>
          </div>
          <h3 class="text-lg font-bold mb-2">Auto-reconexão</h3>
          <p class="text-gray-400 text-sm">Se a conexão cair, reconecta automaticamente. Fique online 24/7.</p>
        </div>

        <div class="bg-white/5 backdrop-blur-lg rounded-2xl p-6 border border-white/10 hover:bg-white/10 transition-all">
          <div class="w-12 h-12 bg-accent-500 rounded-xl flex items-center justify-center mb-4">
            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
            </svg>
          </div>
          <h3 class="text-lg font-bold mb-2">Integração N8N</h3>
          <p class="text-gray-400 text-sm">Webhook pronto para conectar com N8N, Make, Zapier ou qualquer API.</p>
        </div>

        <div class="bg-white/5 backdrop-blur-lg rounded-2xl p-6 border border-white/10 hover:bg-white/10 transition-all">
          <div class="w-12 h-12 bg-brand-500 rounded-xl flex items-center justify-center mb-4">
            <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"/>
            </svg>
          </div>
          <h3 class="text-lg font-bold mb-2">Deploy Simples</h3>
          <p class="text-gray-400 text-sm">Docker compose ou Easypanel. Sobe em minutos, não em horas.</p>
        </div>
      </div>
    </div>
  </section>

  <!-- Pricing -->
  <section id="pricing" class="py-24 px-4 bg-gray-50">
    <div class="max-w-4xl mx-auto">
      <div class="text-center mb-16">
        <span class="text-sm font-semibold text-accent-600 uppercase tracking-wider">Preço</span>
        <h2 class="text-4xl md:text-5xl font-bold text-gray-900 mt-3">Simples e justo</h2>
        <p class="text-xl text-gray-600 mt-4">Sem surpresas. Sem mensalidades.</p>
      </div>

      <div class="bg-gray-900 rounded-3xl p-8 md:p-12 text-white relative overflow-hidden">
        <div class="absolute top-0 right-0 w-64 h-64 bg-accent-500/20 rounded-full blur-3xl"></div>
        <div class="absolute bottom-0 left-0 w-64 h-64 bg-brand-500/20 rounded-full blur-3xl"></div>
        
        <div class="relative">
          <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-8">
            <div>
              <span class="inline-block px-4 py-1 bg-green-500/20 text-green-400 text-sm font-semibold rounded-full mb-4">
                GRÁTIS PARA SEMPRE
              </span>
              <h3 class="text-3xl font-bold mb-2">Você instala, você usa</h3>
              <p class="text-gray-400">Código aberto. Sem limites de uso.</p>
            </div>
            
            <div class="text-center md:text-right">
              <div class="text-5xl font-black mb-2">R$ 0</div>
              <p class="text-gray-400">Apenas o custo do seu servidor</p>
            </div>
          </div>

          <hr class="border-white/10 my-8">

          <div class="grid md:grid-cols-2 gap-6">
            <div class="flex items-start gap-3">
              <svg class="w-6 h-6 text-green-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
              </svg>
              <span class="text-gray-300">Contas Telegram ilimitadas</span>
            </div>
            <div class="flex items-start gap-3">
              <svg class="w-6 h-6 text-green-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
              </svg>
              <span class="text-gray-300">Mensagens ilimitadas</span>
            </div>
            <div class="flex items-start gap-3">
              <svg class="w-6 h-6 text-green-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
              </svg>
              <span class="text-gray-300">Webhooks ilimitados</span>
            </div>
            <div class="flex items-start gap-3">
              <svg class="w-6 h-6 text-green-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
              </svg>
              <span class="text-gray-300">Atualizações gratuitas</span>
            </div>
          </div>

          <div class="mt-10 text-center">
            <a href="/app/" class="inline-flex items-center justify-center px-8 py-4 bg-white text-gray-900 text-lg font-bold rounded-xl hover:bg-gray-100 transition-all shadow-xl">
              Começar Agora
              <svg class="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
              </svg>
            </a>
            <p class="text-gray-500 text-sm mt-4">Deploy em 5 minutos com Docker ou Easypanel</p>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- FAQ -->
  <section class="py-24 px-4 bg-white">
    <div class="max-w-3xl mx-auto">
      <div class="text-center mb-16">
        <h2 class="text-4xl font-bold text-gray-900">Perguntas Frequentes</h2>
      </div>

      <div class="space-y-6">
        <details class="group bg-gray-50 rounded-xl border border-gray-200">
          <summary class="flex items-center justify-between p-6 cursor-pointer font-semibold text-gray-900">
            O que é um webhook?
            <svg class="w-5 h-5 text-gray-500 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </summary>
          <div class="px-6 pb-6 text-gray-600">
            Um webhook é como um "aviso automático". Quando chega uma mensagem no seu Telegram, nosso servidor envia essa mensagem para a URL que você configurou (seu N8N, por exemplo).
          </div>
        </details>

        <details class="group bg-gray-50 rounded-xl border border-gray-200">
          <summary class="flex items-center justify-between p-6 cursor-pointer font-semibold text-gray-900">
            Preciso de um servidor próprio?
            <svg class="w-5 h-5 text-gray-500 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </summary>
          <div class="px-6 pb-6 text-gray-600">
            Sim, você precisa de um VPS (servidor virtual) para hospedar o Telegram Webhook Hub. Servidores como DigitalOcean, Vultr, ou o Easypanel funcionam perfeitamente.
          </div>
        </details>

        <details class="group bg-gray-50 rounded-xl border border-gray-200">
          <summary class="flex items-center justify-between p-6 cursor-pointer font-semibold text-gray-900">
            Minhas mensagens ficam salvas?
            <svg class="w-5 h-5 text-gray-500 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </summary>
          <div class="px-6 pb-6 text-gray-600">
            Não! As mensagens são apenas encaminhadas do Telegram para seu webhook e descartadas. Não armazenamos conteúdo de mensagens.
          </div>
        </details>

        <details class="group bg-gray-50 rounded-xl border border-gray-200">
          <summary class="flex items-center justify-between p-6 cursor-pointer font-semibold text-gray-900">
            Posso usar com N8N, Make ou Zapier?
            <svg class="w-5 h-5 text-gray-500 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </summary>
          <div class="px-6 pb-6 text-gray-600">
            Sim! Qualquer serviço que aceita webhooks (POST requests) funciona. N8N, Make, Zapier, IFTTT, ou até um servidor próprio.
          </div>
        </details>
      </div>
    </div>
  </section>

  <!-- CTA Section -->
  <section class="py-24 px-4 bg-brand-500">
    <div class="max-w-4xl mx-auto text-center text-white">
      <h2 class="text-4xl md:text-5xl font-bold mb-6">Pronto para automatizar?</h2>
      <p class="text-xl text-white/90 mb-10">Conecte seu Telegram em minutos e comece a criar automações poderosas.</p>
      <a href="/app/" class="inline-flex items-center justify-center px-10 py-5 bg-white text-accent-600 text-lg font-bold rounded-xl hover:bg-gray-100 transition-all shadow-2xl hover:scale-105">
        Criar Minha Conta Grátis
        <svg class="w-5 h-5 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
        </svg>
      </a>
    </div>
  </section>

  <!-- Footer -->
  <footer class="bg-gray-900 text-gray-400 py-12 px-4">
    <div class="max-w-6xl mx-auto">
      <div class="flex flex-col md:flex-row justify-between items-center gap-6">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 bg-brand-500 rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z"/>
            </svg>
          </div>
          <span class="text-lg font-semibold text-white">Telegram Webhook Hub</span>
        </div>
        
        <div class="flex items-center gap-6 text-sm">
          <a href="#features" class="hover:text-white transition-colors">Recursos</a>
          <a href="#how" class="hover:text-white transition-colors">Como Funciona</a>
          <a href="#pricing" class="hover:text-white transition-colors">Preço</a>
          <a href="https://github.com/edsonlcandido/telegram-account-webhook" target="_blank" class="hover:text-white transition-colors flex items-center gap-1">
            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
            </svg>
            GitHub
          </a>
        </div>
      </div>
      
      <hr class="border-gray-800 my-8">
      
      <div class="text-center text-sm">
        <p>&copy; 2026 Telegram Webhook Hub. Código aberto MIT.</p>
      </div>
    </div>
  </footer>
`
