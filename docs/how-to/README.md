# How-to: desarrollo con agentes (agentic-flow)

> Revisado el 18-10-2026 con Claude Code 2.1.302 y la documentación oficial en [code.claude.com/docs](https://code.claude.com/docs/en/overview).
> Lee esta página primero: tiene lo común a todos los entornos. Luego sigue la guía de tu entorno.
> Para los esquemas técnicos (secuencia, ciclo de vida, decisión del hook y permisos), consulta [Cómo funciona](../how-it-works.md).

## Elige tu entorno

| Entorno | Guía | Úsalo para | Estado |
|---|---|---|---|
| Terminal (CLI) | [terminal.md](terminal.md) | Control total, scripts, SSH | **Probado**: `/implement` completo con el workflow nativo (ola 0, 2 olas en paralelo, verificación, revisión, QA); el modo A, también de principio a fin |
| Claude Code Desktop | [desktop.md](desktop.md) | Uso diario con interfaz gráfica | **Parcial**: scripts y agentes probados desde la app; la entrevista de `/architect` en la interfaz, no |
| Visual Studio Code / Cursor | [vscode.md](vscode.md) | Trabajar con los diffs en el editor | Sin probar |
| JetBrains | [jetbrains.md](jetbrains.md) | IntelliJ, PyCharm, WebStorm… | Sin probar |
| Web e iOS (nube) | [web-ios.md](web-ios.md) | Lanzar o seguir trabajo sin tu máquina | Sin probar |
| GitHub Actions | [ci-github-actions.md](ci-github-actions.md) | QA automático en cada pull request | Sin probar |

## Cómo funciona

![El flow de principio a fin](../assets/flow.gif)

La animación se genera con `python3 docs/assets/make_flow_gif.py` (requiere Pillow).

```
 tú ──► /architect (último Opus)
          0 clasifica: feature · change · fix · refactor · tamaño
          1 investiga y reutiliza · lee decisiones previas
          2 entrevista ──► architecture.md (contratos + AC-NNN + manifiesto)
          3 plan-reviewer (último Opus, contexto limpio) ──► corrige
          4 tú apruebas ──► se archiva en docs/architecture/
                                     │
       /implement (orquestador, último Sonnet, no bloquea la sesión)
                                     │
   ola 0   test-author ──► acceptance/  ──► acceptance --expect red   (el juez, antes del código)
                                     │
   ola 1   implementer  implementer  implementer      en paralelo, solo sus ficheros
   ola 2   implementer …                              (no pueden tocar acceptance/)
                                     │
   verificación: build · tipos · lint · tests · acceptance --expect green · diff
                                     │
   revisión   reviewer (solo lectura, filtro de confianza)
   QA         qa (exploratorio, más allá de los AC)
                                     │
   defectos ──► run-wave N WP --fix  (máximo 2 ciclos por WP; después decides tú)
                                     │
   tú apruebas el commit
```

| Pieza | Fichero | Modelo | Hace | No puede |
|---|---|---|---|---|
| Arquitecto | `.claude/commands/architect.md` | Último Opus | Clasifica, investiga, entrevista y escribe `architecture.md` con criterios AC-NNN | Escribir código o tests |
| Revisor del plan | `.claude/agents/plan-reviewer.md` | Último Opus | Critica `architecture.md` en contexto limpio antes de tu aprobación | Escribir nada |
| Orquestador | `.claude/commands/implement.md` | Último Sonnet | Lanza etapas, verifica por fases y gestiona correcciones | Interpretar la arquitectura o resolver bloqueos |
| Test-author | `.claude/agents/test-author.md` | Último Sonnet | Escribe los tests de aceptación desde los AC, antes del código | Implementar |
| Implementer | `.claude/agents/implementer.md` | Último Sonnet | Implementa un WP con sus tests unitarios | Tocar ficheros ajenos o los tests de aceptación |
| Revisor | `.claude/agents/reviewer.md` | Último Sonnet | Revisa calidad y seguridad con filtro de confianza | Escribir nada |
| QA | `.claude/agents/qa.md` | Último Sonnet | Pruebas exploratorias en `qa/`, como etapa de `/implement` | Corregir código de producción |

### Por qué este orden

- **Tests primero, escritos por otro.** El agente que escribe el código no escribe el examen. El test-author redacta los tests de aceptación antes de que exista el código, comprueba que fallan y el hook impide que nadie más los toque. Así un implementer no puede "pasar" rebajando el test.
- **El plan también se revisa.** Quien escribe un plan tiende a darlo por bueno. Un segundo Opus que no ha visto la conversación lo lee como lo leerán los implementers.
- **Ceremonia según el tamaño.** Un cambio trivial no pasa por el flow. Un fix empieza con un test que reproduce el bug. Un refactor exige la suite en verde antes y después.
- **El humano decide qué está bien; la máquina mide.** Tienes dos puertas: aprobar el diseño y aprobar el commit. Los bucles de corrección tienen tope.

Ideas tomadas y adaptadas de [ECC](https://github.com/affaan-m/ECC) (MIT): juez independiente, tamaño según el riesgo, revisión con filtro de confianza, fases de verificación y defensa ante instrucciones inyectadas.

Los modelos están fijados por alias y no se pueden cambiar: `validate` falla si alguna pieza declara otro. Cada alias apunta al modelo más reciente que conoce tu versión de Claude Code, así que mantén Claude Code actualizado.

### Dos modos de ejecución

- **Workflow nativo (por defecto):** `/implement` lanza el workflow `agentic-implement` (`.claude/workflows/`). Es un script de Claude Code que orquesta todo el pipeline de forma determinista y en segundo plano: agentes en paralelo, informes validados por esquema y revisión con verificación adversarial. Lo sigues con `/workflows`. En Pro hay que activar **Dynamic workflows** en `/config`; la plantilla ya trae `"enableWorkflows": true` en `.claude/settings.json`.
- **Modo A (respaldo):** si los workflows no están disponibles, `/implement` usa los comandos `agentic.py run-*`, que lanzan un proceso `claude -p` por WP. Necesita el CLI `claude` en el `PATH`.

`/implement` elige solo. Para forzar el respaldo: `/implement modo A`. Los esquemas de ambas vías están en [Cómo funciona § 6](../how-it-works.md#6-workflow-nativo-y-modo-a).

## Requisitos comunes

1. **Plan:** Pro, Max, Team o Enterprise (o cuenta de Console). El plan gratuito no incluye Claude Code.
2. **CLI de Claude Code instalado.** Lo necesita el modo A; con el workflow nativo es recomendable, pero no obligatorio. La app de escritorio y la extensión de VS Code traen su propio Claude Code, pero eso no pone `claude` en tu `PATH`. Instalador recomendado (se actualiza solo):

   ```bash
   curl -fsSL https://claude.ai/install.sh | bash
   ```

3. **`git` y `python3` 3.9 o posterior.**
4. **macOS, Linux o WSL 2.** Claude Code funciona en Windows nativo, pero `agentic.py` usa `fcntl`, que solo existe en POSIX. En Windows trabaja dentro de WSL.

Comprueba el entorno:

```bash
claude --version
```

```bash
claude doctor
```

```bash
claude auth status
```

```bash
python3 --version
```

Resultado esperado: una versión de Claude Code, `claude doctor` sin errores, `"authMethod": "claude.ai"` con tu `subscriptionType`, y Python 3.9 o posterior.

## Instalar el flow en un proyecto

**Proyecto nuevo**, a partir de la plantilla:

```bash
gh repo create mi-proyecto --template jagosar/agentic-flow --private --clone
```

**Proyecto existente:**

```bash
git clone --depth 1 https://github.com/jagosar/agentic-flow /tmp/agentic-flow
```

```bash
cp -r /tmp/agentic-flow/.claude . && cat /tmp/agentic-flow/.gitignore >> .gitignore
```

```bash
git add .claude .gitignore && git commit -m "Add agentic flow"
```

Después, abre `claude` una vez en la carpeta y **acepta el aviso de confianza**. Sin eso, Claude Code ignora el `permissions.allow` del proyecto. Los hooks y los `deny` se aplican igual.

Comprobación:

```bash
python3 .claude/bin/agentic.py validate
```

Resultado esperado: `No existe .../architecture.md. Lanza /architect primero.`, que es lo correcto en un proyecto sin arquitectura. Cualquier mensaje sobre `model:` indica que alguna definición se ha modificado.

## Ciclo de trabajo

1. **Diseño:** `/architect <petición>`. Incluye el objetivo, el alcance y las restricciones que ya conozcas. La entrevista afina el resto.
2. **Revisión:** lee `architecture.md`, sobre todo la sección 6 (contratos) y la 8 (work packages y olas). Si todas las olas tienen un solo WP, pide "contratos primero" para tener paralelismo.
3. **Commit del diseño:**

   ```bash
   git add architecture.md && git commit -m "Architecture: <tema>"
   ```

4. **Implementación:** `/implement`. Ejecuta la ola 0 (tests de aceptación), las olas, la verificación por fases, la revisión y QA.
5. **Defectos de QA:**
   - **De implementación:** relanza solo ese WP en modo corrección. Hay un máximo de 2 ciclos por WP; al tercero, el script se niega y decides tú.

     ```bash
     python3 .claude/bin/agentic.py run-wave <ola> <WP> --fix
     ```

   - **De diseño:** vuelve a `/architect` con el informe.
6. **Commit y push.** Hazlos tú o pídeselos a la sesión principal. Los agentes del flow no pueden: el hook se lo bloquea.

## Buenas prácticas

- **Un `CLAUDE.md` en la raíz** con las convenciones del repo (estilo, comandos de test, prohibiciones). Todos los agentes lo leen, así que deja de ser necesario repetirlo en cada `architecture.md`.
- **Contratos exactos.** El paralelismo depende de la sección 6. Un contrato vago no falla en la ola: falla en la integración.
- **Una feature por sesión**, cada una en su rama o worktree, con su propio `architecture.md`.
- **No edites a mano los ficheros de un WP mientras corre su ola:** `check-wave` lo marcaría como violación.
- **Commit después de cada ola en OK** si el trabajo es largo, para tener un punto al que volver.
- **En Pro, vigila `/usage`.** Varios agentes en paralelo gastan deprisa los límites del plan. Si llegas al límite a mitad de una ola, relanza solo los WP que fallaron (`run-wave N WP-…`) cuando se renueve.

## Referencia del script

```bash
python3 .claude/bin/agentic.py validate                # manifiesto y modelos coherentes
python3 .claude/bin/agentic.py sync-permissions        # permisos de los agentes en settings.local.json
python3 .claude/bin/agentic.py pipeline-plan           # el plan que sigue el workflow (JSON)
python3 .claude/bin/agentic.py verify                  # build, tipos, lint, tests y aceptación (JSON)
# Modo A (respaldo), etapa por etapa:
python3 .claude/bin/agentic.py run-acceptance         # ola 0: test-author escribe la aceptación
python3 .claude/bin/agentic.py acceptance --expect red # debe fallar antes del código
python3 .claude/bin/agentic.py run-wave 1              # ola 1 en paralelo (modo A)
python3 .claude/bin/agentic.py run-wave 1 WP-02        # solo un WP
python3 .claude/bin/agentic.py run-wave 1 WP-02 --fix  # corregir sus defectos de QA
python3 .claude/bin/agentic.py acceptance --expect green  # debe pasar después
python3 .claude/bin/agentic.py run-review              # revisor de código (solo lectura)
python3 .claude/bin/agentic.py run-qa                  # agente QA (modo A)
python3 .claude/bin/agentic.py check-wave 1            # verificación de propiedad
python3 .claude/bin/agentic.py status                  # ledger: estado de cada agente y etapa
python3 .claude/bin/agentic.py stop                    # parar todos los agentes en marcha
python3 .claude/bin/agentic.py stop WP-02              # parar uno
python3 .claude/bin/agentic.py mark WP-02 blocker nota # anotar a mano
```

- **Códigos de salida:** `0` si todo está bien, `1` si hay un error de uso o el manifiesto no es válido, `3` si hay que revisar y `4` si se agotó el tope de ciclos `--fix`.
- **Informes de cada agente:** `.claude/state/runs/<ID>.json` (campo `result`) y `<ID>.log`.

## Seguir y parar el trabajo

- **La sesión no se bloquea.** Las olas y QA corren en segundo plano, así que puedes seguir hablando con la sesión mientras trabajan.
- **"¿Cómo va?"** El orquestador responde desde el **ledger**, `.claude/state/ledger.md`. Lo escribe `agentic.py`, no el modelo, así que no se pierde aunque la conversación se compacte. Ejemplo:

  ```
  ## Etapas
  - ola 1: OK (20:48)

  ## Agentes
  - [done]    WP-01 (sonnet) — etapa 1 — modo A — inicio 20:48 — DONE
  - [blocker] WP-03 (sonnet) — etapa 2 — modo workflow — inicio 20:48 — BLOCKER
  ```

- **"Para".** Con el workflow nativo, desde `/workflows`: selecciona el run y pulsa `x`. Con `p` lo pausas y reanudas; un run parado se puede relanzar y reutiliza lo ya terminado. En el modo A, `agentic.py stop` mata los procesos y la etapa queda en `REVISAR` con `STOPPED`.
- **Informes cortos.** Implementers y QA responden en menos de 300 palabras, con el resultado primero. El resultado completo de cada ejecución del workflow se guarda en `.claude/state/runs/workflow-result.json`.

## Configuración

`.claude/agentic.json`:

```json
{
  "timeout_s": 1800,
  "auth": "subscription",
  "max_fix_cycles": 2
}
```

- **`timeout_s`:** tiempo máximo de cada etapa. Los agentes que sigan vivos al cumplirse se terminan y quedan como `TIMEOUT`. Para cambiarlo puntualmente: `AGENTIC_TIMEOUT_S`.
- **`auth: "subscription"`:** los agentes usan tu suscripción. En modo `-p`, Claude Code usa `ANTHROPIC_API_KEY` siempre que exista, así que el lanzador quita `ANTHROPIC_API_KEY` y `ANTHROPIC_AUTH_TOKEN` del entorno de los agentes. Usa `"inherit"` solo si quieres facturar contra la API.
- **`max_fix_cycles`:** ciclos `--fix` permitidos por WP antes de escalar a una persona.
- **Modelos:** no se configuran. Están fijados por alias (ver arriba).

## Tests del propio flow

```bash
python3 -m unittest discover -s .claude/bin -p "test_*.py"
```

Son 71 tests de los guardarraíles, los comandos del pipeline, el lanzador y el ledger, más 11 escenarios de la lógica del workflow con agentes simulados (`node .claude/bin/test_workflow.mjs`). Usan un `claude` falso, así que no hacen llamadas reales. En el repo plantilla corren en CI con Python 3.9, 3.12 y 3.14.

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `does not support this model; version X or newer is required` | CLI antiguo para un modelo nuevo | `claude update`. Con npm: `npm install -g @anthropic-ai/claude-code@latest`. Con nvm, usa el npm de nvm, no el del sistema |
| `Ignoring 1 permissions.allow entry ... not been trusted` | La carpeta no es de confianza | Abre `claude` una vez en ella y acepta el aviso |
| `Manifiesto inválido: ... model: sonnet` u `opus` | Alguien fijó otro modelo en un agente o comando | Restaura `model: sonnet` (agentes de ejecución y `/implement`) o `model: opus` (`/architect` y `plan-reviewer`) |
| `RESULTADO: REVISAR` sin `STATUS` | El proceso hijo falló (límite de uso, red, autenticación) | Lee `.claude/state/runs/<ID>.log` |
| `TIMEOUT` | La etapa superó `timeout_s` | Sube `timeout_s` o divide el WP |
| `FUERA DE PROPIEDAD` | Un agente escribió fuera de su zona, o un artefacto de build no está ignorado | Revisa `git diff`. Si es un artefacto (`dist/`…), añádelo a `ignore` en el manifiesto |
| `[agentic guard] ... no posee ...` | El hook hizo su trabajo | Si ese fichero debía ser del WP, corrige el manifiesto con `/architect` |
| `YA PASAN SIN CÓDIGO` en la ola 0 | Los tests de aceptación no prueban nada | Revisa los AC con `/architect`: les falta un resultado observable concreto |
| `agotó sus 2 ciclos --fix` | El defecto no se arregla insistiendo | Decide tú, o cambia el contrato o el AC con `/architect` |
| `... es configuración de calidad ya existente` | Un agente intentó relajar un linter o formatter | Es lo correcto. Si el diseño de verdad exige cambiarla, añade `"config_edit": true` a ese WP con `/architect` |
| `no se desactivan tests para ponerlos en verde` | Un agente intentó añadir `skip`, `xfail` u `only` | El test se arregla o se reporta como `BLOCKER`. Los saltos condicionales (`skipIf`) sí se permiten |
| `... parece una clave ...` | Un agente iba a escribir algo con forma de credencial | Usa variables de entorno o valores sintéticos. Si es un falso positivo en un fixture, cambia el valor de ejemplo |
| `saltarse los hooks de git ... no está permitido` | `--no-verify`, `commit -n` o `core.hooksPath` | Arregla lo que hace fallar el hook de git, o hazlo tú a mano si de verdad hace falta |
| Todas las olas tienen un solo WP | El arquitecto eligió capas reales | Pídele "contratos primero" |
| Un WP relanzado devuelve `BLOCKER` hablando de defectos que no son suyos | Usaste `--fix` con un informe de QA viejo | Relánzalo sin `--fix`, o ejecuta `run-qa` antes |
| `/implement` usa el modo A aunque tienes Pro | Los workflows no están activados | Actívalos en `/config` (Dynamic workflows) o con `"enableWorkflows": true` |
| El workflow se para pidiendo permiso para un comando | Faltan reglas en `settings.local.json` | Ejecuta `agentic.py sync-permissions`, o elige "permitir siempre" la primera vez |

## Referencias oficiales

- [Instalación y actualización](https://code.claude.com/docs/en/setup)
- [Autenticación y precedencia de credenciales](https://code.claude.com/docs/en/authentication)
- [Subagentes](https://code.claude.com/docs/en/sub-agents)
- [Comandos y skills](https://code.claude.com/docs/en/slash-commands)
- [Hooks](https://code.claude.com/docs/en/hooks)
- [Buenas prácticas de Claude Code](https://code.claude.com/docs/en/best-practices)
