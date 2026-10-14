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
    text: 'Recebido! Já te respondo.',
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

// Body de retorno pro n8n (HTTP Response node) — só precisa devolver 200 com {ok:true}
const N8N_RESPONSE_BODY = JSON.stringify({ ok: true, received: true }, null, 2)

// Mapeamento de expressões n8n pra mostrar no template. Sem isso o Vue
// tentaria avaliar `$json.body.X` como propriedade da instância e quebraria.
const N8N_MAPPING = [
  'session_id          →  {{$json.body.session_id}}',
  'chat_id             →  {{$json.body.chat_id}}',
  'text                →  escreva a resposta (pode vir de AI / DB / hardcoded)',
  'reply_to_message_id →  {{$json.body.message_id}}  (se quiser responder com quote)',
].join('\n              ')

// Composable Vue pronto pra responder do frontend sem repetir boilerplate
const VUE_COMPOSABLE = `// apps/web/src/composables/useTelegramReply.ts
import { ref } from 'vue'
import { telegramApi, type WebhookPayload } from '@/services/telegram'

export function useTelegramReply() {
  const sending = ref(false)
  const error = ref<string | null>(null)
  const lastMessageId = ref<number | null>(null)

  /**
   * Responde uma mensagem que chegou via webhook.
   * Se a mensagem original era reply, faz quote automaticamente.
   */
  async function reply(payload: WebhookPayload, text: string) {
    sending.value = true
    error.value = null
    try {
      const res = await telegramApi.sendMessage(
        payload.session_id,
        payload.chat_id,
        text,
        payload.is_reply ? payload.message_id : undefined,
      )
      lastMessageId.value = res.message_id
      return res
    } catch (e: any) {
      error.value = e?.message ?? 'Erro ao enviar'
      throw e
    } finally {
      sending.value = false
    }
  }

  return { sending, error, lastMessageId, reply }
}`

// Exemplo de uso do composable num componente Vue
const VUE_USAGE = `<!-- apps/web/src/components/MessageReplyBox.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import { useTelegramReply } from '@/composables/useTelegramReply'
import type { WebhookPayload } from '@/services/telegram'

const props = defineProps<{ payload: WebhookPayload }>()
const text = ref('')
const { sending, error, reply } = useTelegramReply()

async function send() {
  if (!text.value.trim()) return
  await reply(props.payload, text.value.trim())
  text.value = ''
}
<\u002Fscript>

<template>
  <div>
    <textarea v-model="text" rows="3" placeholder="Responder..." />
    <button @click="send" :disabled="sending || !text.trim()">
      {{ sending ? 'Enviando...' : 'Responder' }}
    </button>
    <p v-if="error" class="text-red-600">{{ error }}</p>
  </div>
<\u002Ftemplate>`

