# How-to: desarrollo con agentes

Guía común. Lee esta primero y luego la de tu entorno.

| Entorno | Guía | Cuándo usarlo |
|---|---|---|
| Claude Code Desktop | [desktop.md](desktop.md) | Uso diario. Es el más cómodo para la entrevista del arquitecto. |
| Visual Studio Code | [vscode.md](vscode.md) | Si ya programas en VS Code y quieres ver los diffs en el editor. |
| Terminal (CLI) | [terminal.md](terminal.md) | Control total, scripts, servidores remotos por SSH. |
| JetBrains (IntelliJ, PyCharm, WebStorm…) | [jetbrains.md](jetbrains.md) | Si tu IDE es JetBrains. |
| Web e iOS | [web-ios.md](web-ios.md) | Lanzar o revisar trabajo desde el móvil, sin tu máquina. |
| GitHub Actions (CI) | [ci-github-actions.md](ci-github-actions.md) | QA automático en cada pull request. |

## El flow en una imagen

```
 tú ──► /architect ──► architecture.md ──► (tú apruebas)
        último Opus       + wp-manifest
                                │
                           /implement
                                │
              ┌── ola 1 ────────┼────────────┐   en paralelo
          implementer      implementer   implementer   último Sonnet
            WP-01            WP-02          WP-03
              └── check-wave 1: ¿cada uno tocó solo lo suyo? ──┘
                                │
              ┌── ola 2 ... (depende de la ola 1)
                                │
                     integración (build + tests)
                                │
                             /qa  ──► qa/report.md   último Sonnet
                                │
            PASS: listo para commit   FAIL: defectos por WP
```

## Los agentes

| Agente | Fichero | Modelo | Qué hace | Qué no puede hacer |
|---|---|---|---|---|
| Arquitecto | `.claude/commands/architect.md` | Último Opus (`opus`) | Entrevista, diseña y escribe `architecture.md` | Escribir código de producción |
| Orquestador | `.claude/commands/implement.md` | El de la sesión | Valida, lanza las olas, verifica e integra | Interpretar la arquitectura o resolver bloqueos |
| Implementador | `.claude/agents/implementer.md` | Último Sonnet (`sonnet`) | Implementa un WP con sus tests unitarios | Tocar ficheros de otro WP, git, dependencias |
| QA | `.claude/agents/qa.md` | Último Sonnet (`sonnet`) | Decide qué probar (contratos, integración, límites…), escribe esos tests en `qa/` y los ejecuta | Corregir código de producción |

## Requisitos (todos los entornos)

- `git` y `python3` (3.9 o posterior).
- Claude Code **actualizado** (`claude update`). Los alias `opus` y `sonnet` apuntan a los modelos más recientes que conoce tu versión, y con una versión antigua un modelo nuevo puede fallar con `does not support this model`.
- El repo con `.claude/` y `.gitignore` de esta plantilla, commiteados.
- La carpeta del proyecto marcada como de confianza: abre `claude` una vez en ella y acepta el aviso.
- macOS o Linux. En Windows usa WSL, porque el script depende de `fcntl` y del comando `python3`.
- **Para el modo paralelo A**: el CLI `claude` en el `PATH` y con sesión iniciada. Compruébalo con `claude --version` en una terminal normal. Si no está, `/implement` usa el modo B (subagentes dentro de la sesión).

## Ciclo de trabajo

1. **Diseño:** `/architect Quiero una API REST de reservas con...`. Responde a las rondas de preguntas.
2. **Revisión:** lee `architecture.md`. Mira sobre todo la sección 6 (contratos) y la 8 (work packages). Si algo no te encaja, díselo al arquitecto en la misma sesión.
3. **Commit del diseño** (recomendado): `git add architecture.md && git commit -m "Architecture: ..."`. Así cada ola parte de un punto limpio.
4. **Implementación:** `/implement`. Al acabar lanza QA solo.
5. **Defectos:**
   - **De implementación:** relanza solo ese WP en modo corrección con `python3 .claude/bin/agentic.py run-wave <ola> WP-02 --fix` y después `/qa`.
   - **De diseño:** vuelve a `/architect` con el informe de QA.
6. **Commit final:** tú, o pídeselo a Claude. El push está bloqueado para los agentes y lo haces tú.

## Comandos del script

