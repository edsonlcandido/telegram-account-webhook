/// <reference path="../pb_data/types.d.ts" />

/**
 * SPA Routing - Serve Vue app em /app/*
 * Compatível com PocketBase 0.40.x
 */

routerAdd("GET", "/app/{path?}", function(c) {
    const path = c.pathParam("path")
    if (!path || path === "") {
        return c.staticFile("pb_public/app/index.html")
    }
    try {
        return c.staticFile("pb_public/app/" + path)
    } catch (e) {
        return c.staticFile("pb_public/app/index.html")
    }
})
