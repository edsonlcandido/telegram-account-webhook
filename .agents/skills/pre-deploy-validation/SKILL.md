---
name: pre-deploy-validation
description: |
  Run static validation BEFORE every deploy that touches migrations or
  frontend code. Two checks: (1) PocketBase locally with fresh pb_data
  to confirm the new migration applies cleanly, (2) `npm run build` on
  the apps that were touched (apps/web, apps/landing) to catch TS /
  build errors. Trigger on requests that mention "validar antes de
  deploy", "rodar local antes", "verificar migration", "npm build",
  "static check", "pre-deploy", or when the user signals a deploy is
  imminent (commit + push + deploy). Pair this skill with
  `.agents/skills/pocketbase-migrations` (for migration syntax rules)
  and `.agents/skills/pocketbase-jsvm` (for hook rules).
---

# Pre-deploy validation (this project)

Easypanel rebuild leva 3-5 min, e o container de PB pode reiniciar em
loop se uma migration falhar — fica fora do ar sem aviso. **Antes de
qualquer `git push` que toque em `pocketbase/pb_migrations/*` ou
`apps/web/src/**` / `apps/landing/src/**`, rodar as duas validações
abaixo**. Se quebrar, NÃO commit / push / deploy.

## Check 1 — PocketBase migration roda limpa

```bash
# 1) Limpar pb_data (estado limpo, garante que a migration roda do zero)
cd pocketbase
cmd.exe /c "C:\Users\edson\.minimax\bin\mavis-trash.cmd -- pb_data"
# Equivalente: rm -- pocketbase/pb_data  (ambos roteiam pelo launcher trusted)

# 2) Subir o PB local. Aplica TODAS as migrations em pb_migrations/.
#    Roda em background (PB serve indefinitely).
.\pocketbase.exe serve --http=127.0.0.1:8090
```

Aguardar o startup terminar. Olhar o stdout:

- **Sinal verde**: `Server started at http://127.0.0.1:8090` + nada
  de `Error: failed to apply migration ...`. PB loga `Applying
  migration NNN_xxx.js` por migration aplicada, mas se não logou
  nada estranho é porque rodou limpo.
- **Sinal vermelho**: `Error: failed to apply migration NNN_xxx.js` →
  NÃO commitar. Sincronizar com a skill
  `.agents/skills/pocketbase-migrations/SKILL.md` (regras de field
  syntax, idempotência, timestamps).

```bash
# 3) Verificações de sanidade (sqlite3 no pb_data):

#    a) Lista de migrations aplicadas (deve bater com arquivos em pb_migrations/)
sqlite3 pb_data/data.db "SELECT file FROM _migrations ORDER BY file"

#    b) Schema da collection que você modificou/criou
sqlite3 pb_data/data.db "PRAGMA table_info(<nome_da_collection>)"
#    Exemplo:
sqlite3 pb_data/data.db "PRAGMA table_info(telegram_messages)"
#    → deve listar o novo campo (ex: sender_username TEXT) e todos
#    os anteriores

#    c) Pra collection nova, conferir que a row existe no _collections
sqlite3 pb_data/data.db "SELECT name FROM _collections ORDER BY name"
```

**Pós-checks** (se você alterou dados existentes via migration):

```bash
# Conferir contagem de rows pós-migração
sqlite3 pb_data/data.db "SELECT COUNT(*) FROM <collection>"

# Conferir que dados foram migrados conforme esperado
sqlite3 pb_data/data.db "SELECT id, name FROM <collection> LIMIT 5"
```

Parar o PB local (Ctrl+C) quando terminar — não é um daemon que
deve ficar rodando.

### Quando skippar

- Mudou só `apps/web/**` ou `apps/landing/**` sem migration → skip
  Check 1, vai direto pro Check 2.
- Mudou só `backend/main.py` ou `pocketbase/pb_hooks/*.pb.js` (que
  são recarregados sem migration) → skip Check 1.

## Check 2 — `npm run build` nos apps modificados

