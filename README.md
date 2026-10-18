# agentic-flow

Flow agéntico para Claude Code: un arquitecto (Opus 5.5) define `architecture.md`, varios implementadores desarrollan en paralelo usando solo ese documento y un agente QA decide qué probar y valida el resultado.

**Guías por entorno:** [docs/how-to/](docs/how-to/README.md) (Desktop, VS Code, terminal, JetBrains, web/iOS, GitHub Actions).

```
.claude/commands/architect.md    → /architect   (Opus 5.5)
.claude/commands/implement.md    → /implement   (orquestador: olas + integración + QA)
.claude/commands/qa.md           → /qa          (solo QA)
.claude/agents/implementer.md    → subagente    (último Sonnet, uno por WP)
.claude/agents/qa.md             → subagente    (último Sonnet)
.claude/bin/agentic.py           → guardarraíles y lanzador paralelo
.claude/settings.json            → hook PreToolUse y reglas allow/deny
```

## Uso

1. `/architect <qué quieres desarrollar o mejorar>`: entrevista por rondas y escribe `architecture.md` con un manifiesto `json wp-manifest`.
2. Revisa y aprueba `architecture.md`.
3. `/implement`: lanza las olas (cada WP de una ola en paralelo), integra y pasa QA.

Requisitos: `python3`, `git` y Claude Code 2.1.280 o posterior (para Opus 5.5).

## Paralelismo

- **Modo A (CLI `claude` en el `PATH`):** `agentic.py run-wave N` lanza un `claude -p --agent implementer --model sonnet` por WP, todos a la vez y sin conectores MCP. El paralelismo es real y no depende del modelo.
- **Modo B (sin CLI):** el orquestador lanza los subagentes con varias llamadas a Agent en un mismo mensaje.

**Modelos:** el arquitecto usa Opus 5.5. Los implementadores y QA usan **siempre el último Sonnet**, mediante el alias `sonnet`, que Claude Code resuelve al Sonnet más reciente que conoce. No se puede cambiar por configuración, y `validate` falla si la definición de un agente orquestado declara otro modelo. Para recibir un Sonnet nuevo en cuanto salga, mantén Claude Code actualizado.

## Guardarraíles

| Qué | Cómo |
|---|---|
| Cada WP solo escribe sus ficheros; QA solo escribe en `qa/` | Hook `PreToolUse` sobre Write/Edit, contra el manifiesto |
| Sin git, sin dependencias nuevas, sin lanzar otras sesiones de Claude | Hook `PreToolUse` sobre Bash, dentro de un WP o de QA |
| Sin push ni borrados masivos | `permissions.deny` en `settings.json`, para todos |
| Comandos permitidos mínimos | `allow_bash` del manifiesto (modo A) |
| Comprobación de propiedad al cerrar cada etapa | `snapshot` + `check-wave`: cualquier fichero cambiado fuera de su propietario hace fallar la etapa |
| Manifiesto coherente | `validate`: propietarios únicos (QA incluido), olas y dependencias |

Limitación: un agente podría escribir con Bash (`echo > fichero`) saltándose el hook de Write. En modo A solo puede ejecutar los comandos de `allow_bash`, y en los dos modos `check-wave` lo detecta al cerrar la etapa.

## En otros proyectos

- Proyecto nuevo: "Use this template" en GitHub.
- Proyecto existente: copia `.claude/` y la línea `.claude/state/` del `.gitignore` y haz commit en la rama que vayas a usar (las sesiones de iOS solo ven lo commiteado).
