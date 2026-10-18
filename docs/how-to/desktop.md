# How-to: Claude Code Desktop

**Objetivo:** usar el flow desde la pestaña **Code** de la app de Claude.
**Estado:** parcial. Los scripts, los agentes y las dos pasadas completas se ejecutaron desde una sesión de Desktop. La entrevista de `/architect` con tarjetas de preguntas no se ha probado en la interfaz.

Antes, cumple los [requisitos comunes](README.md#requisitos-comunes) e [instala el flow en tu proyecto](README.md#instalar-el-flow-en-un-proyecto).

## Requisitos de este entorno

- La app de Claude para macOS, Windows o Linux (beta), con sesión iniciada en un plan Pro, Max, Team o Enterprise.
- **El CLI instalado aparte**, para el modo A. La app trae su propio Claude Code, pero no pone `claude` en el `PATH`. Sin el CLI, `/implement` usa el modo B.
- En Windows, trabaja con el entorno **WSL**, porque `agentic.py` necesita POSIX.

## 1. Abrir la sesión

1. Abre la app y pulsa la pestaña **Code**, arriba en el centro.
2. Elige **Local**, o **WSL** en Windows, y pulsa **Select folder**. Selecciona la carpeta del repo.
3. **Modelo:** el desplegable junto al botón de enviar no importa para el flow. `/architect` cambia solo al último Opus, y `/implement` y `/qa` al último Sonnet.
4. **Modo de permisos** (selector junto al botón de enviar):
   - **Manual** la primera vez, para ver cada paso.
   - **Accept edits** cuando conozcas el flow.
   - **Auto** no se ha probado con el flow: su clasificador podría frenar el lanzamiento de agentes en paralelo.

**Resultado esperado:** una sesión abierta en tu proyecto. Al escribir `/`, aparecen `/architect`, `/implement` y `/qa`.

## 2. Diseñar

```
/architect Quiero un servicio de reservas con API REST, Postgres y autenticación JWT
```

- Las preguntas aparecen como tarjetas con opciones, con la recomendada primero.
- Al final verás `Manifiesto válido` y una petición de aprobación.
- Abre `architecture.md` en el panel de ficheros (pulsa la ruta) y revísalo. Cuando lo apruebes, pide en la sesión "haz commit de architecture.md".

## 3. Implementar

```
/implement
```

- En el modo A, cada ola corre como tarea en segundo plano. Ábrela en el **panel de tareas**, donde también aparecen los subagentes del modo B.
- Puedes seguir hablando con la sesión mientras corre. La app te avisa al acabar.
- Para ver los logs en bruto, abre el terminal integrado con **Ctrl+\`** y ejecuta `tail -f .claude/state/runs/*.log`.

**Resultado esperado:** una tabla de WP en `DONE`, la integración en verde y el estado de QA.

## 4. Revisar y entregar

- Pulsa el indicador `+N -M` para abrir la **vista de diff**. Puedes comentar líneas concretas y Claude lo revisará.
- Revisa el informe de QA en `qa/report.md`.
- Opcional: `/code-review` hace una revisión de calidad además de QA.
- Para el commit, el push y el PR, pídeselo a la sesión o usa los botones de la app. Los agentes del flow no pueden hacer commit ni push; la sesión principal solo lo hace si se lo pides.

## Trucos

- **Varias features a la vez:** abre una sesión por feature desde la barra lateral, cada una en su worktree.
- **Desde el móvil:** activa **Remote Control** en la sesión para responder a la entrevista del arquitecto desde el teléfono. La ejecución sigue en tu máquina, en modo A.
- **Trabajo largo:** elige **Cloud** al crear la sesión para que siga aunque cierres la app. Consulta [web-ios.md](web-ios.md).
- **Seguir el avance sin esperar:** mientras una ola trabaja, pregunta "¿cómo va?" y el orquestador responde desde el ledger. Para cortar, di "para" o "para WP-02".
- **Relanzar un WP:** escribe "relanza WP-03 de la ola 2 para corregir los defectos de QA". La sesión ejecuta `run-wave 2 WP-03 --fix`.

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `/implement` siempre usa el modo B | Instala el CLI (ver requisitos) y reinicia la app |
| La app pide permiso para `agentic.py` cada vez | Abre `claude` una vez en la carpeta desde una terminal y acepta el aviso de confianza |
| No aparecen `/architect` ni los demás | Comprueba que `.claude/commands/` está en la carpeta que elegiste |

## Referencias

- [Primeros pasos con Desktop](https://code.claude.com/docs/en/desktop-quickstart)
- [Usar Claude Code Desktop](https://code.claude.com/docs/en/desktop)
