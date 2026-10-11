#!/usr/bin/env node

import { copyFileSync, mkdirSync, existsSync, readdirSync, statSync, rmSync } from 'fs'
import { join } from 'path'
import { fileURLToPath } from 'url'
import { dirname } from 'path'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)
const rootDir = join(__dirname, '..')

const sourceDir = join(rootDir, 'apps', 'landing', 'dist')
const targetDir = join(rootDir, 'pocketbase', 'pb_public')

function copyRecursive(src, dest) {
  if (!existsSync(src)) {
    console.error(`❌ Diretório source não encontrado: ${src}`)
    console.log('💡 Execute primeiro: npm run build:landing')
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

console.log('📋 Copiando build da landing page...')

// Limpar diretório de destino (exceto subpastas especiais)
if (existsSync(targetDir)) {
  const entries = readdirSync(targetDir)
  for (const entry of entries) {
    const fullPath = join(targetDir, entry)
    if (entry !== 'app') { // Preservar a pasta app
      rmSync(fullPath, { recursive: true, force: true })
    }
  }
}

copyRecursive(sourceDir, targetDir)

console.log('✅ Landing page copiada para pocketbase/pb_public/')
