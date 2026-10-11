import { defineConfig } from 'vite'
import { resolve } from 'path'

// Gerar timestamp de build no formato YYYYMMDD-HHMMSS
const now = new Date()
const buildVersion = [
  now.getFullYear(),
  String(now.getMonth() + 1).padStart(2, '0'),
  String(now.getDate()).padStart(2, '0'),
  '-',
  String(now.getHours()).padStart(2, '0'),
  String(now.getMinutes()).padStart(2, '0'),
  String(now.getSeconds()).padStart(2, '0')
].join('')

// Plugin para adicionar ?v=timestamp nos assets do HTML
function versionQueryPlugin() {
  return {
    name: 'version-query',
    transformIndexHtml(html: string) {
      // Adiciona ?v=timestamp em arquivos .js e .css
      return html.replace(
        /(src|href)="([^"]+\.(js|css))"/g,
        `$1="$2?v=${buildVersion}"`
      )
    }
  }
}

export default defineConfig({
  plugins: [versionQueryPlugin()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
      },
      output: {
        // Nomes fixos para melhor SEO (versão vai como ?v= query string)
        entryFileNames: 'js/[name].js',
        chunkFileNames: 'js/[name].js',
        assetFileNames: (assetInfo) => {
          const name = assetInfo.name || ''
          if (name.endsWith('.css')) {
            return 'css/style.css'
          }
          if (/\.(png|jpe?g|gif|svg|webp|ico)$/i.test(name)) {
            return 'images/[name][extname]'
          }
          if (/\.(woff2?|ttf|eot|otf)$/i.test(name)) {
            return 'fonts/[name][extname]'
          }
          return 'assets/[name][extname]'
        }
      }
    },
    target: 'es2015',
    minify: true,
    cssMinify: true
  },
  server: {
    port: 5173,
    // Proxy para desenvolvimento local
    // Redireciona requisições para os serviços corretos
    proxy: {
      '/api': {
        target: 'http://localhost:8090',
        changeOrigin: true
      },
      '/_': {
        target: 'http://localhost:8090',
        changeOrigin: true
      },
      '/app': {
        target: 'http://localhost:5174',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/app/, '/app')
      }
    }
  }
})