# agentic-flow

Un equipo de agentes para Claude Code que lleva una idea a código probado:

1. **Diseño:** un arquitecto (último Opus) escribe un contrato verificable y otro Opus lo revisa en contexto limpio.
2. **Ola 0:** un test-author escribe los tests de aceptación antes del código.
3. **Implementación:** varios implementers trabajan en paralelo para ponerlos en verde, cada uno en sus propios ficheros.
4. **Revisión y QA:** un revisor mira la calidad y QA explora lo que nadie previó.
5. **Documentación viva:** con el código aceptado, el mapa del código se regenera solo y un agente pone al día README y CHANGELOG.

Cada agente recibe las reglas de su lenguaje (Python, TypeScript, Go, Rust, Java, Kotlin, C#, Ruby, PHP o Swift), además de las comunes.

Tú decides en dos puntos: apruebas el diseño y apruebas el commit.

<p align="center">
  <img src="docs/assets/flow.gif" alt="El flow en tres actos. Arquitectura: describes el objetivo, el arquitecto (Opus) pregunta y escribe architecture.md, otro Opus lo revisa y tú lo apruebas. Construcción: el test-author escribe los tests de aceptación, que fallan porque aún no hay código; la ola 1 corre en paralelo, el hook bloquea una escritura ajena, check-wave verifica, la ola 2 usa ese código y la aceptación pasa a verde. Verificación: el revisor revisa con filtro de confianza, QA encuentra un defecto en WP-02, se corrige con --fix (máximo 2 ciclos), el doc-updater pone al día el mapa del código, el README y el CHANGELOG, y el resultado es PASS; tú haces el commit." width="768">
</p>

- **[Cómo funciona](docs/how-it-works.md):** esquemas del flow, secuencia, ciclo de vida, decisión del hook y matriz de permisos.
- **[Guías por entorno](docs/how-to/README.md):** terminal, Desktop, VS Code, JetBrains, web e iOS, GitHub Actions y el [plugin](docs/how-to/plugin.md).

## Inicio rápido

Requisitos:
- **Dynamic workflows activado:** en Pro, en `/config`. La plantilla ya trae `"enableWorkflows": true`.
- macOS, Linux o WSL 2.
- `python3` 3.9 o posterior.
- `git`.
- El CLI de Claude Code actualizado.
- Un plan Pro, Max, Team o Enterprise.

**Proyecto nuevo**, desde la plantilla:

```bash
gh repo create mi-proyecto --template jagosar/agentic-flow --private --clone
```

**Proyecto que ya existe**, con el plugin, desde una sesión de Claude Code en ese repo:

```
/plugin install agentic-flow --marketplace jagosar/agentic-flow
```

```
/agentic-flow:init
```

`/agentic-flow:init` copia el flow a `.claude/`, combina tu `settings.json` sin quitar nada y detecta tu lenguaje. Si lo repites tras actualizar el plugin, actualiza el flow sin pisar los ficheros que hayas modificado. Los detalles, en [la guía del plugin](docs/how-to/plugin.md).

En la carpeta del proyecto, abre `claude`, acepta el aviso de confianza y ejecuta:

```
/architect Quiero un acortador de URLs con CLI y almacenamiento en JSON
```

```
/implement
```

Sin el plugin, también puedes copiar `.claude/` a mano: lo tienes en [Instalar el flow en un proyecto](docs/how-to/README.md#instalar-el-flow-en-un-proyecto).

## Qué hay dentro

| Pieza | Fichero | Modelo | Papel |
|---|---|---|---|
| `/architect` | `.claude/commands/architect.md` | último Opus | Clasifica la petición, investiga, entrevista y escribe `architecture.md` con contratos y criterios AC-NNN |
| plan-reviewer | `.claude/agents/plan-reviewer.md` | último Opus | Revisa `architecture.md` en contexto limpio antes de tu aprobación |
| `/implement` | `.claude/commands/implement.md` | último Sonnet | Valida, lanza el workflow y gestiona tu puerta de commit |
| `agentic-implement` | `.claude/workflows/agentic-implement.js` | n/a (script) | Workflow nativo: ola 0, olas en paralelo, verificación, revisión adversarial, QA y correcciones con tope, de forma determinista y en segundo plano |
| test-author | `.claude/agents/test-author.md` | último Sonnet | Escribe los tests de aceptación desde los AC, antes del código |
| implementer | `.claude/agents/implementer.md` | último Sonnet | Implementa un work package, en paralelo con los demás de su ola |
| reviewer | `.claude/agents/reviewer.md` | último Sonnet | Revisión de calidad y seguridad, de solo lectura y con filtro de confianza |
| verifier | `.claude/agents/verifier.md` | último Sonnet | Intenta refutar cada hallazgo grave; la incertidumbre nunca rebaja un bloqueo |
| qa | `.claude/agents/qa.md` | último Sonnet | Pruebas exploratorias más allá de los AC |
| doc-updater | `.claude/agents/doc-updater.md` | último Sonnet | Pone al día README, CHANGELOG y guías con el código ya aceptado, dentro de su zona |
| Reglas por lenguaje | `.claude/rules-library/*.md` | n/a | Comunes y por lenguaje. `rules-sync` instala en `.claude/rules/agentic/` las del `stack` y las que detecta |
| Plugin | `.claude-plugin/`, `plugin/commands/init.md` | último Sonnet | `/agentic-flow:init` instala o actualiza el flow en otro repo |
| gatekeeper | `.claude/agents/gatekeeper.md` | último Sonnet | Ejecuta los pasos deterministas de `agentic.py` para el workflow, que no tiene shell |
| `agentic.py` | `.claude/bin/agentic.py` | n/a | Guardarraíles (hook), pasos deterministas (`verify`, `open/close-stage`, `stack`, `codemap`, `docs-check`…), ledger, instalador y lanzador del modo A |

Los modelos están fijados por alias (`opus`, `sonnet`), que siempre apuntan a la versión más reciente que conoce tu Claude Code. `validate` falla si alguien fija otro modelo.

## Guardarraíles

| Riesgo | Protección |
|---|---|
| Un agente escribe en ficheros que no son suyos | Hook `PreToolUse`: cada agente solo escribe en su zona del manifiesto. El revisor y el plan-reviewer, en ninguna |
| Un implementer "pasa" rebajando el examen | Los tests de aceptación los escribe otro agente antes del código. Nadie más puede tocarlos. Deben fallar antes (`--expect red`) y pasar después (`--expect green`) |
| Relajar un linter o formatter para que pase | Bloqueado modificar configuración de calidad existente, salvo `config_edit: true` en el WP |
| Desactivar tests (`skip`, `xfail`, `only`) | Bloqueado en ficheros de test. Los saltos condicionales (`skipIf`) sí se permiten |
| Secretos en el código | Bloqueadas las escrituras con patrones de credenciales (AWS, GitHub, Anthropic, Slack, Google, claves privadas) |
| Saltarse los hooks de git | `--no-verify`, `commit -n` y `core.hooksPath` bloqueados para todos, también para la sesión principal |
| Git, dependencias o sesiones anidadas desde un agente | Bloqueados dentro de cualquier agente del flow |
| Escrituras que esquivan el hook (por Bash) | `check-wave` compara las huellas antes y después de cada etapa |
| Falsos positivos de revisión que bloquean | Un `verifier` independiente intenta refutar cada hallazgo grave; solo se descarta si lo refuta con confianza |
| Romper lo que ya funcionaba | Línea base antes de tocar nada; una fase que pasaba y ahora falla es regresión y bloquea. Los fallos previos se informan sin culpar a ningún WP |
| Un plan que "sigue el estilo" sin decir cuál | Cada WP trae patrones a imitar con `fichero:líneas`; `validate` comprueba que existen |
| Bucles de corrección sin fin | Máximo 2 ciclos de corrección por WP. Después decides tú |
| Documentación que inventa comandos o rutas | El doc-updater solo escribe en su zona `docs` y debe comprobar cada afirmación en el código; `docs-check` valida enlaces, anclas y rutas. El mapa del código lo genera `agentic.py`, nunca el modelo |
| Un agente reescribe el plan, el archivo de decisiones o el flow | `architecture.md`, `docs/architecture/`, `.claude/` y el codemap están vetados a todos los agentes, aunque su zona los incluya por prefijo |
| Actualizar el flow pisa tus cambios | `install` recuerda la huella de cada fichero que instaló: solo sustituye los que no has modificado |
| Instrucciones inyectadas en el repo | Defensa explícita en las instrucciones de cada agente |
| Un fallo del propio guardarraíl | El hook falla cerrado: dentro de un agente, cualquier error bloquea |
| Agentes que se quedan colgados | `timeout_s` por etapa y `agentic.py stop` |
| Créditos de API por error | `auth: "subscription"` quita `ANTHROPIC_API_KEY` a los agentes |

El detalle, con el diagrama de decisión, está en [Cómo funciona § 4](docs/how-it-works.md#4-guardarraíles-decisión-del-hook).

## Estado

- **Probado de principio a fin con agentes reales:**
  - `/implement` con el workflow nativo: ola 0 (16 AC en rojo), dos olas en paralelo, verificación, revisión, QA y ledger cerrado, en unos 5 minutos;
  - el hook bloquea escrituras ajenas también dentro del workflow (probado con una sonda adversarial);
  - **sobre un repo con código** (añadir expiración al acortador): el arquitecto generó la sección 4b y referencias `fichero:línea` exactas, con el *gotcha* de compatibilidad. El workflow fijó la línea base, pasó 13 AC nuevos y mantuvo en verde los 16 antiguos. El fichero de datos de la versión anterior sigue funcionando byte a byte, y los implementers siguieron los patrones citados;
  - el modo A de respaldo, de principio a fin;
  - el plugin: `/agentic-flow:init` en una sesión real (cargado con `--plugin-dir`) instaló el flow en un repo TypeScript y dejó activas sus reglas. `claude plugin validate --strict` pasa en el CI;
  - la actualización de un flow copiado a mano: conservó los ficheros sin registro, los sustituyó con `--force` e instaló las reglas de Python;
  - el doc-updater (modo A) sobre el acortador con expiración: en 21 segundos escribió un CHANGELOG fiel al código, sin salir de su zona, y `docs-check` quedó en verde.
- **Tests del propio flow:** 129 tests en Python (guardarraíles, comandos del pipeline, reglas, documentación viva, instalador, definiciones de agentes, plugin y deriva de la documentación) y 19 escenarios del workflow con agentes simulados. Corren en un CI endurecido: actions fijadas por SHA, permisos mínimos, npm sin scripts de instalación y Python 3.9, 3.12 y 3.14.
- **Sin probar con agentes reales:** el ciclo de corrección, y la etapa de documentación dentro del workflow nativo (los dos solo con escenarios simulados); la entrevista interactiva en la interfaz; la instalación del plugin desde el marketplace; VS Code, JetBrains, nube y GitHub Actions.

## Créditos

Varias ideas del flow v2 están adaptadas de [ECC](https://github.com/affaan-m/ECC) (MIT, © 2026 Affaan Mustafa):
- el juez independiente y la ceremonia según el tamaño;
- la revisión con filtro de confianza y las fases de verificación;
- la protección de configuración, el bloqueo de `--no-verify` y la defensa ante instrucciones inyectadas;
- las reglas por lenguaje y el agente de documentación con su mapa del código.
