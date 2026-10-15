<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// Blocos de payload prontos pra copiar
const INCOMING_PAYLOAD = JSON.stringify(
  {
    session_id: 'account_5511999998888',
    message_id: 1234,
    chat_id: 5511988887777,
    chat_type: 'private',
    chat_title: 'Maria Silva',
    outgoing: false,
    text: 'oi, tudo bem?',
    sender_id: 5511988887777,
    sender_name: 'Maria Silva',
    sender_username: 'maria',
    is_reply: false,
    reply_to_message_id: null,
    has_media: false,
    media_type: null,
    media_mime_type: null,
    timestamp: '2026-10-13T20:51:03.123456',
  },
  null,
  2,
)

const SEND_MESSAGE_PAYLOAD = JSON.stringify(
  {
    session_id: 'account_5511999998888',
    chat_id: 5511988887777,
    text: '<b>Recebido!</b> Já te respondo.',
    parse_mode: 'html',
    image_url: null,
    reply_to_message_id: 1234,
  },
  null,
  2,
)

const SEND_MESSAGE_RESPONSE = JSON.stringify(
  {
    success: true,
    message_id: 1235,
    chat_id: 5511988887777,
    timestamp: '2026-10-13T20:51:05.654321',
    is_reply: true,
    parse_mode: 'html',
    has_media: false,
    media_type: null,
  },
  null,
  2,
)

const SEND_IMAGE_PAYLOAD = JSON.stringify(
  {
    session_id: 'account_5511999998888',
    chat_id: 5511988887777,
    text: 'Olha essa foto',
    image_url: 'https://exemplo.com/foto.jpg',
  },
  null,
  2,
)

const TEST_PAYLOAD = JSON.stringify(
  {
    type: 'test',
    message: 'Conexão OK!',
    timestamp: '2026-10-13T20:51:03.123456',
  },
  null,
  2,
)

const CURL_REPLY = `# Responde à mensagem que chegou no webhook. Requer o token PB.
curl -X POST https://api-telegram.ehtudo.app/api/send-message \\
  -H "Content-Type: application/json" \\
  -H "Authorization: SEU_TOKEN_PB" \\
  -d '${SEND_MESSAGE_PAYLOAD.replace(/\n/g, '')}'`

// Estado do botão "Copiar" (qual bloco foi copiado por último)
const copied = ref<string | null>(null)

async function copy(key: string, text: string) {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = key
    setTimeout(() => {
      if (copied.value === key) copied.value = null
    }, 1500)
  } catch {
    // fallback: cria textarea temporária
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    try {
      document.execCommand('copy')
      copied.value = key
      setTimeout(() => {
        if (copied.value === key) copied.value = null
      }, 1500)
    } finally {
      document.body.removeChild(ta)
    }
  }
}

