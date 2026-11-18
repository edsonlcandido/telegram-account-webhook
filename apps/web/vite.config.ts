import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath } from 'url'
import { dirname } from 'path'

const __dirname = dirname(fileURLToPath(import.meta.url))

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Carrega variáveis de ambiente do diretório apps/web/ (não do raiz do monorepo)
  const env = loadEnv(mode, __dirname, 'VITE_')
  const pbUrl = env.VITE_POCKETBASE_URL || 'http://localhost:8090'
  
  console.log('🔧 Vite Config - Mode:', mode)
  console.log('🔧 Vite Config - CWD:', process.cwd())
  console.log('🔧 Vite Config - VITE_POCKETBASE_URL:', env.VITE_POCKETBASE_URL)
  console.log('🔧 Vite Config - Proxy target:', pbUrl)
  
  return {
    plugins: [vue()],
    base: '/app/',
    // Expõe TELEGRAM_API_URL (env var do build) ao frontend
    envPrefix: ['VITE_', 'TELEGRAM_API_URL'],
    server: {
      // Proxy dinâmico - usa VITE_POCKETBASE_URL ou fallback para localhost
      // Redireciona requisições /api e /_ para o PocketBase
      proxy: {
        '/api': {
          target: pbUrl,
          changeOrigin: true,
        },
        '/_': {
          target: pbUrl,
          changeOrigin: true,
        }
      },
    },
  }
})
