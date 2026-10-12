/// <reference path="../pb_data/types.d.ts" />

// Landing page na raiz
routerAdd("GET", "/{path...}", $apis.static("pb_public", false))

// Web app em /app/*
routerAdd("GET", "/app/{path...}", $apis.static("pb_public/app", false))
