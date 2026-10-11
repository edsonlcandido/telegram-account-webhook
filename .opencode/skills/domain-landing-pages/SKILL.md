---
name: domain-landing-pages
description: Como criar landing pages específicas por segmento de cliente no template — SaaS, negócio local, portfólio, evento, app mobile, infoproduto. Cobre componentes reusáveis, padrões de design, integração com PB (form de contato + leads), deploy e estratégia multi-cliente. Use quando o usuário quiser usar o template pra um cliente novo e precisar decidir tipo de landing + componentes + como conectar com o app.
---

# Domínio — Landing Pages (por segmento de cliente)

Você vai pegar esse template e criar **um app por cliente**. Cada cliente vai precisar de uma landing própria — de SaaS a salão de beleza. Esta skill dá o catálogo de **receitas prontas** pra montar a landing certa pro segmento, plugar com PocketBase, e fazer deploy.

> Foco: entregar rápido pro cliente. Não tem otimização de SEO agressiva (não é WordPress). Cada landing é um **experimento de copy + design**, não um poste de blog.

## Filosofia

| Decisão | Escolha |
|---|---|
| Onde fica a landing | `apps/landing/` (já existe no template, é vanilla Vite+TS) — **modular por cliente** |
| Como publica | Static build em Netlify/Vercel/Cloudflare Pages **ou** dentro do PocketBase em `pb_public/` |
| Como coleta leads | Hook PB `POST /api/leads` + collection `leads` (ou `contact_requests`) |
| Como mede | Plausible/Vercel Analytics (1 script, 0 cookies) |
| SEO | Meta tags dinâmicas + sitemap.xml + OG image. Não é prioridade. |

## Tipos de landing — qual usar

| Segmento do cliente | Tipo recomendado | Estrutura principal |
|---|---|---|
| SaaS B2B | SaaS | Hero + features + pricing + logos + CTA |
| SaaS B2C | App-style | Hero com mockup + benefícios simples + screenshots + preço |
| Restaurante / loja local | Local business | Hero com foto + cardápio/menu + endereço+horário+mapa + reserva |
| Profissional liberal (dentista, advogado, personal) | Profissional | Hero com foto + serviços + sobre + contato + agendamento |
| Portfólio (designer, dev, fotógrafo) | Portfólio | Hero + grid de projetos + sobre + contato |
| Evento pontual (casamento, conferência, workshop) | Evento | Hero com data + countdown + programa + speakers + inscrição |
| Curso / infoproduto | Infoproduto | Hero + módulos + instrutor + bônus + garantia + CTA compra |
| App mobile | App | Hero com mockup do app + features + screenshots + badges App Store/Play |
| E-commerce simples | Vitrine | Hero + grid de produtos + filtro + contato WhatsApp |

## Arquitetura de landing no monorepo

### Estratégia A — Uma landing por app (multi-cliente)

```
apps/
├── landing-template/      # template base (não publicado)
├── landing-cliente-x/     # clone customizado pra cliente X
├── landing-cliente-y/     # outro cliente
└── web-app-cliente-x/     # app do cliente X (pode compartilhar com landing de outro)
```

Prós: cada cliente isolado, build independente
Contras: precisa de mais skills (`monorepo-add-app`)

### Estratégia B — Landing única parametrizada (1 cliente)

Pra 1 projeto só, simplesmente customiza `apps/landing/src/main.ts` direto. Mais rápido.

### Estratégia C — Landing dentro do PB (sem Cloudflare)

Útil quando o cliente não quer configurar deploy externo. O template já tem:

```bash
npm run build:landing    # gera apps/landing/dist
npm run copy:landing     # copia pra pocketbase/pb_public/
```

A landing fica acessível em `https://app.cliente.com/`. Funciona, sem CDN extra. Limitação: HTTPS único domínio.

### Como decidir

| Critério | A | B | C |
|---|---|---|---|
| 1 cliente só | overkill | ✅ ideal | ✅ se não quiser CDN |
| Muitos clientes diferentes | ✅ ideal | ruim | ✗ |
| Cliente quer domínio próprio | ✅ + DNS | ✅ + DNS | ✅ + DNS |
| Velocidade de delivery | mais lento | mais rápido | mais rápido |
| Pra customizar UI | trabalho | trabalho | trabalho |

**Padrão recomendado pra agência**: **Estratégia A** quando for cliente novo, **B** quando for variação.

## Estrutura base de uma landing

Cada `apps/landing/index.html`:

