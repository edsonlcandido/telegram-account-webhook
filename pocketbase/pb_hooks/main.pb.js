/// <reference path="../pb_data/types.d.ts" />

/**
 * PocketBase Hook: SPA Routing para o Web App
 * 
 * Serve o Vue SPA em /app/* com index fallback para SPA routing.
 * Sem dependência de $apis.static().
 */

routerAdd("GET", "/app/{path?}", function(c) {
    c.staticFile("pb_public/app/index.html")
})