// Hook JS que pode ser usado dentro do PocketBase como alternativa ao n8n:
// cria uma collection \`telegram_webhook_events\` e grava cada POST recebido.
const PB_HOOK = `// pocketbase/pb_hooks/telegram_webhook_receiver.pb.js
// Cole este arquivo em pb_hooks/ e crie a collection \`telegram_webhook_events\`
// no admin do PB (campos: session_id, message_id, chat_id, text, payload JSON, received_at).
//
// Funciona como receptor alternativo ao n8n: aponte a webhook_url do backend
// pra \`https://seu-pb.com/api/telegram/webhook-in\` e o PB grava cada evento.

routerAdd("POST", "/api/telegram/webhook-in", (e) => {
  const data = JSON.parse(e.requestBody || '{}')
  const col = $app.dao().findCollectionByNameOrId('telegram_webhook_events')
  const record = new Record(col, {
    session_id: data.session_id ?? '',
    message_id: data.message_id ?? 0,
    chat_id: data.chat_id ?? 0,
    text: data.text ?? '',
    payload: data,
    received_at: new Date().toISOString(),
  })
  $app.dao().saveRecord(record)
  return e.json(200, { ok: true })
})`

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
        </div>
      </section>

      <!-- 5. Receptor real: n8n -->
      <section class="bg-white rounded-2xl shadow-xl overflow-hidden">
        <div class="bg-gradient-to-r from-pink-500 to-rose-500 px-6 py-4">
          <h2 class="text-xl font-bold text-white flex items-center gap-2">
            <span class="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center font-bold">5</span>
            Receptor real — n8n (sua instância)
          </h2>
          <p class="text-pink-50 text-sm mt-1">
            Olhando o dashboard, sua <code class="bg-white/20 px-1 rounded">webhook_url</code>
            aponta pro n8n (
            <code class="bg-white/20 px-1 rounded">ehtudo-n8n.pfdgdz.easypanel.host</code>).
            É esse o workflow que recebe hoje.
          </p>
        </div>
        <div class="p-6 space-y-4">
          <ol class="text-sm text-gray-700 space-y-3 list-decimal list-inside">
            <li>
              <strong>Webhook trigger</strong> no n8n — recebe o payload do
              <code>POST</code> da seção 1. Não precisa configurar nada especial;
              o trigger já entrega o body em <code>$json.body</code>.
            </li>
            <li>
              <strong>Switch (opcional)</strong> — separa incoming de outgoing
              pelo campo <code>body.outgoing</code>, e separa chats
              privados/grupos/canais por <code>body.chat_type</code>.
            </li>
            <li>
              <strong>HTTP Request</strong> chamando
              <code>https://api-telegram.ehtudo.app/api/send-message</code>
              pra responder. Use <em>Send Body</em> com JSON Mode:
            </li>
          </ol>

          <div class="flex items-center justify-between">
            <p class="text-sm text-gray-500">Body do HTTP Request (n8n → backend)</p>
            <button
              @click="copy('n8n', SEND_MESSAGE_PAYLOAD)"
              class="text-xs px-3 py-1.5 bg-pink-50 text-pink-700 rounded-lg hover:bg-pink-100 font-medium"
            >
              {{ copied === 'n8n' ? '✓ Copiado' : 'Copiar' }}
            </button>
          </div>
          <pre class="bg-gray-900 text-gray-100 text-xs rounded-xl p-4 overflow-x-auto leading-relaxed"><code>{{ SEND_MESSAGE_PAYLOAD }}</code></pre>

          <p class="text-xs text-gray-500">
            Authorization: pegue o token PB (você já tem isso no admin
            <code>telegram-webhook.ehtudo.app/_/</code> → users → qualquer
            usuário → "Use as auth record"). Header:
            <code>Authorization: &lt;jwt&gt;</code> (sem prefixo Bearer, o
            backend aceita os dois).
          </p>

          <div class="flex items-center justify-between mt-2">
            <p class="text-sm text-gray-500">Body do HTTP Response (volta pro backend)</p>
            <button
              @click="copy('n8nres', N8N_RESPONSE_BODY)"
              class="text-xs px-3 py-1.5 bg-pink-50 text-pink-700 rounded-lg hover:bg-pink-100 font-medium"
            >
              {{ copied === 'n8nres' ? '✓ Copiado' : 'Copiar' }}
            </button>
          </div>
          <pre class="bg-gray-900 text-gray-100 text-xs rounded-xl p-4 overflow-x-auto leading-relaxed"><code>{{ N8N_RESPONSE_BODY }}</code></pre>

          <div class="text-xs text-gray-500 bg-pink-50 border border-pink-200 rounded-lg p-3">
            <strong>Mapeamento útil no n8n:</strong>
            <pre class="mt-2 font-mono whitespace-pre-wrap">{{ N8N_MAPPING }}</pre>
          </div>
        </div>
      </section>

      <!-- 6. Composable Vue pra responder do frontend -->
      <section class="bg-white rounded-2xl shadow-xl overflow-hidden">
        <div class="bg-gradient-to-r from-indigo-500 to-blue-600 px-6 py-4">
          <h2 class="text-xl font-bold text-white flex items-center gap-2">
            <span class="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center font-bold">6</span>
            Resposta via frontend Vue (composable)
          </h2>
          <p class="text-indigo-100 text-sm mt-1">
            Pra quando você quiser responder diretamente de um componente Vue
            (ex.: painel admin que mostra eventos e tem botão "responder").
          </p>
        </div>
        <div class="p-6 space-y-4">
          <div class="flex items-center justify-between">
            <p class="text-sm text-gray-500">composables/useTelegramReply.ts</p>
            <button
              @click="copy('comp', VUE_COMPOSABLE)"
              class="text-xs px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg hover:bg-indigo-100 font-medium"
            >
              {{ copied === 'comp' ? '✓ Copiado' : 'Copiar' }}
            </button>
          </div>
          <pre class="bg-gray-900 text-gray-100 text-xs rounded-xl p-4 overflow-x-auto leading-relaxed"><code>{{ VUE_COMPOSABLE }}</code></pre>

          <div class="flex items-center justify-between mt-2">
            <p class="text-sm text-gray-500">Uso num componente</p>
            <button
              @click="copy('usage', VUE_USAGE)"
              class="text-xs px-3 py-1.5 bg-indigo-50 text-indigo-700 rounded-lg hover:bg-indigo-100 font-medium"
            >
              {{ copied === 'usage' ? '✓ Copiado' : 'Copiar' }}
            </button>
          </div>
          <pre class="bg-gray-900 text-gray-100 text-xs rounded-xl p-4 overflow-x-auto leading-relaxed"><code>{{ VUE_USAGE }}</code></pre>
        </div>
      </section>

      <!-- 7. Receptor alternativo: hook do PocketBase -->
      <section class="bg-white rounded-2xl shadow-xl overflow-hidden">
        <div class="bg-gradient-to-r from-slate-700 to-slate-900 px-6 py-4">
          <h2 class="text-xl font-bold text-white flex items-center gap-2">
            <span class="w-8 h-8 bg-white/20 rounded-lg flex items-center justify-center font-bold">7</span>
            Receptor alternativo — hook do PocketBase
          </h2>
          <p class="text-slate-200 text-sm mt-1">
            Se em algum momento você quiser gravar os eventos direto no seu PB
            (sem passar pelo n8n), esse hook cria uma rota que recebe o POST e
            persiste cada mensagem numa collection.
          </p>
        </div>
        <div class="p-6 space-y-3">
          <ol class="text-sm text-gray-700 space-y-2 list-decimal list-inside">
            <li>
              Crie a collection <code>telegram_webhook_events</code> no admin
              do PB com os campos:
              <code>session_id</code> (text), <code>message_id</code> (number),
              <code>chat_id</code> (number), <code>text</code> (text),
              <code>payload</code> (JSON), <code>received_at</code> (date).
            </li>
            <li>
              Salve o hook abaixo em
              <code>pocketbase/pb_hooks/telegram_webhook_receiver.pb.js</code> e
              reinicie o serviço.
            </li>
            <li>
              Mude a <code>webhook_url</code> da conta pra
              <code>https://telegram-webhook.ehtudo.app/api/telegram/webhook-in</code>.
            </li>
          </ol>

          <div class="flex items-center justify-between">
            <p class="text-sm text-gray-500">telegram_webhook_receiver.pb.js</p>
            <button
              @click="copy('pbhook', PB_HOOK)"
              class="text-xs px-3 py-1.5 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 font-medium"
            >
              {{ copied === 'pbhook' ? '✓ Copiado' : 'Copiar' }}
            </button>
          </div>
          <pre class="bg-gray-900 text-gray-100 text-xs rounded-xl p-4 overflow-x-auto leading-relaxed"><code>{{ PB_HOOK }}</code></pre>
        </div>
      </section>
    </main>
  </div>
</template>
