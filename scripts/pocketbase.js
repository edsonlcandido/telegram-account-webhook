#!/usr/bin/env node

import { spawn } from 'child_process'
import { fileURLToPath } from 'url'
import { dirname, join } from 'path'
import { existsSync, mkdirSync, chmodSync } from 'fs'
import https from 'https'
import fs from 'fs'
import { execSync } from 'child_process'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const rootDir = join(__dirname, '..')
const pbDir = join(rootDir, 'pocketbase')
const pbBinary = join(pbDir, 'pocketbase')

// Detectar plataforma e arquitetura
const platform = process.platform
const arch = process.arch

function getPocketBaseURL() {
  const version = '0.36.2' // Versão do PocketBase
  
  let os = ''
  let archSuffix = ''
  
  if (platform === 'linux') {
    os = 'linux'
  } else if (platform === 'darwin') {
    os = 'darwin'
  } else if (platform === 'win32') {
    os = 'windows'
  } else {
    throw new Error(`Plataforma não suportada: ${platform}`)
  }
  
  if (arch === 'x64') {
    archSuffix = 'amd64'
  } else if (arch === 'arm64') {
    archSuffix = 'arm64'
  } else {
    throw new Error(`Arquitetura não suportada: ${arch}`)
  }
  
  const fileName = `pocketbase_${version}_${os}_${archSuffix}.zip`
  return `https://github.com/pocketbase/pocketbase/releases/download/v${version}/${fileName}`
}

function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest)
    
    https.get(url, (response) => {
      if (response.statusCode === 302 || response.statusCode === 301) {
        // Seguir redirect
        downloadFile(response.headers.location, dest).then(resolve).catch(reject)
        return
      }
      
      response.pipe(file)
      
      file.on('finish', () => {
        file.close()
        resolve()
      })
    }).on('error', (err) => {
      fs.unlink(dest, () => {})
      reject(err)
    })
  })
}

async function downloadAndExtractPocketBase() {
  console.log('🔄 Baixando PocketBase...')
  
  if (!existsSync(pbDir)) {
    mkdirSync(pbDir, { recursive: true })
  }
  
  const zipPath = join(pbDir, 'pocketbase.zip')
  const url = getPocketBaseURL()
  
  await downloadFile(url, zipPath)
  
  console.log('📦 Extraindo PocketBase...')
  
  execSync(`unzip -o "${zipPath}" -d "${pbDir}"`, { stdio: 'inherit' })
  fs.unlinkSync(zipPath)
  
  // Tornar executável
  chmodSync(pbBinary, '755')
  
  console.log('✅ PocketBase instalado com sucesso!')
}

async function startPocketBase() {
  if (existsSync(pbBinary)) {
    console.log('✅ PocketBase já instalado')
  } else {
    await downloadAndExtractPocketBase()
  }

  // Bind em 0.0.0.0 por padrão pra funcionar em VSCode Server / Codespaces /
  // qualquer ambiente atrás de reverse proxy (Easypanel, Traefik, Tunnel...).
  // Sobrescrever via PB_HTTP se quiser loopback: PB_HTTP=127.0.0.1:8090 npm run dev:pb
  const http = process.env.PB_HTTP || '0.0.0.0:8090'

  console.log(`🚀 Iniciando PocketBase em ${http}...`)

  const pb = spawn(pbBinary, ['serve', `--http=${http}`], {
    cwd: pbDir,
    stdio: 'inherit',
  })
  
  pb.on('error', (err) => {
    console.error('Erro ao iniciar PocketBase:', err)
    process.exit(1)
  })
  
  pb.on('close', (code) => {
    console.log(`PocketBase encerrado com código ${code}`)
    process.exit(code)
  })
}

startPocketBase().catch((err) => {
  console.error('Erro:', err)
  process.exit(1)
})
