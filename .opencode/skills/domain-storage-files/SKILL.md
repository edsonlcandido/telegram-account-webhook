---
name: domain-storage-files
description: Como implementar upload e gerenciamento de arquivos no template — collection com campo `file`, thumbnail, validação de MIME/tamanho, S3-compatível, gallery component e signed URLs. Use quando o usuário quiser upload de avatar, anexos, imagens em posts (já tratado em blog), documentos, ou storage privado.
---

# Domínio — Storage / Upload de arquivos

PocketBase tem campo `file` nativo (filesystem local) + S3-compatível opcional. Cobre 90% dos casos sem libs externas.

## Caso 1 — Avatar do user

### Adicionar campo à collection `users`

No admin `/_/`, edite `users` → adicionar campo `avatar` (type: `file`, maxSelect: 1, maxSize: 2MB, mimeTypes: image/jpeg,image/png,image/webp).

Ou via migration:

```js
// pb_migrations/1700000000_user_avatar.js
/// <reference path="../pb_data/types.d.ts" />

const usersCol = $app.dao().findCollectionByNameOrId('users')
usersCol.schema.add(new Field({
  name: 'avatar', type: 'file', required: false, maxSelect: 1, maxSize: 2 * 1024 * 1024,
  mimeTypes: ['image/jpeg', 'image/png', 'image/webp'],
}))
$app.dao().saveCollection(usersCol)
```

### Componente de upload

```vue
<!-- components/AvatarUpload.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import pb from '@/services/pocketbase'
import { useAuthStore } from '@/stores/auth'
import { CameraIcon } from '@heroicons/vue/24/outline'

const auth = useAuthStore()
const file = ref<File | null>(null)
const preview = ref<string | null>(null)
const loading = ref(false)

const props = defineProps<{ userId: string; avatar?: string }>()
const emit = defineEmits<{ updated: [filename: string] }>()

function onPick(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (!f) return
  if (f.size > 2 * 1024 * 1024) { alert('Máx 2MB'); return }
  file.value = f
  preview.value = URL.createObjectURL(f)
}

async function upload() {
  if (!file.value) return
  loading.value = true
  try {
    const fd = new FormData()
    fd.append('avatar', file.value)
    const updated = await pb.collection('users').update(props.userId, fd)
    auth.user = updated          // atualiza store reativamente
    emit('updated', updated.avatar)
    preview.value = null
  } finally {
    loading.value = false
  }
}

const currentUrl = () => {
  if (preview.value) return preview.value
  if (props.avatar) return pb.files.getURL({ id: props.userId, collectionId: '_pb_users_auth_' }, props.avatar, { thumb: '100x100' })
  return null
}
</script>

<template>
  <div class="flex items-center gap-4">
    <div class="w-24 h-24 rounded-full overflow-hidden bg-gray-200 flex items-center justify-center">
      <img v-if="currentUrl()" :src="currentUrl()!" class="w-full h-full object-cover" />
      <UserCircleIcon v-else class="w-16 h-16 text-gray-400" />
    </div>
    <div>
      <label class="cursor-pointer inline-flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg">
        <CameraIcon class="w-5 h-5" />
        Escolher foto
        <input type="file" accept="image/*" class="hidden" @change="onPick" />
      </label>
      <button v-if="file" @click="upload" :disabled="loading"
        class="ml-2 px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50">
        {{ loading ? 'Enviando...' : 'Salvar' }}
      </button>
    </div>
  </div>
</template>
```

> Thumb query: `?thumb=100x100` ou `?thumb=100x100f` (crop fit). Outros: `WxH`, `WxHt` (top crop), `WxHf` (face), `WxHb` (bottom).

## Caso 2 — Anexos em uma coleção

Adicionar campo `attachments` à collection existente:

```js
// migration: lead com anexos
const leadsCol = $app.dao().findCollectionByNameOrId('leads')
leadsCol.schema.add(new Field({
  name: 'attachments', type: 'file', required: false, maxSelect: 5,
  maxSize: 10 * 1024 * 1024,
  mimeTypes: ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'],
}))
$app.dao().saveCollection(leadsCol)
```

### Upload múltiplo

```ts
async function uploadAttachments(recordId: string, files: File[]) {
  const fd = new FormData()
  for (const f of files) fd.append('attachments', f)
  return pb.collection('leads').update(recordId, fd)
}
```

### Visualizar/baixar

```vue
<script setup lang="ts">
import pb from '@/services/pocketbase'
const props = defineProps<{ record: any; field: string }>()

function url(file: string, thumb?: string) {
  return pb.files.getURL(props.record, file, { thumb })
}
</script>

<template>
  <div class="grid grid-cols-3 gap-3">
    <a v-for="f in (record[field] || [])" :key="f" :href="url(f)" target="_blank"
      class="relative group rounded-lg overflow-hidden border bg-white">
      <img v-if="f.match(/\.(jpe?g|png|webp|gif)$/i)"
        :src="url(f, '400x300')" class="w-full h-40 object-cover" />
      <div v-else class="p-4 text-sm">
        📄 {{ f.split('/').pop() }}
      </div>
    </a>
  </div>
</template>
```

## Caso 3 — Arquivos privados (signed URLs)

Por padrão, `pb_data/storage/` é **público**. Pra proteger:

```js
// admin: marcar campo como 'private' (não tem UI; via migration):
const col = $app.dao().findCollectionByNameOrId('documents')
col.schema.findFieldByName('file').options = { ...col.schema.findFieldByName('file').options, protected: true }
$app.dao().saveCollection(col)
```

Acessar de client autenticado:

```ts
const token = pb.authStore.token
const url = pb.files.getURL(record, record.file) + `?token=${token}`
```

Pra URL temporária (assinada server-side):