```html
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{{NOME_CLIENTE}} - {{TAGLINE}}</title>
  <meta name="description" content="{{META_DESC}}" />
  <meta name="theme-color" content="#3b82f6" />

  <!-- OG / Facebook -->
  <meta property="og:title" content="{{NOME_CLIENTE}}" />
  <meta property="og:description" content="{{META_DESC}}" />
  <meta property="og:image" content="{{OG_IMAGE_URL}}" />
  <meta property="og:type" content="website" />

  <!-- Favicon -->
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />

  <!-- Analytics (1 script, 0 cookie) -->
  <script defer data-domain="{{DOMINIO}}" src="https://plausible.io/js/script.js"></script>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

## Componentes reusáveis (snippet library)

Cada um é HTML inline + classes Tailwind. Cole direto no `main.ts` ou extraia pra arquivos `.ts` separados.

### 1. Navbar

```html
<nav class="fixed top-0 w-full z-50 bg-white/80 backdrop-blur-lg border-b border-gray-100">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex justify-between items-center py-4">
      <a href="/" class="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
        {{LOGO_TEXT}}
      </a>
      <div class="hidden md:flex gap-8 items-center">
        <a href="#features" class="text-gray-600 hover:text-gray-900">Recursos</a>
        <a href="#pricing"  class="text-gray-600 hover:text-gray-900">Preços</a>
        <a href="#contact"  class="text-gray-600 hover:text-gray-900">Contato</a>
        <a href="/app/"     class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">Entrar</a>
      </div>
    </div>
  </div>
</nav>
```

### 2. Hero — variantes

**Variante A — Texto + CTA (SaaS B2B)**:
```html
<section class="pt-32 pb-20 px-4 sm:px-6 lg:px-8 text-center bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50">
  <div class="max-w-4xl mx-auto">
    <span class="px-4 py-2 bg-blue-100 text-blue-700 text-sm font-semibold rounded-full">🎉 Lançamento</span>
    <h1 class="mt-6 text-5xl md:text-6xl font-extrabold text-gray-900 leading-tight">
      {{TAGLINE}}
    </h1>
    <p class="mt-6 text-xl text-gray-600 max-w-2xl mx-auto">{{SUBTITLE}}</p>
    <div class="mt-8 flex flex-col sm:flex-row gap-4 justify-center">
      <a href="#cta" class="px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white text-lg font-semibold rounded-xl hover:opacity-90">Começar grátis</a>
      <a href="#demo" class="px-8 py-4 bg-white border-2 border-gray-200 text-gray-800 text-lg font-semibold rounded-xl hover:bg-gray-50">Ver demo</a>
    </div>
    <p class="mt-4 text-sm text-gray-500">Sem cartão de crédito • 14 dias grátis</p>
  </div>
</section>
```

**Variante B — Imagem/mockup (App-style / Infoproduto)**:
```html
<section class="pt-32 pb-20 px-4 bg-gradient-to-br from-slate-900 to-slate-800 text-white">
  <div class="max-w-7xl mx-auto grid md:grid-cols-2 gap-12 items-center">
    <div>
      <h1 class="text-5xl md:text-6xl font-extrabold">{{TAGLINE}}</h1>
      <p class="mt-4 text-xl text-gray-300">{{SUBTITLE}}</p>
      <a href="#cta" class="mt-8 inline-block px-8 py-4 bg-blue-600 text-white rounded-xl">Baixar agora</a>
    </div>
    <div>
      <img src="/mockup.png" alt="" class="rounded-2xl shadow-2xl" />
    </div>
  </div>
</section>
```

**Variante C — Foto real (Local business / Profissional)**:
```html
<section class="relative h-screen flex items-center justify-center text-center text-white overflow-hidden">
  <img src="/bg.jpg" alt="" class="absolute inset-0 w-full h-full object-cover" />
  <div class="absolute inset-0 bg-black/50"></div>
  <div class="relative z-10 px-4">
    <h1 class="text-5xl md:text-7xl font-extrabold">{{NOME}}</h1>
    <p class="mt-4 text-2xl">{{TAGLINE}}</p>
    <a href="tel:{{TELEFONE}}" class="mt-8 inline-block px-8 py-4 bg-white text-gray-900 rounded-xl font-semibold">📞 {{TELEFONE}}</a>
  </div>