```bash
python3 .claude/bin/agentic.py validate          # manifiesto coherente
python3 .claude/bin/agentic.py run-wave 1        # ola 1 en paralelo
python3 .claude/bin/agentic.py run-wave 1 WP-02  # solo un WP
python3 .claude/bin/agentic.py run-wave 1 WP-02 --fix  # corregir sus defectos de QA
python3 .claude/bin/agentic.py run-qa            # agente QA
python3 .claude/bin/agentic.py check-wave 1      # verificación de propiedad
```

Informes de cada agente: `.claude/state/runs/<ID>.json` (campo `result`) y `<ID>.log`.

## Modelos, tiempo y suscripción

`.claude/agentic.json` fija lo que usa el lanzador (modos A y QA):

```json
{
  "timeout_s": 1800,
  "auth": "subscription"
}
```

- `auth: "subscription"` (por defecto): los agentes usan tu sesión de Claude, es decir, tu suscripción. El lanzador les quita `ANTHROPIC_API_KEY` y `ANTHROPIC_AUTH_TOKEN` aunque estén en tu entorno, para que no consuman créditos de API sin que te des cuenta. Usa `"inherit"` solo si quieres que los agentes usen la API key (por ejemplo, en CI).
- `timeout_s`: tiempo máximo de cada etapa. Al cumplirse, los agentes que sigan vivos se terminan y quedan como `TIMEOUT`. Es el freno si un agente se atasca.
- Para cambiar el timeout puntualmente sin tocar el fichero: `AGENTIC_TIMEOUT_S`.
- **Modelos:** los implementadores y QA usan siempre el último Sonnet (alias `sonnet`), tanto en el modo A (`--model sonnet`) como en el B (`model: sonnet` en `.claude/agents/*.md`). No se puede cambiar por config ni por entorno, y `validate` rechaza cualquier agente orquestado que declare otro modelo, incluidos los agentes especializados del campo `agent`. El alias apunta al Sonnet más reciente que conoce tu versión de Claude Code: actualízala (`claude update`) para recibir los nuevos. El arquitecto usa siempre el último Opus (`model: opus` en `.claude/commands/architect.md`), y `validate` también lo comprueba.

**Consumo de la suscripción:** cada agente cuenta contra los límites de uso de tu plan, y en paralelo los gastan más deprisa. Ten en cuenta que:

- El arquitecto (Opus) consume más que los agentes orquestados (Sonnet).
- El modo B consume más que el A, porque los informes de los subagentes pasan por el contexto del orquestador.
- Si llegas al límite, los agentes que estén en marcha fallan y la etapa queda en `REVISAR`. Relanza esos WP con `run-wave N WP-…` cuando se renueve el límite.

## Tests del propio flow

```bash
python3 -m unittest discover -s .claude/bin -p "test_*.py"
```

Son 42 tests de los guardarraíles y del lanzador. Usan un `claude` falso, así que no hacen llamadas reales. En el repo plantilla corren en CI.

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `does not support this model; version 2.1.280 or newer is required` | CLI antiguo | `claude update`. Si da un error de permisos y usas nvm, puede que la shell esté usando el npm del sistema: `$(dirname $(which node))/npm install -g @anthropic-ai/claude-code@latest` |
| `Ignoring 1 permissions.allow entry ... this workspace has not been trusted` | La carpeta del proyecto aún no es de confianza para Claude Code | Abre `claude` una vez en esa carpeta y acepta el aviso. Los hooks y los `deny` se aplican igual; lo que se pierde es el `allow` que evita las preguntas |
| Todas las olas tienen un solo WP | El arquitecto eligió "capas reales" | Pídele "contratos primero" en la entrevista, o explícale que quieres más paralelismo |
| Aviso `isn't described by this version's model catalog` | CLI sin el modelo en su catálogo | Funciona igual; actualiza para quitar el aviso |
| `RESULTADO: REVISAR` sin `STATUS` | El proceso hijo falló | Lee `.claude/state/runs/<ID>.log` |
| `FUERA DE PROPIEDAD` | Un agente escribió fuera de su zona, normalmente por Bash | Revisa `git diff` de ese fichero y deshazlo o asígnalo en el manifiesto |
| `[agentic guard] ... no posee ...` | El hook hizo su trabajo | Si el fichero debía ser de ese WP, corrige el manifiesto con `/architect` |
| Un subagente no puede escribir: "ejecuta claim" | Modo B y el agente no se registró | Debería ocurrir solo una vez; el agente se registra y continúa |
| `Manifiesto inválido` | Solapes, dependencias de la misma ola, rutas raras | Vuelve a `/architect` con el error |
| Las olas van una detrás de otra en el modo B | El orquestador no agrupó las llamadas | Usa el modo A (CLI en el `PATH`) |
