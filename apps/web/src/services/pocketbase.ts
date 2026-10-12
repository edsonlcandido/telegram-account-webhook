import PocketBase from 'pocketbase'

// Detectar URL automaticamente
function getPocketBaseUrl(): string {
  // Se VITE_POCKETBASE_URL está definido, usar ele
  if (import.meta.env.VITE_POCKETBASE_URL) {
    return import.meta.env.VITE_POCKETBASE_URL
  }
  
  // Em produção (mesma origem), usar URL relativa
  if (import.meta.env.PROD) {
    return window.location.origin
  }
  
  // Fallback para localhost
  return 'http://localhost:8090'
}

const url = getPocketBaseUrl()
console.log('🔧 PocketBase URL:', url)

const pb = new PocketBase(url)

export default pb