</section>
```

### 3. Features grid

```html
<section id="features" class="py-20 px-4 sm:px-6 lg:px-8">
  <div class="max-w-7xl mx-auto">
    <div class="text-center mb-16">
      <h2 class="text-4xl md:text-5xl font-extrabold">{{FEATURES_TITLE}}</h2>
      <p class="mt-4 text-xl text-gray-600">{{FEATURES_SUBTITLE}}</p>
    </div>
    <div class="grid md:grid-cols-3 gap-8">
      <!-- repetir 3-6 vezes -->
      <div class="group p-8 bg-white rounded-2xl shadow-xl hover:shadow-2xl transition border-2 border-transparent hover:border-blue-200">
        <div class="w-14 h-14 bg-blue-100 text-blue-600 rounded-xl flex items-center justify-center text-2xl mb-4">⚡</div>
        <h3 class="text-xl font-bold mb-2">{{FEATURE_TITLE}}</h3>
        <p class="text-gray-600">{{FEATURE_DESC}}</p>
      </div>
    </div>
  </div>
</section>
```

### 4. Pricing table (3 planos)

```html
<section id="pricing" class="py-20 px-4 bg-gray-50">
  <div class="max-w-6xl mx-auto">
    <h2 class="text-4xl font-extrabold text-center mb-12">Planos simples</h2>
    <div class="grid md:grid-cols-3 gap-6">
      <!-- Free -->
      <div class="bg-white rounded-2xl p-8 shadow">
        <h3 class="text-xl font-bold">{{P1_NAME}}</h3>
        <p class="mt-4 text-4xl font-extrabold">R$ 0<span class="text-lg text-gray-500 font-normal">/mês</span></p>
        <ul class="mt-6 space-y-2 text-sm">{{P1_FEATURES}}</ul>
        <a href="#cta" class="mt-8 block w-full py-3 bg-gray-100 text-gray-800 rounded-lg text-center font-medium">Começar</a>
      </div>
      <!-- Pro (destacado) -->
      <div class="bg-gradient-to-br from-blue-600 to-purple-600 text-white rounded-2xl p-8 shadow-2xl transform scale-105">
        <span class="px-3 py-1 bg-yellow-300 text-yellow-900 rounded-full text-xs font-bold">MAIS POPULAR</span>
        <h3 class="mt-3 text-xl font-bold">{{P2_NAME}}</h3>
        <p class="mt-4 text-4xl font-extrabold">R$ 99<span class="text-lg opacity-80 font-normal">/mês</span></p>
        <ul class="mt-6 space-y-2 text-sm">{{P2_FEATURES}}</ul>
        <a href="#cta" class="mt-8 block w-full py-3 bg-white text-blue-600 rounded-lg text-center font-bold">Assinar</a>
      </div>
      <!-- Enterprise -->
      <div class="bg-white rounded-2xl p-8 shadow">
        <h3 class="text-xl font-bold">{{P3_NAME}}</h3>
        <p class="mt-4 text-4xl font-extrabold">Sob consulta</p>
        <ul class="mt-6 space-y-2 text-sm">{{P3_FEATURES}}</ul>
        <a href="#contact" class="mt-8 block w-full py-3 bg-gray-100 text-gray-800 rounded-lg text-center font-medium">Falar</a>
      </div>
    </div>
  </div>
</section>
```

### 5. Logo cloud (prova social)

```html
<section class="py-16 px-4 border-y border-gray-100">
  <p class="text-center text-sm text-gray-500 uppercase tracking-wider mb-6">Confiam em nós</p>
  <div class="max-w-5xl mx-auto flex flex-wrap justify-center gap-12 items-center opacity-60 grayscale">
    <!-- repetir N logos -->
    <img src="/logos/cliente-1.svg" alt="Cliente 1" class="h-8" />
    <img src="/logos/cliente-2.svg" alt="Cliente 2" class="h-8" />
  </div>
</section>
```

### 6. Testimonials (carrossel simples)

```html
<section class="py-20 px-4">
  <div class="max-w-4xl mx-auto text-center">
    <blockquote class="text-2xl md:text-3xl font-medium text-gray-900 leading-relaxed">
      "{{TESTIMONIAL}}"
    </blockquote>
    <div class="mt-6 flex items-center justify-center gap-3">
      <img src="{{AVATAR}}" alt="" class="w-12 h-12 rounded-full" />
      <div class="text-left">
        <p class="font-semibold">{{NOME}}</p>
        <p class="text-sm text-gray-500">{{CARGO}}</p>
      </div>
    </div>
  </div>
