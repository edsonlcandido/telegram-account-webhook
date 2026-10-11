import { defineConfig, type UserConfig } from 'vite'
import baseConfig from './vite.config.js'

// Aceita qualquer Host: por padrão (ideal pra VSCode Server / Easypanel /
// Cloudflare Tunnel que mudam URL). Pra travar por domínio, defina antes
// do `npm run dev`:
//
//   export VITE_ALLOWED_HOSTS="*.meudominio.com,meudominio.com,localhost"
const allowedHosts: true | string[] = (() => {
  const raw = process.env.VITE_ALLOWED_HOSTS
  if (!raw) return true
  const list = raw.split(',').map((s: string) => s.trim()).filter(Boolean)
  return list.length ? list : true
})()

// landing/vite.config.ts exporta um objeto direto (sem função wrapper).
// O cast pra UserConfig é só pra destravar o spread — o objeto já existe em runtime.
const base = baseConfig as UserConfig

export default defineConfig({
  ...base,
  server: {
    ...base.server,
    host: '0.0.0.0',
    allowedHosts,
  },
})