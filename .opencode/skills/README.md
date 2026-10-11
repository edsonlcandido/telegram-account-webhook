# Skills para OpenCode / Mavis

Esta pasta contém **skills** (instruções estruturadas) que agentes de IA compatíveis com o formato [Mavis/opencode](https://github.com/nicepkg/mavis) usam pra trabalhar de forma mais efetiva com este template.

## O que são skills?

Skills são **prompts reutilizáveis** que guiam o agente de IA em tarefas específicas deste stack. Cada skill tem:

- **Nome** (kebab-case) — o agente descobre via autoload
- **Descrição** (frontmatter) — define **quando** a skill é acionada
- **Corpo** — como executar a tarefa, com snippets e padrões do projeto

Quando você pede algo ao agente, ele lê a `description` de cada skill pra decidir qual carregar. **Você não precisa chamar manualmente** — basta descrever o que quer.

Exemplos de prompts que disparam skills automaticamente:

| Você fala | Skill acionada |
|---|---|
| "como faço pra criar uma collection nova?" | `pocketbase-collections` |
| "adicionar leads com funil kanban" | `domain-crm-leads` |
| "configurar proxy do Vite" | `vite-env-config` |
| "deploy com Docker" | `docker-pb-deploy` |

## Como usar localmente

### Opção 1 — usar como `.opencode/skills/`

```bash
# dentro do projeto clonado deste template:
ln -s ../skills .opencode/skills
# ou copie:
cp -r skills .opencode/skills
```

### Opção 2 — usar como `~/.mavis/skills/` (global)

```bash
mkdir -p ~/.mavis/skills
cp -r skills/* ~/.mavis/skills/
```

### Opção 3 — só ler manualmente

Abra qualquer `SKILL.md` em qualquer editor. O conteúdo é referência útil independente de IA.

## Índice das skills

### 🧱 Camada técnica (como fazer X)

| Skill | Quando usar |
|---|---|
| `pocketbase-template-scaffold` | Clonar, instalar, rodar tudo pela primeira vez. Resolver conflito de porta/Hook/proxy. |
| `pocketbase-collections` | Criar collection nova, migration JS, hooks (`onRecordAfterCreate*` etc), regras de acesso. |
| `vue-pinia-store` | Adicionar store Pinia no padrão do projeto (Composition API + `pb.authStore.onChange`). |
| `vue-router-auth` | Adicionar rota protegida, `meta: requiresAuth`, lazy loading, redirect por role. |
| `tailwind-vue-component` | Criar componente Vue + Tailwind v4 (`@import "tailwindcss"`, sem config JS). |
| `vite-env-config` | Variáveis `VITE_*`, `.env.local` em Codespaces, proxy `/api`/`/_` pra PocketBase. |
| `docker-pb-deploy` | Build, rodar, versionar imagem, CI com GHCR, healthcheck, backup do `pb_data`. |
| `monorepo-add-app` | Criar `apps/<novo>/` plugado no build pipeline (script raiz, copy, hook PB, Dockerfile stage). |

### 🗺️ Estratégia

| Skill | Quando usar |
|---|---|
| `evolution-roadmap` | Em que ordem adicionar features, quando pular etapas, anti-padrões comuns. |

### 🎯 Domínios completos (exemplos end-to-end)

| Skill | Quando usar |
|---|---|
| `domain-crm-leads` | CRM com leads/contacts/activities + funil kanban + dashboard de pipeline |
| `domain-blog-cms` | Blog/CMS com posts/categorias/tags/comentários + slug auto + editor |
| `domain-saas-billing` | SaaS com Stripe Checkout + webhook + entitlements + pricing page |
| `domain-realtime` | Kanban multi-user, chat, presença online, notificações in-app via SSE |
| `domain-storage-files` | Avatar, anexos múltiplos, XHR com progress, signed URLs, S3-compatible |
| `domain-email-hooks` | Templates HTML, Resend/SMTP, fila com retry, bounces, cron de digest |
| `domain-rbac` | Roles no user, matriz de permissions, diretiva `v-can`, multi-team, audit log |
| `domain-admin-panel` | Bootstrap do 1º super admin, UI de gerenciamento de usuários, convite por email, reset de senha forçado, impersonar |
| `domain-landing-pages` | Receitas de landing por segmento (SaaS, local, portfólio, evento…), componentes prontos, integração com PB, estratégia multi-cliente |

## Workflow sugerido

1. **Primeira vez no template?** → Comece por `pocketbase-template-scaffold` + `evolution-roadmap`
2. **Vai adicionar uma feature?** → Olhe a skill de domínio correspondente primeiro, depois as técnicas (Pinia, Router, Tailwind)
3. **Deploy?** → `docker-pb-deploy`
4. **Customização avançada?** → Combine várias skills (ex: CRM + RBAC + Storage + Email)

## Contribuindo

Pra adicionar uma skill nova:

1. Crie a pasta: `skills/<nome-em-kebab-case>/`
2. Crie `SKILL.md` com frontmatter:

   ```yaml
   ---
   name: minha-skill
   description: Quando o agente deve carregar isso. Seja específico — é a única coisa que ele vê antes de decidir.
   ---
   ```

3. Corpo em Markdown: **comandos prontos pra copiar**, **snippets do template**, **checklist**, **anti-padrões**
4. Adicione entrada no índice deste README
5. Abra PR 🎉

## Licença

Mesma do template (MIT).