</section>
```

### 7. FAQ accordion (vanilla, sem lib)

```html
<section class="py-20 px-4 bg-gray-50">
  <div class="max-w-3xl mx-auto">
    <h2 class="text-4xl font-extrabold text-center mb-12">Perguntas frequentes</h2>
    <div class="space-y-3">
      <details class="bg-white rounded-xl p-5 cursor-pointer group">
        <summary class="flex justify-between items-center font-medium">
          {{PERGUNTA}}
          <svg class="w-5 h-5 transition-transform group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
          </svg>
        </summary>
        <p class="mt-3 text-gray-600">{{RESPOSTA}}</p>
      </details>
    </div>
  </div>
</section>
```

### 8. CTA final

```html
<section class="py-20 px-4 bg-gradient-to-br from-blue-600 to-purple-600 text-white">
  <div class="max-w-3xl mx-auto text-center">
    <h2 class="text-4xl md:text-5xl font-extrabold">{{CTA_HEADLINE}}</h2>
    <p class="mt-4 text-xl opacity-90">{{CTA_SUBTITLE}}</p>
    <a href="#form" class="mt-8 inline-block px-8 py-4 bg-white text-blue-600 rounded-xl text-lg font-semibold hover:scale-105 transition">
      {{CTA_BUTTON}}
    </a>
  </div>
</section>
```

### 9. Form de contato / captura de lead

```html
<form id="form" class="max-w-md mx-auto bg-white p-6 rounded-2xl shadow-xl">
  <input name="name" required placeholder="Seu nome" class="w-full mb-3 px-4 py-3 border rounded-lg" />
  <input name="email" type="email" required placeholder="Email" class="w-full mb-3 px-4 py-3 border rounded-lg" />
  <input name="phone" placeholder="WhatsApp (opcional)" class="w-full mb-4 px-4 py-3 border rounded-lg" />
  <textarea name="message" placeholder="Mensagem (opcional)" rows="3" class="w-full mb-4 px-4 py-3 border rounded-lg"></textarea>
  <button class="w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700">
    Enviar
  </button>
  <p class="mt-3 text-xs text-gray-500 text-center">🔒 Seus dados são privados.</p>
</form>
```

### 10. Footer

```html
<footer class="bg-gray-900 text-gray-400 py-12 px-4">
  <div class="max-w-7xl mx-auto grid md:grid-cols-4 gap-8">
    <div>
      <p class="text-white font-bold text-lg">{{LOGO_TEXT}}</p>
      <p class="mt-2 text-sm">{{TAGLINE}}</p>
    </div>
    <div>
      <p class="text-white font-semibold mb-3">Produto</p>
      <ul class="space-y-2 text-sm">
        <li><a href="#features">Recursos</a></li>
        <li><a href="#pricing">Preços</a></li>
        <li><a href="/app/">Entrar</a></li>
      </ul>
    </div>
    <div>
      <p class="text-white font-semibold mb-3">Empresa</p>
      <ul class="space-y-2 text-sm">
        <li><a href="#about">Sobre</a></li>
        <li><a href="#contact">Contato</a></li>
      </ul>
    </div>
    <div>
      <p class="text-white font-semibold mb-3">Contato</p>
      <p class="text-sm">{{EMAIL}}</p>
      <p class="text-sm">{{TELEFONE}}</p>
    </div>
  </div>
  <div class="max-w-7xl mx-auto mt-8 pt-8 border-t border-gray-800 text-center text-sm">
    © {{ANO}} {{EMPRESA}}. Todos os direitos reservados.
  </div>
</footer>
```

## Como plugar com PocketBase

### 1. Collection `leads` (catches unificadas)

```js
// pocketbase/pb_migrations/1700000001_leads.js
migrate((db) => {
  Dao(db).saveCollection(new Collection({
    name: 'leads',
    type: 'base',
    schema: [
      { name: 'name',     type: 'text', max: 120 },
      { name: 'email',    type: 'email', required: true },
      { name: 'phone',    type: 'text', max: 32 },
      { name: 'message',  type: 'text' },
      { name: 'source',   type: 'select', options: { maxSelect: 1, values: ['landing-form', 'footer', 'modal'] } },
      { name: 'page_url', type: 'url' },
      { name: 'utm',      type: 'json' },
    ],
    indexes: ['CREATE INDEX idx_leads_created ON leads (created)'],
  }))
})
```

### 2. Hook pra receber form

```js
// pocketbase/pb_hooks/leads.pb.js
routerAdd('POST', '/api/public/leads', (c) => {
  const data = JSON.parse(c.request.body())
  // anti-spam simples
  if (!data.email || !data.email.includes('@')) return c.json(400, { error: 'email required' })
  if (data.honeypot) return c.json(200, { ok: true })  // bots preenchendo campo escondido

  $app.dao().saveRecord(new Record($app.findCollectionByNameOrId('leads'), {
    name: data.name, email: data.email, phone: data.phone, message: data.message,
    source: data.source || 'landing-form',
    page_url: c.request.header.get('Referer') || '',
    utm: data.utm || {},
  }))

  // notifica dono do app
  const html = `
    <h2>Novo lead: ${data.name || data.email}</h2>
    <p>Email: ${data.email}</p>
    <p>Telefone: ${data.phone || '—'}</p>
    <p>Mensagem: ${data.message || '—'}</p>
    <p>Origem: ${data.source}</p>
    <p>Página: ${c.request.header.get('Referer')}</p>
  `
  $app.newMailClient().send(new MailerMessage({
    from: { address: $app.settings().meta.senderAddress, name: 'Site' },
    to: [{ address: $app.settings().meta.senderAddress }],
    subject: '🎯 Novo lead: ' + (data.name || data.email),
    html,
  }))

  return c.json(200, { ok: true })
})

