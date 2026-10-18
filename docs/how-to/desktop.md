# How-to: Claude Code Desktop

Antes, lee los requisitos de [README.md](README.md).

## 1. Preparar el proyecto

- **Proyecto nuevo:** en GitHub, `jagosar/agentic-flow` → **Use this template** → clónalo en tu máquina.
- **Proyecto existente:** copia `.claude/` y la línea `.claude/state/` del `.gitignore` y haz commit.

## 2. Abrir la sesión

1. Abre la app de Claude → pestaña **Code**.
2. Nueva sesión → elige la carpeta del repo. Si la app te ofrece trabajar en un worktree, puedes aceptar: el flow funciona igual.
3. En el selector de modelo, elige **Opus 5.5**. `/architect` ya fuerza Opus 5.5 desde su frontmatter, pero el orquestador usa el modelo de la sesión.
4. Modo de permisos: **Ask** para la primera vez. Cuando conozcas el flow, **Auto-accept edits** ahorra clics al arquitecto.

## 3. Diseñar

```
/architect Quiero un servicio de reservas con API REST, Postgres y autenticación JWT
```

- Las preguntas aparecen como tarjetas con opciones. La recomendada va primero.
- Al final, el arquitecto valida el manifiesto (`agentic.py validate`) y te pide aprobación.
- Abre `architecture.md` en el panel de ficheros y revísalo antes de aprobar.

## 4. Implementar

```
/implement
```

- El orquestador comprueba si hay un `claude` en el `PATH`. Ojo: la app de escritorio trae su propio Claude Code, que no cuenta. Para el modo A necesitas el CLI instalado aparte (`npm install -g @anthropic-ai/claude-code` o el instalador oficial) y con sesión iniciada.
- En el modo A, cada ola corre como tarea en segundo plano. Puedes seguir hablando con la sesión mientras tanto, y la app te avisa cuando acaba.
- La regla `allow` de `.claude/settings.json` permite `agentic.py` sin preguntarte cada vez.
- Al terminar las olas y la integración, lanza QA solo.

## 5. Revisar

- Panel **Diff**: todos los cambios de la ejecución.
- Informe de QA: `qa/report.md`.
- Commit: pídeselo a la sesión ("haz commit de todo con un mensaje descriptivo") o hazlo tú. El push lo haces tú, porque está bloqueado para los agentes.

## Trucos

- **Varias features a la vez:** abre una sesión por feature, cada una en su worktree. Cada una tiene su propio `architecture.md` en su rama.
- **Desde el móvil:** activa Remote Control en la sesión y podrás seguir la entrevista del arquitecto desde el teléfono.
- **Relanzar un WP:** escribe en la sesión "relanza WP-03 de la ola 2 para corregir los defectos de QA". Lo hace con `run-wave 2 WP-03`.
