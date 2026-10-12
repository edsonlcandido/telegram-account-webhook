import { defineStore } from 'pinia'
import { ref } from 'vue'
import { telegramApi, type TelegramSession } from '../services/telegram'

export const useTelegramStore = defineStore('telegram', () => {
  // Estado
  const sessions = ref<TelegramSession[]>([])
  const loading = ref(false)
  const error = ref('')

  // Getters
  const activeSessions = () => sessions.value.filter(s => s.active)
  const totalSessions = () => sessions.value.length

  // Ações
  async function fetchSessions() {
    loading.value = true
    error.value = ''
    
    try {
      const result = await telegramApi.getSessions()
      sessions.value = result.sessions
    } catch (e: any) {
      error.value = e.message
      console.error('Erro ao buscar sessões:', e)
    } finally {
      loading.value = false
    }
  }

  async function deleteSession(sessionId: string) {
    loading.value = true
    error.value = ''
    
    try {
      await telegramApi.deleteSession(sessionId)
      sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
    } catch (e: any) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function setWebhook(sessionId: string, webhookUrl: string) {
    try {
      await telegramApi.setWebhook(sessionId, webhookUrl)
      // Atualiza localmente
      const session = sessions.value.find(s => s.session_id === sessionId)
      if (session) {
        session.webhook_url = webhookUrl
      }
    } catch (e: any) {
      error.value = e.message
      throw e
    }
  }

  return {
    sessions,
    loading,
    error,
    activeSessions,
    totalSessions,
    fetchSessions,
    deleteSession,
    setWebhook,
  }
})