routerAdd('POST', '/api/public/newsletter', (c) => {
  const { email } = JSON.parse(c.request.body())
  try { $app.dao().saveRecord(new Record($app.findCollectionByNameOrId('subscribers'), { email })) } catch {}
  return c.json(200, { ok: true })
})
```

### 3. JS no front da landing pra conectar

```ts
// apps/landing/src/main.ts (adicionar no final)
document.querySelectorAll('form[data-lead-form]').forEach(form => {
  form.addEventListener('submit', async (e) => {
    e.preventDefault()
    const fd = new FormData(form as HTMLFormElement)
    const data = Object.fromEntries(fd.entries())

    // capture UTM
    const url = new URL(location.href)
    data.utm = {}
    url.searchParams.forEach((v, k) => { if (k.startsWith('utm_')) data.utm[k] = v })

    try {
      const res = await fetch('/api/public/leads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (res.ok) {
        ;(form as HTMLFormElement).innerHTML = '<div class="text-center p-8"><p class="text-2xl">✅ Recebemos!</p><p>Entraremos em contato em breve.</p></div>'
      }
    } catch {
      alert('Erro ao enviar. Tente novamente.')
    }
  })
})
```

> Forma mais simples: colocar `<form action="/api/public/leads" method="POST">` direto. PB recebe o POST e responde... mas se o PB não estiver na mesma origem (CDN independente), vai ter CORS. Solução: fetch via JS.

## Padrões de design (customize por cliente)

### Paleta por segmento

```ts
// apps/landing/src/theme.ts — use com template literals no main.ts
export const themes = {
  saas_b2b:    { primary: '#3b82f6', accent: '#8b5cf6', bg: '#f8fafc', dark: '#0f172a' },
  ecommerce:   { primary: '#f59e0b', accent: '#dc2626', bg: '#fffbeb', dark: '#1c1917' },
  health:      { primary: '#10b981', accent: '#06b6d4', bg: '#f0fdf4', dark: '#064e3b' },
  food:        { primary: '#dc2626', accent: '#f59e0b', bg: '#fef2f2', dark: '#7f1d1d' },
  education:   { primary: '#6366f1', accent: '#ec4899', bg: '#eef2ff', dark: '#1e1b4b' },
  portfolio:   { primary: '#0f172a', accent: '#64748b', bg: '#ffffff', dark: '#0f172a' },
  event:       { primary: '#a855f7', accent: '#ec4899', bg: '#faf5ff', dark: '#581c87' },
} as const
```

Uso:
```html
<div class="bg-[#3b82f6]">...</div>
<!-- ou gerar CSS variables via JS -->
```

### Fontes Google por vibe

```html
<!-- Moderna tech: Inter -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap" rel="stylesheet">

<!-- Elegante luxo: Playfair Display + Inter -->
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;600&display=swap" rel="stylesheet">

