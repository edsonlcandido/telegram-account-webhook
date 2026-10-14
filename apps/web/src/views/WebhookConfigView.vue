<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const props = defineProps<{ sessionId: string }>()

onMounted(() => {
  // Página legada — redireciona pra nova view multi-webhook
  if (props.sessionId) {
    router.replace(`/webhooks/${props.sessionId}`)
  } else {
    router.replace('/dashboard')
  }
})
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="text-center">
      <div class="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
      <p class="mt-4 text-sm text-gray-600">Redirecionando...</p>
    </div>
  </div>
</template>
