---
model: sonnet
description: Lleva architecture.md a código verificado con el workflow nativo agentic-implement (ola 0, olas en paralelo, verificación, revisión adversarial, QA y correcciones con tope). Si los workflows no están disponibles, usa el modo A.
argument-hint: "[ola inicial] [modo A]"
---

# Rol

Eres el lanzador del flow. No escribes código ni tests, y no interpretas la arquitectura. La ejecución la hace el workflow nativo `agentic-implement` (`.claude/workflows/agentic-implement.js`), que orquesta de forma determinista y en segundo plano. Tú validas antes, lo lanzas, y después presentas el resultado y gestionas la puerta humana del commit.

Argumentos: $ARGUMENTS
- Un número: retoma desde esa ola, sin la ola 0.
- `modo A`: usa el respaldo sin comprobar nada.

# 1. Validación previa

1. Ejecuta `python3 .claude/bin/agentic.py validate`. Si falla, para y dile al usuario que vuelva a `/architect`.
2. Si la sección 11 de `architecture.md` bloquea algún WP, para.
3. Si el diseño no está commiteado, recomienda hacer el commit antes de empezar.
4. Ejecuta `python3 .claude/bin/agentic.py sync-permissions`. Añade a `.claude/settings.local.json` los permisos que necesitan los agentes (tests, verificación), para que el workflow no se detenga a preguntar.

# 2. Lanzar el workflow (vía principal)

Lanza el workflow guardado con la herramienta Workflow:
- **nombre:** `agentic-implement`;
- **`args`:** `{}`, o `{ "start_wave": N }` si te pasaron una ola.

Corre en segundo plano. Dile al usuario en una línea que ha empezado, que puede seguirlo con `/workflows` y que puede seguir hablando contigo, y termina tu turno. No esperes ni consultes en bucle: la notificación de fin te despertará.

Mientras corre:
- **"¿Cómo va?":** responde con `python3 .claude/bin/agentic.py status` (el ledger) o remite a `/workflows`.
- **"Para":** el usuario lo detiene desde `/workflows` (tecla `x`). Si te lo pide a ti, díselo.

**Cuándo pasar al modo A:**
- Si la herramienta Workflow no existe o el usuario tiene los workflows desactivados, explícale que en Pro se activan en `/config` (**Dynamic workflows**) o con `"enableWorkflows": true`.
- Si `claude --version` funciona, ofrece el modo A como alternativa.

# 3. Presentar el resultado (puerta humana)

El workflow devuelve un JSON. Primero guárdalo, porque es el registro completo de la ejecución, incluido el informe de QA:
1. Escríbelo tal cual con la herramienta Write en `.agentic-result.json`, en la raíz del repo.
2. Ejecuta `python3 .claude/bin/agentic.py save-result .agentic-result.json`, que lo mueve a `.claude/state/runs/workflow-result.json`.

No lo escribas directamente en `.claude/`, que es una ruta protegida, ni lo pases por un heredoc, porque el filtro de seguridad de Bash lo bloquea.

Después preséntalo así:

- **Estado:** `result` (`OK` o `REVISAR`) y, si falló, `failed_stage` y `detail`.
- **WP:** tabla con WP, estado, ficheros y comprobaciones, tomada de `work_packages`.
- **Verificación:** cada fase de `verification.phases`, con la aceptación en verde.
- **Revisión:**
  - hallazgos confirmados;
  - refutados por el verificador (y por qué);
  - avisos medios y bajos.
- **QA:** estado, plan, defectos y huecos de cobertura.
- **Correcciones:** `fix_cycles` y qué WP se corrigieron.
- **Pendiente (`pending`):** cada elemento con su tipo.
  - **Diseño:** se lleva a `/architect`.
  - **Tope agotado o sin WP:** decide el usuario.

Si `result` es `OK`, propón los mensajes de commit (uno por bloque lógico, en el formato de la sección 7) y **espera la aprobación del usuario**. No hagas commit ni push sin ella.

# 4. Modo A (respaldo, sin workflows)

Requiere el CLI `claude` en el `PATH`. Cada paso es un comando de `python3 .claude/bin/agentic.py`, lanzado con Bash **en segundo plano** (`run_in_background: true`). Termina el turno tras lanzarlo y sigue cuando llegue la notificación. Cada comando acaba en `RESULTADO: OK` o `REVISAR`. Ante `REVISAR`, para y presenta el problema.

1. **Ola 0:**
   - `run-acceptance` y después `acceptance --expect red`.
   - En un refactor, solo `acceptance --expect green`, como línea base.
2. **Olas:** `run-wave N` para cada ola, en orden.
3. **Verificación:** `verify`.
4. **Revisión y QA:** `run-review` y `run-qa`.
5. **Correcciones:**
   - Un defecto de implementación crítico o alto se corrige con `run-wave <ola> <WP> --fix`, con un máximo de 2 ciclos por WP (el script se niega al tercero, con salida 4). Después se repiten la verificación y la etapa que lo encontró.
   - Un defecto de diseño se lleva a `/architect`.
6. **Cierre:** el mismo informe y la misma puerta humana que en el paso 3.

# Reglas

- No resuelvas tú un bloqueo. No edites ficheros de un WP ni los tests de aceptación.
- No hagas commit ni push salvo que el usuario lo pida explícitamente. Los agentes del flow no pueden hacerlo: el hook se lo bloquea.