<!-- Divertida criativa: Poppins + Pacifico -->
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&family=Pacifico&display=swap" rel="stylesheet">
```

## SEO mínimo (mesmo sem foco, faz o básico)

### Sitemap dinâmico via hook PB

```js
// pocketbase/pb_hooks/seo.pb.js
routerAdd('GET', '/sitemap.xml', (c) => {
  const base = c.request.host
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemapindex.org/sitemapindex.org/schemas/sitemap/0.9">
  <url><loc>${base}/</loc><priority>1.0</priority></url>
</urlset>`
  c.response.header().set('Content-Type', 'application/xml')
  return c.string(200, xml)
})

routerAdd('GET', '/robots.txt', (c) => {
  return c.string(200, `User-agent: *\nAllow: /\nSitemap: ${c.request.host}/sitemap.xml\n`)
})
```

### Meta tags dinâmicas (se landing tem várias seções com URLs únicas)

Não recomendado pra landing one-page — use meta estáticas no `<head>`.

## Deploy — onde hospedar a landing

| Opção | Prós | Contras |
|---|---|---|
| **Netlify** | Drag-drop, grátis, formulário nativo | Vendor lock-in |
| **Vercel** | Framework-aware (Vite), rápido | Vendor lock-in |
| **Cloudflare Pages** | Rápido, barato, global | UI menos amigável |
| **GitHub Pages** | Grátis pra repo público | Sem HTTPS custom sem domínio próprio |
| **PocketBase static** | Já configurado, sem CDN extra | Compartilha origem com API |

### Setup Vercel (mais rápido)

```bash
npm i -g vercel
cd apps/landing
vercel              # login + detecta Vite
vercel --prod       # produção
```

Adicione domínio em `vercel.com → domains`. HTTPS automático. **Grátis**.

### Setup Netlify (drag-drop)

```bash
npm run build:landing
# arrasta apps/landing/dist pra https://app.netlify.com/drop
```

### Dentro do PocketBase (estratégia C)

Já vem no template! `npm run build && npm run copy:landing`. Landing vai pra `/` do PB.

## Estratégia multi-cliente (receita de agência)

Quando você pegar o 5º cliente, vai cansar de clonar. Receita:

1. **Crie `apps/landing-base/`** — template com todos os componentes
2. **Pra cada cliente**: copie `apps/landing-base/` → `apps/landing-cliente-x/`
3. **Customize no `main.ts`** — branding, copy, cores
4. **Atualize proxy no `vite.config.ts`** se for testar local
5. **Deploy em subdomínio**: `cliente-x.suaagencia.com.br`

Ou, mais avançado:

1. **Uma única landing** parametrizada via env vars:

```ts
// apps/landing-cliente/src/config.ts
const client = {
  name: import.meta.env.VITE_CLIENT_NAME,
  tagline: import.meta.env.VITE_CLIENT_TAGLINE,
  color: import.meta.env.VITE_CLIENT_PRIMARY_COLOR,
  // ...
}
```

2. **Cada cliente tem seu `.env.production`** e mesmo build, mas gera via:
```bash
cd apps/landing-cliente
VITE_CLIENT_NAME="Acme" VITE_CLIENT_PRIMARY_COLOR="#dc2626" npm run build
```

Vantagem: 1 codebase, várias marcas. Desvantagem: copy única compartilhada (não dá pra ter texto radicalmente diferente).

## Checklist de entrega pro cliente

Antes de mandar a URL final:

- [ ] HTTPS funcionando
- [ ] Meta tags (title, description, og:image)
- [ ] Favicon
- [ ] Imagens otimizadas (use `?w=800` no Cloudflare ou `<img loading="lazy">`)
- [ ] Mobile testado (Chrome DevTools, lighthouse)
- [ ] Form de contato testado (envia email + grava no PB)
- [ ] Links internos funcionando (anchor links, anchors, etc)
- [ ] CTAs com destino correto
- [ ] Analytics configurado (Plausible ou GA4)
- [ ] Pixel do Meta se cliente roda ads
- [ ] Cookie banner **se** tiver analytics que use cookie
- [ ] 404 page customizada (mínimo)
- [ ] Email de contato respondendo (testei antes)
- [ ] DNS configurado (cliente geralmente precisa do help nisso)
- [ ] Backup da hospedagem / documentação de como atualizar

## Próximas skills que destravam projetos

| Próxima skill | Quando precisar |
|---|---|
| `domain-admin-panel` (já existe) | Cliente quer gerenciar usuários via UI |
| `domain-saas-billing` (já existe) | Cliente quer cobrar mensalidade |
| `domain-crm-leads` (já existe) | Leads precisam virar pipeline de vendas |
| `domain-storage-files` (já existe) | Upload de imagens/docs |
| `domain-email-hooks` (já existe) | Confirmações, notificações |
| Multi-idioma (não tem ainda) | Cliente quer EN/ES além de PT |

Se quiser alguma skill adicional específica de landing que não cobri (ex: página de "em construção", popup de saída, integração com WhatsApp click-to-chat, AB testing com feature flag), me fala que eu adiciono.