#!/usr/bin/env node

import { copyFileSync, mkdirSync, existsSync, readdirSync, statSync, rmSync } from 'fs'
import { join } from 'path'
import { fileURLToPath } from 'url'
import { dirname } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const rootDir = join(__dirname, '..')

const sourceDir = join(rootDir, 'apps', 'web', 'dist')
const targetDir = join(rootDir, 'pocketbase', 'pb_public', 'app')

function copyRecursive(src, dest) {
  if (!existsSync(src)) {
    console.error(`❌ Diretório source não encontrado: ${src}`)
    console.log('💡 Execute primeiro: npm run build:web')
    process.exit(1)
  }

  const stats = statSync(src)
  
  if (stats.isDirectory()) {
    if (!existsSync(dest)) {
      mkdirSync(dest, { recursive: true })
    }
    
    const files = readdirSync(src)
    
    for (const file of files) {
      copyRecursive(join(src, file), join(dest, file))
    }
  } else {
    copyFileSync(src, dest)
  }
}

console.log('📋 Copiando build do web app...')

// Limpar diretório de destino
if (existsSync(targetDir)) {
  rmSync(targetDir, { recursive: true, force: true })
}

copyRecursive(sourceDir, targetDir)

console.log('✅ Web app copiado para pocketbase/pb_public/app/')
