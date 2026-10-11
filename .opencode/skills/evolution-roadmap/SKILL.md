---
name: evolution-roadmap
description: Estratégia macro de evolução do projeto no template pocketbase-vue-tailwind-template — em que ordem adicionar features, quais skills usar em cada fase, e como evitar retrabalho. Use quando o usuário quiser planejar a próxima sprint, priorizar MVP, ou decidir "o que vem depois do login".
---

# Roadmap — Como evoluir o template

O template é um **canivete suíço**. Sem um roadmap, você perde tempo construindo a coisa errada. Esta skill é a visão macro — combine com as **skills técnicas** (vue-pinia-store, vue-router-auth…) e **skills de domínio** (domain-crm-leads, domain-saas-billing…) pra implementar.

## Fases recomendadas

```
Fase 0 → 1 → 2 → 3 → 4
       │   │   │   │
       ▼   ▼   ▼   ▼
    Setup  Auth  Domínio  Features  Polimento
    (1h)   (1d)  (3-7d)   avançadas (ongoing)
```

## Fase 0 — Setup (1h)

Antes de qualquer feature, valide o ambiente:

```bash
git clone ... && cd meu-app
npm install
npm run dev                       # PB :8090, Landing :5173, Web :5174
```

Crie admin PB em `http://localhost:8090/_/`. Acesse o app em `/app/dashboard`.

> Use a skill `pocketbase-template-scaffold` se travar.

Checklist Fase 0:
- [ ] PB admin criado
- [ ] Collection `users` confirmada (vem por default)
- [ ] Login funcionando em `/app/login`
- [ ] Tailwind v4 carregando (testar uma classe qualquer em Dashboard)

## Fase 1 — Auth (1 dia)

O template já tem `auth.ts`, login/register, router guard. **Raramente precisa mexer aqui.** Mas pode customizar:

- Adicionar campos ao user: `name`, `avatar`, `role` (via migration)
- Recuperação de senha: criar view `/forgot-password` + collection `password_resets`
- OAuth (Google/GitHub): ver `domain-rbac` + skill futura de OAuth
- Logout em dropdown de menu

> Skill útil: `vue-router-auth`, `pocketbase-collections`.

## Fase 2 — Domínio principal (3-7 dias)

Aqui é onde o app se diferencia. **Comece pelo modelo de dados**, não pela UI.

### Passo a passo genérico

1. **Desenhar 1-3 collections core** (ex: CRM → `leads`, `contacts`, `activities`)
2. **Criar migrations JS** (versionadas no git)
3. **Configurar regras de acesso** (CRUD por ownership)
4. **Stub do Pinia store** (mesmo antes da UI)
5. **1 view CRUD mínima** (lista + form) — validar fluxo end-to-end
6. **Depois polir** (filtros, paginação, validações, UX)

### Qual domínio?

| Se o app é... | Vai pra skill... |
|---|---|
| CRM / pipeline de vendas | `domain-crm-leads` |
| Blog / portal de conteúdo | `domain-blog-cms` |
| SaaS com pagamento | `domain-saas-billing` |
| Chat / dashboards live | `domain-realtime` |
| Upload de imagens / documentos | `domain-storage-files` |
| Notificação por email | `domain-email-hooks` |
| Permissões granulares (admin/editor/viewer) | `domain-rbac` |

Pode combinar: SaaS com CRM (`domain-crm-leads` + `domain-saas-billing`).

## Fase 3 — Features avançadas

Típico adicionar nessa fase:

- 📊 **Dashboard com métricas** → `domain-realtime` (subscriptions) + agregações
- 🔍 **Busca full-text** → filter do PB com `~` + índice SQL
- 📎 **Upload de anexos** → `domain-storage-files`
- 📧 **Emails transacionais** → `domain-email-hooks`
- 💳 **Pagamentos** → `domain-saas-billing`
- 🏢 **Multi-tenant** → relation em todas as collections → `team_id`
- 🔔 **Notificações in-app** → `notifications` collection + realtime
- 📱 **PWA / offline** → service worker + vite-plugin-pwa
- 🌐 **i18n** → vue-i18n + `pb_settings` collection

## Fase 4 — Polimento (ongoing)

- Type safety end-to-end: gerar types do PB e usar em tudo
- Testes: Vitest (unit) + Playwright (E2E)
- CI/CD: GitHub Actions → docker-pb-deploy
- Monitoramento: Sentry (`VITE_SENTRY_DSN`)
- SEO: meta tags + sitemap pra landing
- Performance: lazy load views, virtualização de listas grandes

## Anti-padrões comuns

| ❌ Pular pra UI | ✅ Modelar dados primeiro |
|---|---|
| ❌ Construir tudo de uma vez | ✅ MVP focado, validar com 1 user |
| ❌ Over-engineering (multi-tenant antes de ter 2 clientes) | ✅ Escalar quando precisar |
| ❌ Ignorar migrations | ✅ Toda collection → migration JS |
| ❌ Hardcoded config | ✅ `.env.*` + `import.meta.env.VITE_*` |
| ❌ `admin = true` em todo user | ✅ RBAC real (`domain-rbac`) |

## Ordem sugerida de skills pra um projeto novo

1. `pocketbase-template-scaffold` → setup
2. `pocketbase-collections` → modelagem base
3. `vue-pinia-store` → state management
4. `vue-router-auth` → rotas/guards
5. `tailwind-vue-component` → UI
6. `domain-<seu-caso>` → feature end-to-end
7. `vite-env-config` → envs quando começar a ter integrações
8. `docker-pb-deploy` → quando for publicar

## Quando pular uma fase

- **Protótipo descartável** → Fase 0 + esboço da Fase 2, sem migrations
- **Hackathon** → Hardcode, sem auth robusta, single-user
- **Cliente único interno** → Pode pular multi-tenant/RBAC por um bom tempo

## Métrica de progresso

| Fase | Tempo típico | Saída |
|---|---|---|
| 0 → 1 | 1h + 1d | App logando, collection users customizada |
| 1 → 2 | 3-7d | MVP do domínio navegável |
| 2 → 3 | 1-2 sem | Features que diferenciam seu app |
| 3 → 4 | contínuo | Robustez, escala, polimento |

> **Regra de ouro**: se você está há mais de 1 dia sem conseguir mostrar uma tela nova pro usuário, está fazendo demais. Volte pra Fase 2, valide com 1 user, depois escale.