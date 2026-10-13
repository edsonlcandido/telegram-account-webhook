/// <reference path="../pb_data/types.d.ts" />

// Landing page na raiz (sem fallback SPA pq a landing é estática)
routerAdd("GET", "/{path...}", $apis.static("pb_public", false))

// Web app em /app/* com fallback SPA (index.html) pra sub-rotas do Vue Router
// tipo /app/dashboard. Sem isso, qualquer sub-rota retorna 404.
routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", true))
