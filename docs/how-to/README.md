# How-to: desarrollo con agentes (agentic-flow)

> Revisado el 18-10-2026 con Claude Code 2.1.302 y la documentación oficial en [code.claude.com/docs](https://code.claude.com/docs/en/overview).
> Lee esta página primero: tiene lo común a todos los entornos. Luego sigue la guía de tu entorno.

## Elige tu entorno

| Entorno | Guía | Úsalo para | Estado |
|---|---|---|---|
| Terminal (CLI) | [terminal.md](terminal.md) | Control total, scripts, SSH | **Probado**: pasada completa en modo A y en modo B |
| Claude Code Desktop | [desktop.md](desktop.md) | Uso diario con interfaz gráfica | **Parcial**: scripts y agentes probados desde la app; la entrevista de `/architect` en la interfaz, no |
| Visual Studio Code / Cursor | [vscode.md](vscode.md) | Trabajar con los diffs en el editor | Sin probar |
| JetBrains | [jetbrains.md](jetbrains.md) | IntelliJ, PyCharm, WebStorm… | Sin probar |
| Web e iOS (nube) | [web-ios.md](web-ios.md) | Lanzar o seguir trabajo sin tu máquina | Sin probar |
| GitHub Actions | [ci-github-actions.md](ci-github-actions.md) | QA automático en cada pull request | Sin probar |

## Cómo funciona

![El flow de principio a fin](../assets/flow.gif)

La animación se genera con `python3 docs/assets/make_flow_gif.py` (requiere Pillow).

```
 tú ──► /architect ──────────► architecture.md ──► tú lo revisas y apruebas
        último Opus             + wp-manifest
                                     │
                               /implement   (orquestador, último Sonnet)
                                     │
              ┌── ola 1 ─────────────┼──────────────┐   en paralelo
          implementer           implementer     implementer   último Sonnet
            WP-01                 WP-02           WP-03
              └── check-wave 1: ¿cada uno tocó solo lo suyo? ──┘
                                     │
              ┌── ola 2 … (solo lo que necesita código real de la ola 1)
                                     │
                       integración (build + tests completos)
                                     │
                     QA (último Sonnet) ──► qa/report.md
                                     │
              PASS: listo para commit      FAIL: defectos por WP
```

| Pieza | Fichero | Modelo | Hace | No puede |
|---|---|---|---|---|
| Arquitecto | `.claude/commands/architect.md` | Último Opus (`opus`) | Entrevista, diseña y escribe `architecture.md` | Escribir código de producción |
| Orquestador | `.claude/commands/implement.md` | Último Sonnet (`sonnet`) | Valida, lanza olas, verifica e integra | Interpretar la arquitectura o resolver bloqueos |
| Implementador | `.claude/agents/implementer.md` | Último Sonnet (`sonnet`) | Implementa un WP con sus tests | Tocar ficheros ajenos, usar git o instalar dependencias |
| QA | `.claude/agents/qa.md` + `/qa` | Último Sonnet (`sonnet`) | Decide qué probar, escribe tests en `qa/` y los ejecuta | Corregir código de producción |

Los modelos están fijados por alias y no se pueden cambiar: `validate` falla si alguna pieza declara otro. Cada alias apunta al modelo más reciente que conoce tu versión de Claude Code, así que mantén Claude Code actualizado.

### Dos modos de ejecución

- **Modo A (por defecto):** `agentic.py run-wave N` lanza un proceso `claude -p` por WP, todos a la vez. El paralelismo es real y no depende del modelo. Necesita el CLI `claude` en el `PATH`.
- **Modo B:** si no hay CLI, como en la nube, el orquestador lanza subagentes con varias llamadas a Agent en un mismo mensaje. Claude Code admite por defecto hasta 20 subagentes simultáneos por sesión.

`/implement` elige solo. Para forzar un modo: `/implement modo A` o `/implement modo B`.

## Requisitos comunes

1. **Plan:** Pro, Max, Team o Enterprise (o cuenta de Console). El plan gratuito no incluye Claude Code.
2. **CLI de Claude Code instalado** (lo necesita el modo A en todos los entornos). La app de escritorio y la extensión de VS Code traen su propio Claude Code, pero eso no pone `claude` en tu `PATH`. Instalador recomendado (se actualiza solo):

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

4. **Implementación:** `/implement`. Al acabar, ejecuta la integración y QA.
5. **Defectos de QA:**
   - **De implementación:** relanza solo ese WP en modo corrección y vuelve a pasar QA.

     ```bash
     python3 .claude/bin/agentic.py run-wave <ola> <WP> --fix
     ```

   - **De diseño:** vuelve a `/architect` con el informe.
6. **Commit final.** El push lo haces tú, porque está bloqueado para los agentes.

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
python3 .claude/bin/agentic.py run-wave 1              # ola 1 en paralelo (modo A)
python3 .claude/bin/agentic.py run-wave 1 WP-02        # solo un WP
python3 .claude/bin/agentic.py run-wave 1 WP-02 --fix  # corregir sus defectos de QA
python3 .claude/bin/agentic.py run-qa                  # agente QA (modo A)
python3 .claude/bin/agentic.py snapshot 1              # antes de una ola en modo B
python3 .claude/bin/agentic.py check-wave 1            # verificación de propiedad
```

- **Códigos de salida:** `0` si todo está bien, `1` si hay un error de uso o el manifiesto no es válido, `3` si hay que revisar.
- **Informes de cada agente:** `.claude/state/runs/<ID>.json` (campo `result`) y `<ID>.log`.

## Configuración

`.claude/agentic.json`:

```json
{
  "timeout_s": 1800,
  "auth": "subscription"
}
```

- **`timeout_s`:** tiempo máximo de cada etapa. Los agentes que sigan vivos al cumplirse se terminan y quedan como `TIMEOUT`. Para cambiarlo puntualmente: `AGENTIC_TIMEOUT_S`.
- **`auth: "subscription"`:** los agentes usan tu suscripción. En modo `-p`, Claude Code usa `ANTHROPIC_API_KEY` siempre que exista, así que el lanzador quita `ANTHROPIC_API_KEY` y `ANTHROPIC_AUTH_TOKEN` del entorno de los agentes. Usa `"inherit"` solo si quieres facturar contra la API.
- **Modelos:** no se configuran. Están fijados por alias (ver arriba).

## Tests del propio flow

```bash
python3 -m unittest discover -s .claude/bin -p "test_*.py"
```

Son 43 tests de los guardarraíles y del lanzador. Usan un `claude` falso, así que no hacen llamadas reales. En el repo plantilla corren en CI con Python 3.9, 3.12 y 3.14.

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `does not support this model; version X or newer is required` | CLI antiguo para un modelo nuevo | `claude update`. Con npm: `npm install -g @anthropic-ai/claude-code@latest`. Con nvm, usa el npm de nvm, no el del sistema |
| `Ignoring 1 permissions.allow entry ... not been trusted` | La carpeta no es de confianza | Abre `claude` una vez en ella y acepta el aviso |
| `Manifiesto inválido: ... model: sonnet` u `opus` | Alguien fijó otro modelo en un agente o comando | Restaura `model: sonnet` (agentes, `/implement`, `/qa`) o `model: opus` (`/architect`) |
| `RESULTADO: REVISAR` sin `STATUS` | El proceso hijo falló (límite de uso, red, autenticación) | Lee `.claude/state/runs/<ID>.log` |
| `TIMEOUT` | La etapa superó `timeout_s` | Sube `timeout_s` o divide el WP |
| `FUERA DE PROPIEDAD` | Un agente escribió fuera de su zona, o un artefacto de build no está ignorado | Revisa `git diff`. Si es un artefacto (`dist/`…), añádelo a `ignore` en el manifiesto |
| `[agentic guard] ... no posee ...` | El hook hizo su trabajo | Si ese fichero debía ser del WP, corrige el manifiesto con `/architect` |
| Todas las olas tienen un solo WP | El arquitecto eligió capas reales | Pídele "contratos primero" |
| Un WP relanzado devuelve `BLOCKER` hablando de defectos que no son suyos | Usaste `--fix` con un informe de QA viejo | Relánzalo sin `--fix`, o ejecuta `run-qa` antes |
| Las olas van en serie en el modo B | El orquestador no agrupó las llamadas a Agent | Usa el modo A, o pídeselo de nuevo explícitamente |

## Referencias oficiales

- [Instalación y actualización](https://code.claude.com/docs/en/setup)
- [Autenticación y precedencia de credenciales](https://code.claude.com/docs/en/authentication)
- [Subagentes](https://code.claude.com/docs/en/sub-agents)
- [Comandos y skills](https://code.claude.com/docs/en/slash-commands)
- [Hooks](https://code.claude.com/docs/en/hooks)
- [Buenas prácticas de Claude Code](https://code.claude.com/docs/en/best-practices)
