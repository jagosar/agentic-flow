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
          Opus 5.5        + wp-manifest
                                │
                           /implement
                                │
              ┌── ola 1 ────────┼────────────┐   en paralelo
          implementer      implementer   implementer   Sonnet 5.5
            WP-01            WP-02          WP-03
              └── check-wave 1: ¿cada uno tocó solo lo suyo? ──┘
                                │
              ┌── ola 2 ... (depende de la ola 1)
                                │
                     integración (build + tests)
                                │
                             /qa  ──► qa/report.md   Opus 5.5
                                │
            PASS: listo para commit   FAIL: defectos por WP
```

## Los agentes

| Agente | Fichero | Modelo | Qué hace | Qué no puede hacer |
|---|---|---|---|---|
| Arquitecto | `.claude/commands/architect.md` | Opus 5.5 | Entrevista, diseña y escribe `architecture.md` | Escribir código de producción |
| Orquestador | `.claude/commands/implement.md` | El de la sesión | Valida, lanza las olas, verifica e integra | Interpretar la arquitectura o resolver bloqueos |
| Implementador | `.claude/agents/implementer.md` | Sonnet 5.5 | Implementa un WP con sus tests unitarios | Tocar ficheros de otro WP, git, dependencias |
| QA | `.claude/agents/qa.md` | Opus 5.5 | Decide qué probar (contratos, integración, límites…), escribe esos tests en `qa/` y los ejecuta | Corregir código de producción |

## Requisitos (todos los entornos)

- `git` y `python3` (3.9 o posterior).
- Claude Code **2.1.280 o posterior** para Opus 5.5. Con versiones anteriores, el lanzador falla con `does not support this model`. Actualiza con `claude update`.
- El repo con `.claude/` y `.gitignore` de esta plantilla, commiteados.
- **Para el modo paralelo A**: el CLI `claude` en el `PATH` y con sesión iniciada. Compruébalo con `claude --version` en una terminal normal. Si no está, `/implement` usa el modo B (subagentes dentro de la sesión).

## Ciclo de trabajo

1. **Diseño:** `/architect Quiero una API REST de reservas con...`. Responde a las rondas de preguntas.
2. **Revisión:** lee `architecture.md`. Mira sobre todo la sección 6 (contratos) y la 8 (work packages). Si algo no te encaja, díselo al arquitecto en la misma sesión.
3. **Commit del diseño** (recomendado): `git add architecture.md && git commit -m "Architecture: ..."`. Así cada ola parte de un punto limpio.
4. **Implementación:** `/implement`. Al acabar lanza QA solo.
5. **Defectos:**
   - **De implementación:** relanza solo ese WP con `python3 .claude/bin/agentic.py run-wave <ola> WP-02` y después `/qa`.
   - **De diseño:** vuelve a `/architect` con el informe de QA.
6. **Commit final:** tú, o pídeselo a Claude. El push está bloqueado para los agentes y lo haces tú.

## Comandos del script

```bash
python3 .claude/bin/agentic.py validate          # manifiesto coherente
python3 .claude/bin/agentic.py run-wave 1        # ola 1 en paralelo
python3 .claude/bin/agentic.py run-wave 1 WP-02  # solo un WP
python3 .claude/bin/agentic.py run-qa            # agente QA
python3 .claude/bin/agentic.py check-wave 1      # verificación de propiedad
```

Informes de cada agente: `.claude/state/runs/<ID>.json` (campo `result`) y `<ID>.log`.

Variables para cambiar de modelo sin editar ficheros: `AGENTIC_IMPLEMENTER_MODEL` y `AGENTIC_QA_MODEL`.

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `does not support this model; version 2.1.280 or newer is required` | CLI antiguo | `claude update` |
| Aviso `isn't described by this version's model catalog` | CLI sin el modelo en su catálogo | Funciona igual; actualiza para quitar el aviso |
| `RESULTADO: REVISAR` sin `STATUS` | El proceso hijo falló | Lee `.claude/state/runs/<ID>.log` |
| `FUERA DE PROPIEDAD` | Un agente escribió fuera de su zona, normalmente por Bash | Revisa `git diff` de ese fichero y deshazlo o asígnalo en el manifiesto |
| `[agentic guard] ... no posee ...` | El hook hizo su trabajo | Si el fichero debía ser de ese WP, corrige el manifiesto con `/architect` |
| Un subagente no puede escribir: "ejecuta claim" | Modo B y el agente no se registró | Debería ocurrir solo una vez; el agente se registra y continúa |
| `Manifiesto inválido` | Solapes, dependencias de la misma ola, rutas raras | Vuelve a `/architect` con el error |
| Las olas van una detrás de otra en el modo B | El orquestador no agrupó las llamadas | Usa el modo A (CLI en el `PATH`) |
