# agentic-flow

Flow agéntico para Claude Code: un arquitecto (Opus 5.5) define `architecture.md` y varios implementadores (Sonnet 5.5) desarrollan en paralelo usando solo ese documento.

```
.claude/commands/architect.md    → /architect  (Opus 5.5)
.claude/commands/implement.md    → /implement  (orquestador)
.claude/agents/implementer.md    → subagente   (Sonnet 5.5, uno por WP)
.claude/bin/agentic.py           → guardarraíles y lanzador paralelo
.claude/settings.json            → hook PreToolUse y reglas deny
```

## Uso

1. `/architect <qué quieres desarrollar o mejorar>`: entrevista por rondas y escribe `architecture.md` con un manifiesto `json wp-manifest`.
2. Revisa y aprueba `architecture.md`.
3. `/implement`: lanza las olas. Cada WP de una ola corre en paralelo.

Requisitos: `python3` y `git` en el entorno.

## Paralelismo

- **Modo A (Desktop / CLI):** `python3 .claude/bin/agentic.py run-wave N` lanza un `claude -p --agent implementer --model claude-sonnet-5-5` por WP, todos a la vez. El paralelismo es real y no depende del modelo.
- **Modo B (sin CLI, p. ej. nube):** el orquestador lanza los subagentes con varias llamadas a Agent en un mismo mensaje.

## Guardarraíles

| Qué | Cómo |
|---|---|
| Un WP solo escribe sus ficheros | Hook `PreToolUse` sobre Write/Edit, contra el manifiesto |
| Sin git, sin dependencias nuevas, sin lanzar otras sesiones de Claude | Hook `PreToolUse` sobre Bash, solo dentro de un WP |
| Sin push ni borrados masivos | `permissions.deny` en `settings.json`, para todos |
| Comandos permitidos mínimos | `allow_bash` del manifiesto (modo A) |
| Comprobación final de propiedad | `snapshot` + `check-wave`: cualquier fichero cambiado que no pertenezca a un WP de la ola hace fallar la ola |
| Manifiesto coherente | `validate`: propietarios únicos, olas y dependencias |

Limitación: un implementador podría escribir con Bash (`echo > fichero`) saltándose el hook de Write. En modo A solo puede ejecutar los comandos de `allow_bash`, y en los dos modos `check-wave` lo detecta al cerrar la ola.

## En otros proyectos

- Proyecto nuevo: "Use this template" en GitHub.
- Proyecto existente: copia `.claude/` y `.gitignore` (añade `.claude/state/`) y haz commit en la rama que vayas a usar (las sesiones de iOS solo ven lo commiteado).