function goBack() {
  router.push('/dashboard')
}
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-50 via-blue-50 to-purple-50">
    <!-- Navigation -->
    <nav class="bg-white/80 backdrop-blur-lg shadow-lg sticky top-0 z-50 border-b border-gray-200">
      <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex justify-between h-16">
          <div class="flex items-center">
            <button @click="goBack" class="flex items-center text-gray-600 hover:text-gray-900">
              <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M15 19l-7-7 7-7"
                />
              </svg>
              <span class="font-semibold">Voltar</span>
            </button>
          </div>
          <div class="flex items-center">
            <span
              class="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent"
            >
              Documentação da API
            </span>
          </div>
        </div>
      </div>
    </nav>

    <main class="max-w-4xl mx-auto py-8 px-4 space-y-6">
      <!-- Intro -->
      <div class="bg-white rounded-2xl shadow-xl p-8">
        <h1 class="text-3xl font-bold text-gray-900 mb-3">Como funciona o webhook</h1>
        <p class="text-gray-600 leading-relaxed">
          Quando chega uma mensagem numa conta Telegram vinculada, o backend faz
          <code class="px-1.5 py-0.5 bg-gray-100 rounded text-sm">POST</code> na
          <code class="px-1.5 py-0.5 bg-gray-100 rounded text-sm">webhook_url</code>
          configurada. Sua URL recebe o payload abaixo, processa e, se quiser
          responder, chama
          <code class="px-1.5 py-0.5 bg-gray-100 rounded text-sm">/api/send-message</code>
          com o <code class="px-1.5 py-0.5 bg-gray-100 rounded text-sm">session_id</code>
          e <code class="px-1.5 py-0.5 bg-gray-100 rounded text-sm">chat_id</code>
          recebidos.
        </p>
      </div>

      <!-- 1. POST recebido -->
      <section class="bg-white rounded-2xl shadow-xl overflow-hidden">
        <div class="bg-gradient-to-r from-blue-500 to-blue-600 px-6 py-4">
          <h2 class="text-xl font-bold text-white flex items-center gap-2">
            <span class="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center font-bold">1</span>
            POST que você recebe na sua URL
          </h2>
          <p class="text-blue-100 text-sm mt-1">
            Disparado a cada mensagem nova (incoming ou outgoing da própria conta).
          </p>
        </div>

        <div class="p-6 space-y-4">
          <div class="flex items-center justify-between">
            <p class="font-semibold text-gray-800">Payload (JSON)</p>
            <button
              @click="copy('in', INCOMING_PAYLOAD)"
              class="text-xs px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 font-medium"
            >
              {{ copied === 'in' ? '✓ Copiado' : 'Copiar' }}
            </button>
          </div>
          <pre class="bg-gray-900 text-gray-100 text-xs rounded-xl p-4 overflow-x-auto leading-relaxed"><code>{{ INCOMING_PAYLOAD }}</code></pre>

          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="text-left text-gray-500 border-b border-gray-200">
                <tr>
                  <th class="py-2 pr-4">Campo</th>
                  <th class="py-2 pr-4">Tipo</th>
                  <th class="py-2">Descrição</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-100 text-gray-700">
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">session_id</td>
                  <td class="py-2 pr-4">string</td>
                  <td class="py-2">ID da conta que recebeu. Use no callback.</td>
                </tr>
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">message_id</td>
                  <td class="py-2 pr-4">int</td>
                  <td class="py-2">ID da mensagem no Telegram. Use em <code>reply_to_message_id</code>.</td>
                </tr>
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">chat_id</td>
                  <td class="py-2 pr-4">int</td>
                  <td class="py-2">ID do chat. Use no callback.</td>
                </tr>
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">chat_type</td>
                  <td class="py-2 pr-4">string</td>
                  <td class="py-2"><code>private</code> · <code>group</code> · <code>supergroup</code> · <code>channel</code> · <code>unknown</code></td>
                </tr>
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">chat_title</td>
                  <td class="py-2 pr-4">string?</td>
                  <td class="py-2">Nome do chat ou do peer (em private).</td>
                </tr>
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">outgoing</td>
                  <td class="py-2 pr-4">bool</td>
                  <td class="py-2"><code>true</code> = a própria conta enviou (celular/desktop). Pode filtrar/ignorar.</td>
                </tr>
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">text</td>
                  <td class="py-2 pr-4">string</td>
                  <td class="py-2">Conteúdo. Vazio se for só mídia.</td>
                </tr>
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">sender_id / sender_name / sender_username</td>
                  <td class="py-2 pr-4">int? / string? / string?</td>
                  <td class="py-2">Identificação do remetente. <code>username</code> pode ser <code>null</code>.</td>
                </tr>
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">is_reply</td>
                  <td class="py-2 pr-4">bool</td>
                  <td class="py-2">Se a mensagem é reply de outra.</td>
                </tr>
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">reply_to_message_id</td>
                  <td class="py-2 pr-4">int?</td>
                  <td class="py-2">ID da mensagem respondida (se <code>is_reply=true</code>).</td>
                </tr>
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">has_media</td>
                  <td class="py-2 pr-4">bool</td>
                  <td class="py-2">Se tem mídia anexa.</td>
                </tr>
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">media_type</td>
                  <td class="py-2 pr-4">string?</td>
                  <td class="py-2"><code>photo</code> · <code>video</code> · <code>voice</code> · <code>audio</code> · <code>document</code> · <code>sticker</code> · <code>geo</code> · <code>contact</code> · <code>poll</code></td>
                </tr>
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">media_mime_type</td>
                  <td class="py-2 pr-4">string?</td>
                  <td class="py-2">MIME quando aplicável (ex: <code>image/jpeg</code>).</td>
                </tr>
                <tr>
                  <td class="py-2 pr-4 font-mono text-xs">timestamp</td>
                  <td class="py-2 pr-4">ISO 8601</td>
                  <td class="py-2">Quando o backend processou.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- 2. POST de resposta -->
      <section class="bg-white rounded-2xl shadow-xl overflow-hidden">
        <div class="bg-gradient-to-r from-green-500 to-emerald-600 px-6 py-4">
          <h2 class="text-xl font-bold text-white flex items-center gap-2">
            <span class="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center font-bold">2</span>
            POST pra responder — <code class="font-mono">/api/send-message</code>
          </h2>
          <p class="text-green-100 text-sm mt-1">
            Chame isso no seu endpoint pra enviar a resposta. Requer o token PB no header.
          </p>
        </div>

        <div class="p-6 space-y-6">
          <div>
            <p class="font-semibold text-gray-800 mb-2">Request</p>
            <div class="bg-gray-50 rounded-xl p-3 text-xs font-mono text-gray-700 mb-3">
              POST https://api-telegram.ehtudo.app/api/send-message<br />
              Content-Type: application/json<br />
              Authorization: &lt;token PB&gt;
            </div>
            <div class="flex items-center justify-between mb-2">
              <p class="text-sm text-gray-500">Body</p>
              <button
                @click="copy('send', SEND_MESSAGE_PAYLOAD)"
                class="text-xs px-3 py-1.5 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 font-medium"
              >
                {{ copied === 'send' ? '✓ Copiado' : 'Copiar' }}
              </button>
            </div>
            <pre class="bg-gray-900 text-gray-100 text-xs rounded-xl p-4 overflow-x-auto leading-relaxed"><code>{{ SEND_MESSAGE_PAYLOAD }}</code></pre>
          </div>

          <div>
            <p class="font-semibold text-gray-800 mb-2">Resposta (200)</p>
            <div class="flex items-center justify-between mb-2">
              <p class="text-sm text-gray-500">Body</p>
              <button
                @click="copy('resp', SEND_MESSAGE_RESPONSE)"
                class="text-xs px-3 py-1.5 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 font-medium"
              >
                {{ copied === 'resp' ? '✓ Copiado' : 'Copiar' }}
              </button>
            </div>
            <pre class="bg-gray-900 text-gray-100 text-xs rounded-xl p-4 overflow-x-auto leading-relaxed"><code>{{ SEND_MESSAGE_RESPONSE }}</code></pre>
          </div>

          <div>
            <p class="font-semibold text-gray-800 mb-2">Exemplo com curl</p>
            <div class="flex items-center justify-between mb-2">
              <p class="text-sm text-gray-500">Comando</p>
              <button
                @click="copy('curl', CURL_REPLY)"
                class="text-xs px-3 py-1.5 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 font-medium"
              >
                {{ copied === 'curl' ? '✓ Copiado' : 'Copiar' }}
              </button>
            </div>
            <pre class="bg-gray-900 text-gray-100 text-xs rounded-xl p-4 overflow-x-auto leading-relaxed whitespace-pre"><code>{{ CURL_REPLY }}</code></pre>
          </div>

          <div>
            <p class="font-semibold text-gray-800 mb-2">Modos suportados</p>
            <p class="text-sm text-gray-600 mb-3">
              O mesmo endpoint cobre 3 modos. Os campos <code>parse_mode</code> e
              <code>image_url</code> são opcionais; mande o que precisar.
            </p>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div class="bg-gray-50 rounded-xl p-3 border border-gray-200">
                <p class="font-semibold text-gray-800 mb-1">1. Texto simples</p>
                <code class="text-gray-600">{"text": "oi"}</code>
                <p class="text-gray-500 mt-1">Default. Não interpreta formatação.</p>
              </div>
              <div class="bg-gray-50 rounded-xl p-3 border border-gray-200">
                <p class="font-semibold text-gray-800 mb-1">2. Texto com HTML</p>
                <code class="text-gray-600">{"text": "&lt;b&gt;oi&lt;/b&gt;", "parse_mode": "html"}</code>
                <p class="text-gray-500 mt-1">Subset Telegram: &lt;b&gt;, &lt;i&gt;, &lt;u&gt;, &lt;s&gt;, &lt;code&gt;, &lt;pre&gt;, &lt;a href&gt;.</p>
              </div>
              <div class="bg-gray-50 rounded-xl p-3 border border-gray-200">
                <p class="font-semibold text-gray-800 mb-1">3. Imagem via URL</p>
                <code class="text-gray-600">{"text": "...", "image_url": "https://..."}</code>
                <p class="text-gray-500 mt-1">
                  Foto legendada. Sem <code>text</code>, vai sem caption.
                </p>
              </div>
            </div>
            <div class="mt-3 flex items-center justify-between">
              <p class="text-xs text-gray-500">Exemplo de envio de imagem:</p>
              <button
                @click="copy('image', SEND_IMAGE_PAYLOAD)"
                class="text-xs px-3 py-1.5 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 font-medium"
              >
                {{ copied === 'image' ? '✓ Copiado' : 'Copiar' }}
              </button>
            </div>
            <pre class="bg-gray-900 text-gray-100 text-xs rounded-xl p-4 overflow-x-auto leading-relaxed mt-2"><code>{{ SEND_IMAGE_PAYLOAD }}</code></pre>
          </div>
        </div>
      </section>

      <!-- 3. Webhook de teste -->
      <section class="bg-white rounded-2xl shadow-xl overflow-hidden">
        <div class="bg-gradient-to-r from-yellow-500 to-orange-500 px-6 py-4">
          <h2 class="text-xl font-bold text-white flex items-center gap-2">
            <span class="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center font-bold">3</span>
            POST do botão "Testar Webhook"
          </h2>
          <p class="text-yellow-50 text-sm mt-1">
            Disparado manualmente pela tela de configuração pra validar a URL.
          </p>
        </div>
        <div class="p-6 space-y-4">
          <p class="text-sm text-gray-600">
            Quando você clica em <strong>Testar</strong> na tela de configuração, o backend
            envia este payload pra URL que você digitou. Não tem campo <code>session_id</code>
            — é só um ping.
          </p>
          <div class="flex items-center justify-between">
            <p class="text-sm text-gray-500">Payload</p>
            <button
              @click="copy('test', TEST_PAYLOAD)"
              class="text-xs px-3 py-1.5 bg-yellow-50 text-yellow-700 rounded-lg hover:bg-yellow-100 font-medium"
            >
              {{ copied === 'test' ? '✓ Copiado' : 'Copiar' }}
            </button>
          </div>
          <pre class="bg-gray-900 text-gray-100 text-xs rounded-xl p-4 overflow-x-auto leading-relaxed"><code>{{ TEST_PAYLOAD }}</code></pre>
        </div>
      </section>

      <!-- 4. Notas -->
      <section class="bg-white rounded-2xl shadow-xl overflow-hidden">
        <div class="bg-gradient-to-r from-purple-500 to-purple-600 px-6 py-4">
          <h2 class="text-xl font-bold text-white flex items-center gap-2">
            <span class="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center font-bold">4</span>
            Notas importantes
          </h2>
        </div>
        <div class="p-6 space-y-3 text-sm text-gray-700">
          <div class="flex gap-3">
            <span class="text-purple-600 font-bold">•</span>
            <p>
              <strong>Responda 200 rápido.</strong> O backend dá timeout em 30s. Se demorar
              mais que isso, o evento é só logado como falha — não há retry.
            </p>
          </div>
          <div class="flex gap-3">
            <span class="text-purple-600 font-bold">•</span>
            <p>
              <strong>outgoing: true</strong> significa que a própria conta enviou a
              mensagem (pelo celular, desktop ou web do Telegram). Normalmente você quer
              ignorar — exceto se estiver sincronizando em vários lugares.
            </p>
          </div>
          <div class="flex gap-3">
            <span class="text-purple-600 font-bold">•</span>
            <p>
              <strong>Sem loop.</strong> Mensagens enviadas pelo nosso próprio
              <code>/api/send-message</code> já são suprimidas no backend (10s) — não
              voltam como webhook.
            </p>
          </div>
          <div class="flex gap-3">
            <span class="text-purple-600 font-bold">•</span>
            <p>
              <strong>Sessão offline = 404.</strong> Se a conta não está na lista
              <code>active_clients</code> em memória (ex.: container acabou de subir e
              ainda não inicializou), o <code>/api/send-message</code> retorna
              <code>404 "Sessão não encontrada ou offline"</code>. Aguarde o status ficar
              "Online" no dashboard.
            </p>
          </div>
          <div class="flex gap-3">
            <span class="text-purple-600 font-bold">•</span>
            <p>
              <strong>chat_id aceita @username.</strong> Pode mandar
              <code>"@fulano"</code> no lugar de número, e o Telethon resolve.
            </p>
          </div>
          <div class="flex gap-3">
            <span class="text-purple-600 font-bold">•</span>
            <p>
              <strong>Pausar webhook.</strong> Use o botão "Pausar" no dashboard
              (<code>/api/toggle-webhook</code>) pra silenciar sem perder a URL
              configurada.
            </p>
          </div>
          <div class="flex gap-3">
            <span class="text-purple-600 font-bold">•</span>
            <p>
              <strong>Token PB obrigatório.</strong> O <code>/api/send-message</code>
              exige o JWT do PocketBase no header <code>Authorization</code> (o frontend
              pega do <code>pb.authStore.token</code> automaticamente).
            </p>
          </div>
          <div class="flex gap-3">
            <span class="text-purple-600 font-bold">•</span>
            <p>
              <strong>Múltiplos webhooks + filtros.</strong> Uma sessão pode ter N
              webhooks, cada um com filtros próprios: <code>filter_direction</code>
              (all/incoming/outgoing), <code>filter_chat_type</code>
              (all/private/group/supergroup/channel) e <code>filter_text_match</code>
              (none/equals/contains). Configure na tela de webhooks da conta.
            </p>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>
