<script setup lang="ts">
import { computed, ref } from 'vue'
import { telegramApi, type IntegrationTokenResponse } from '../services/telegram'

/**
 * Gera um token do PocketBase pro usuário logado — o mesmo formato que o
 * Admin UI produz pelo "Impersonate". O objetivo é o usuário copiar e colar
 * `Authorization: <token>` em OUTRO sistema (n8n, Make, backend próprio)
 * pra chamar o `/api/send-message`.
 *
 * O token NÃO é persistido em lugar nenhum: nem no PocketBase (lá é
 * stateless), nem no Pinia/localStorage. Sair da página = perder o token.
 */
const emit = defineEmits<{
  /** Token gerado (ou `null` se o usuário limpou). O pai usa pra montar o curl. */
  generated: [token: string | null]
  /** O pai cuida do curl — ele tem o payload e o helper de copy. */
  copyCurl: []
}>()

const durationOptions = [
  { value: 3600, label: '1 hora' },
  { value: 86400, label: '24 horas' },
  { value: 604800, label: '7 dias' },
  { value: 2592000, label: '30 dias' },
  { value: 31536000, label: '1 ano' },
]

const selectedDuration = ref<number>(2592000)
const isGenerating = ref(false)
const tokenError = ref<string | null>(null)
const revealed = ref(false)
const copied = ref(false)
const token = ref<IntegrationTokenResponse | null>(null)

/** Mascarado por padrão — evita screenshot acidental e olhada por cima do ombro. */
const displayToken = computed(() => {
  const value = token.value?.token
  if (!value) return ''
  return revealed.value ? value : `${'•'.repeat(24)}${value.slice(-8)}`
})

const expiresLabel = computed(() => {
  const exp = token.value?.expires_at
  if (!exp) return ''
  return new Date(exp * 1000).toLocaleString('pt-BR')
})

async function generate() {
  // Guarda de reentrância: o botão já fica disabled, mas um duplo clique
  // rápido ainda pode disparar duas calls antes do re-render.
  if (isGenerating.value) return

  isGenerating.value = true
  tokenError.value = null
  try {
    const result = await telegramApi.createIntegrationToken({
      duration: selectedDuration.value,
    })
    token.value = result
    revealed.value = false
    copied.value = false
    emit('generated', result.token)
  } catch (err) {
    tokenError.value = err instanceof Error ? err.message : 'Erro ao gerar o token'
    // O token anterior continua válido e visível — nada de estado parcial.
  } finally {
    isGenerating.value = false
  }
}

async function copyToken() {
  const value = token.value?.token
  if (!value) return
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
    } else {
      // Fallback pra contexto não seguro (HTTP) — mesmo caminho do ApiDocsView.
      const ta = document.createElement('textarea')
      ta.value = value
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    tokenError.value = 'Não foi possível copiar. Use o botão "Revelar" e copie manualmente.'
  }
}

function toggleReveal() {
  revealed.value = !revealed.value
}
</script>

<template>
  <div class="bg-gray-50 rounded-xl p-5 border border-gray-200">
    <div class="flex items-start gap-3 mb-4">
      <span class="text-xl leading-none" aria-hidden="true">🔑</span>
      <div>
        <p class="font-semibold text-gray-800">Token de integração</p>
        <p class="text-sm text-gray-600 mt-1">
          Pra chamar esse endpoint de outro sistema (n8n, Make, backend próprio), o
          header <code class="px-1.5 py-0.5 bg-white rounded text-xs">Authorization</code>
          precisa de um token. Gere o seu aqui e copie.
        </p>
      </div>
    </div>

    <div class="flex flex-wrap items-end gap-3">
      <div class="flex flex-col gap-1">
        <label for="integration-token-duration" class="text-xs font-medium text-gray-600">
          Validade
        </label>
        <select
          id="integration-token-duration"
          v-model.number="selectedDuration"
          class="px-3 py-2 text-sm rounded-lg border border-gray-300 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500"
        >
          <option v-for="option in durationOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </div>

      <button
        type="button"
        @click="generate"
        :disabled="isGenerating"
        class="px-4 py-2 text-sm font-semibold rounded-lg text-white bg-brand-500 hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
      >
        {{ isGenerating ? 'Gerando…' : '🔑 Gerar token' }}
      </button>
    </div>

    <p v-if="!token" class="text-xs text-gray-500 mt-3">
      O token aparece uma única vez. Se perder, é só gerar outro.
    </p>

    <!-- Erro -->
    <div
      v-if="tokenError"
      class="mt-4 px-3 py-2 rounded-lg bg-red-50 text-red-700 text-xs border border-red-200"
    >
      {{ tokenError }}
    </div>

    <!-- Token gerado -->
    <div v-if="token" class="mt-4 space-y-3">
      <div class="flex flex-wrap gap-2">
        <button
          type="button"
          @click="copyToken"
          class="text-xs px-3 py-1.5 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 font-medium"
        >
          {{ copied ? '✓ Copiado' : 'Copiar token' }}
        </button>
        <button
          type="button"
          @click="toggleReveal"
          class="text-xs px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 font-medium"
        >
          {{ revealed ? 'Ocultar' : 'Revelar' }}
        </button>
        <button
          type="button"
          @click="emit('copyCurl')"
          class="text-xs px-3 py-1.5 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 font-medium"
        >
          Copiar curl completo
        </button>
      </div>

      <pre
        class="bg-gray-900 text-gray-100 text-xs rounded-xl p-3 overflow-x-auto break-all leading-relaxed"
        ><code>{{ displayToken }}</code></pre>

      <p class="text-xs text-gray-500">
        expira em <span class="font-semibold text-gray-700">{{ expiresLabel }}</span>
        <span v-if="!expiresLabel"> (o backend não informou o prazo)</span>
      </p>

      <div
        class="px-3 py-2 rounded-lg bg-amber-50 text-amber-800 text-xs border border-amber-200 space-y-1"
      >
        <p class="font-semibold">⚠ Token estático — leia antes de usar em produção</p>
        <ul class="list-disc list-inside space-y-0.5">
          <li>
            Não renova e <strong>não tem revogação individual</strong>. Gerar outro não
            invalida este — os dois valem até o prazo.
          </li>
          <li>
            Para invalidar de verdade: troque a senha do usuário no Admin UI do
            PocketBase (isso rotaciona o <code>tokenKey</code> dele).
          </li>
          <li>
            Quem tiver o token acessa <strong>todos</strong> os endpoints deste usuário —
            inclusive criar/deletar webhooks e sessões, não só enviar mensagem.
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>