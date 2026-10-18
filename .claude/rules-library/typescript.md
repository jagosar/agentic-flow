---
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/*.js"
  - "**/*.jsx"
  - "**/*.mjs"
  - "**/*.cjs"
---
<!-- Adaptado de ECC (rules/typescript), https://github.com/affaan-m/ECC — MIT License, Copyright (c) 2026 Affaan Mustafa. -->
# TypeScript y JavaScript

Amplía las [reglas comunes](common.md).

## Estilo

- Tipos explícitos de parámetros y retorno en todo lo exportado; inferencia en las variables locales obvias.
- `interface` para formas de objeto extensibles; `type` para uniones, intersecciones y tipos utilitarios.
- Uniones de literales en vez de `enum`, salvo que haga falta por interoperabilidad.
- Sin `any`: `unknown` para lo que llega de fuera, y se estrecha antes de usarlo. Genéricos cuando el tipo depende de quien llama.
- `const` por defecto; spread o `structuredClone` en vez de mutar objetos recibidos.
- En ficheros `.js`, JSDoc cuando aclare los tipos.

## Errores

- Clases de error propias que extienden `Error`, con `name` y `cause`.
- Toda promesa se espera o se devuelve: nada de promesas sueltas. `try/catch` alrededor del `await`, no `.catch` vacío.
- Valida en la frontera lo que llega sin tipo (JSON, cuerpo de una petición), con un esquema (por ejemplo zod) si el proyecto ya lo usa.

## Tests

- El runner que ya use el proyecto (`vitest`, `jest` o `node --test`).
- Tests de componentes por comportamiento visible (Testing Library), no por detalles internos.
- Playwright para los flujos de extremo a extremo críticos, si el proyecto lo tiene.
- Sin `console.log` en el código de producción; se usa el logger del proyecto.

## Seguridad

- Secretos con `process.env`, comprobados al arrancar.
- Nunca `eval`, `new Function` ni `innerHTML` con datos externos; en React, nada de `dangerouslySetInnerHTML` sin sanear.
- `child_process.execFile` o `spawn` con lista de argumentos, no `exec` con texto concatenado.
- `npm audit` (o el equivalente del gestor) cuando cambie el lockfile.

## Comandos habituales

| Fase de `verify` | Comando típico |
|---|---|
| build | `npm run build` |
| types | `npx tsc --noEmit` |
| lint | `npx eslint .` |
| tests | `npm test` o `npx vitest run` |