```js
// pb_hooks/documents.pb.js
routerAdd('GET', '/api/documents/:id/url', (c) => {
  if (!c.auth) return c.json(401, { error: 'auth required' })
  const rec = $app.dao().findRecordById('documents', c.request.pathValue('id'))
  if (rec.getString('owner') !== c.auth.id) return c.json(403, { error: 'forbidden' })

  const ttl = 60 * 5   // 5 min
  const sig = $security.hs256(`${rec.id}:${Date.now() / 1000 + ttl}`, $os.getenv('URL_SECRET'))
  const url = $app.settings().publicUrl + '/api/files/' + rec.collection().id + '/' + rec.id + '/' + rec.getString('file')
  return c.json(200, { url: url + '?exp=' + Math.floor(Date.now() / 1000 + ttl) + '&sig=' + sig })
})
```

## Caso 4 — S3-compatible (Backblaze, MinIO, R2)

PocketBase **não tem S3 nativo ainda** — opções:

1. **Proxy no servidor** (hook PB gera signed URL S3):
```js
// pb_hooks/files.pb.js
routerAdd('GET', '/api/s3-url/:collection/:recordId/:filename', async (c) => {
  if (!c.auth) return c.json(401, { error: 'auth' })

  // gera URL pré-assinada MinIO/R2
  const signed = await s3.getSignedUrlPromise('getObject', {
    Bucket: $os.getenv('S3_BUCKET'),
    Key: `${c.request.pathValue('collection')}/${c.request.pathValue('recordId')}/${c.request.pathValue('filename')}`,
    Expires: 300,
  })
  return c.json(200, { url: signed })
})
```

2. **Worker de sync** que copia `pb_data/storage/` → S3 periodicamente
3. **Pré-upload via hook**: client pede URL, faz upload direto pro S3, manda key pro PB

## Componente Gallery (drag & drop + progress)

```vue
<!-- components/FileDropzone.vue -->
<script setup lang="ts">
import { ref } from 'vue'
import pb from '@/services/pocketbase'

const props = defineProps<{ collection: string; recordId: string; field: string }>()
const emit = defineEmits<{ uploaded: [files: string[]] }>()

const dragOver = ref(false)
const progress = ref(0)
const loading = ref(false)

async function handleFiles(files: FileList | null) {
  if (!files?.length) return
  loading.value = true
  try {
    const fd = new FormData()
    for (const f of Array.from(files)) fd.append(props.field, f)

    // PocketBase suporta progresso via XHR direto
    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', `${pb.baseUrl}/api/collections/${props.collection}/records/${props.recordId}`)
      xhr.setRequestHeader('Authorization', pb.authStore.token)
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) progress.value = Math.round((e.loaded / e.total) * 100)
      }
      xhr.onload = () => xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(xhr.statusText))
      xhr.onerror = () => reject(new Error('Network error'))
      xhr.send(fd)
    })

    const updated = await pb.collection(props.collection).getOne(props.recordId)
    emit('uploaded', updated[props.field] || [])
  } finally {
    loading.value = false
    progress.value = 0
  }
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  dragOver.value = false
  handleFiles(e.dataTransfer?.files ?? null)
}
</script>

<template>
  <div @dragover.prevent="dragOver = true"
       @dragleave="dragOver = false"
       @drop="onDrop"
       :class="['rounded-xl border-2 border-dashed p-8 text-center transition',
         dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50']">
    <p class="text-gray-600">Solte arquivos aqui ou</p>
    <label class="mt-2 inline-block px-4 py-2 bg-blue-600 text-white rounded-lg cursor-pointer">
      Selecionar
      <input type="file" multiple class="hidden" @change="(e) => handleFiles((e.target as HTMLInputElement).files)" />
    </label>
    <div v-if="loading" class="mt-3">
      <div class="w-full bg-gray-200 rounded-full h-2">
        <div class="bg-blue-600 h-2 rounded-full transition-all" :style="{ width: progress + '%' }"></div>
      </div>
      <p class="text-sm mt-1">{{ progress }}%</p>
    </div>
  </div>
</template>
```

## Limites & validações

```js
// no schema da collection
{
  name: 'gallery', type: 'file', maxSelect: 10,
  maxSize: 5 * 1024 * 1024,                       // 5MB por arquivo
  mimeTypes: ['image/jpeg', 'image/png', 'image/webp'],
  thumbs: ['100x100', '400x300', '1200x800'],     // gera automáticos
}
```

`thumbs` faz PB gerar as variantes no upload. Acessar com `?thumb=100x100` no getURL.

## Hook — processar após upload

```js
// pb_hooks/uploads.pb.js
onRecordAfterUpdateRequest((e) => {
  if (e.collection.name !== 'posts') return
  const files = e.record.get('cover_image') || []    // array de filenames
  if (files.length === 0) return
  console.log('📸 novo cover:', files[0])
  // ex: chamar API de moderação, extrair EXIF, etc
}, $app)
```

## Anti-padrões

| ❌ Não | ✅ Fazer |
|---|---|
| `URL.createObjectURL` em todo render | Gerar URL uma vez via `pb.files.getURL()` |
| Salvar arquivo como base64 em campo texto | Usar campo `file` nativo |
| Expor URL protegida sem checar auth | Hook valida `c.auth.id` antes |
| Salvar no client sem progresso | XHR direto com `upload.onprogress` |
| Esquecer de gerar thumbs | Configurar `thumbs: [...]` no schema |

## Onde isso já aparece nas skills

- **Blog** (`domain-blog-cms`): campo `cover_image` com thumbs automáticos
- **CRM** (`domain-crm-leads`): `notes` podem virar anexos via collection separada
- **SaaS** (`domain-saas-billing`): `invoices` com `invoice_pdf_url`