```bash
# 1) apps/web (Vue 3 + TypeScript, frontend principal)
cmd.exe /c "cd /d D:\repos\telegram-account-webhook\apps\web && npm run build"
# Equivale a: vue-tsc (TS check) && vite build

# 2) apps/landing (se você mexeu — Vue 3 + TS, landing estática)
cmd.exe /c "cd /d D:\repos\telegram-account-webhook\apps\landing && npm run build"
```

**Sinal verde**: termina com `✓ built in X.XXs`, exit code 0.

**Sinais vermelhos comuns** (todos bloqueiam o deploy):

- `TS6133 "declared but never read"` — declaraste uma const que não
  foi usada (no template, no script, nem em comentário). Apaga a
  declaração. `vue-tsc` é estrito por default.
- `error TS2XXX: ...` — qualquer erro de TypeScript. Tem que
  consertar antes de commitar.
- `Build failed with X errors` no console do Vite — erro de import,
  template, ou CSS. Leia a stack e conserte.
- Exit code != 0 (com `&&` isso para a próxima coisa) — se viu, o
  build falhou.

**Por que `cmd.exe /c` e não `npm run build` direto**: a `npm.ps1` do
PowerShell é bloqueada pela ExecutionPolicy padrão do Windows
("não pode ser carregado porque o arquivo não está assinado
digitalmente"). `cmd.exe /c` bypassa isso sem mexer em policy
global.

### Quando skippar

- Mudou só `backend/main.py` (Python) → skip Check 2 (Python não tem
  build step; só syntax check).
- Mudou só `pocketbase/**` → skip Check 2.

## Atalho — checklist completo (toda vez que for commitar)

```bash
# 1) Quais áreas foram tocadas?
git status --short

# 2) Se tocou migration:
#    - Check 1 (PB local) ↑
# 3) Se tocou apps/web ou apps/landing:
#    - Check 2 (npm run build) ↑
# 4) Se tocou backend/main.py:
#    - python -c "import ast; ast.parse(open(r'D:\repos\telegram-account-webhook\backend\main.py', encoding='utf-8').read())"
# 5) Se tudo verde:
git add -A
git commit -m "..."
git push
# 6) Deploy via Easypanel MCP ou webhook
```

## Erros comuns que PULARAM essas validações já custaram deploy rollbacks

1. **Migration com field options aninhado em `options: {}`** (PB 0.22 style)
   → erro `(values: cannot be blank.)` em prod. Sintoma: container
   reinicia em loop.
2. **Migration chamando `app.findAllRecords(... { filter: ... })`** (não
   existe no PB 0.40+ JSVM)
   → erro `Object has no member 'filter'`. Aplica parcialmente, deixa
   estado inconsistente. Próxima migration precisa ser defensiva.
3. **Vue template com `<` em string literal** (ex: `{{$json.body.x}}` pra
   documentar n8n)
   → parser SFC do Vue fecha o bloco `</script>` no primeiro `</` que
   achar, quebra o parse. Sintoma: erro de "Unexpected end of tag" em
   build local.
4. **TS6133 "declared but never read"** em `.vue`
   → `vue-tsc` é estrito, falha o build. Sintoma: build local quebra
   com exit code 1.

Todos esses quebrariam o build local / migrariam mal. Deploy só ia
mostrar quando o container tentasse subir e Easypanel ficasse
reinciciando 5min sem aviso.

## When to invoke this skill

- User pede deploy e há migration ou front a ser validado
- User diz "commita e sobe" / "manda pra prod" / "deploy"
- Antes de qualquer `git push` que toque em `pocketbase/pb_migrations/*`,
  `apps/web/src/**`, ou `apps/landing/src/**`
- Quando o agente se pega fazendo `git commit` sem ter rodado Check 1
  ou Check 2 antes (verificar via `git status` se houver migrations
  pendentes)

## Related skills

- `.agents/skills/pocketbase-migrations/SKILL.md` — regras de sintaxe
  de migration (campos, timestamps, idempotência)
- `.agents/skills/pocketbase-jsvm/SKILL.md` — regras de hooks JS no
  PB 0.40+ (top-level funcs invisíveis, `resp.statusCode` vs
  `res.status`, `e.next()` em AfterSuccess)
- AGENTS.md (raiz) — workflow de git + commit + deploy desse projeto
