# How-to: Visual Studio Code (y Cursor)

**Objetivo:** usar el flow desde la extensión oficial de Claude Code, revisando los cambios en el editor.
**Estado:** sin probar. Esta guía sigue la documentación oficial de la extensión. El flow usa los mismos ficheros `.claude/` que el CLI.

Antes, cumple los [requisitos comunes](README.md#requisitos-comunes) e [instala el flow en tu proyecto](README.md#instalar-el-flow-en-un-proyecto).

## Requisitos de este entorno

- VS Code 1.94 o posterior. También funciona en Cursor.
- Extensión **Claude Code**, de Anthropic (`anthropic.claude-code`).
- **El CLI instalado aparte**, para el modo A. La extensión trae su propia copia del CLI para el panel de chat, pero no la pone en el `PATH`.

## 1. Instalar

1. Abre Extensiones (`Ctrl+Shift+X`, o `Cmd+Shift+X` en Mac), busca **Claude Code** y pulsa **Install**.
2. Abre el panel con el icono **Spark**. Está en la barra de herramientas del editor (con un fichero abierto), en la Activity Bar o en **✻ Claude Code**, en la barra de estado.
3. Pulsa **Sign in** y autoriza en el navegador con tu cuenta del plan. No necesitas API key.

**Resultado esperado:** el panel abierto y con sesión iniciada.

## 2. Abrir el proyecto

Usa `File → Open Folder` sobre la raíz del repo, donde está `.claude/`. Al escribir `/` en el panel, deberían aparecer `/architect`, `/implement` y `/qa`.

## 3. Usar el flow

```
/architect Quiero añadir exportación a PDF de las facturas
```

- No hace falta elegir modelo: cada comando fija el suyo. Para ver el modelo de la sesión, pulsa su nombre al pie de la caja de texto.
- El indicador de modo de permisos, al pie de la caja de texto, funciona como en Desktop. Empieza con un modo que te pregunte.
- Revisa `architecture.md` en el editor y apruébalo.

```
/implement
```

- **Modo B:** pulsa el contador de agentes para abrir el **mapa de agentes**. Ahí ves cada subagente con su estado y su transcripción.
- **Modo A:** los procesos escriben directamente en disco. Revisa los cambios en **Source Control** (`Ctrl+Shift+G`).

## 4. Revisar y commit

- **Source Control** muestra cada fichero tocado. Abre `qa/report.md` para ver el resultado de QA.
- Haz el commit desde Source Control. El push también lo haces tú.

## Alternativa: el CLI en la terminal integrada

Abre la terminal integrada (`` Ctrl+` ``) y sigue [terminal.md](terminal.md). Si arrancas `claude` desde ahí, se conecta con el editor para mostrar los diffs.

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `/implement` siempre usa el modo B | Instala el CLI aparte y reinicia VS Code |
| No aparecen los comandos del flow | Abre la carpeta raíz del repo, no una subcarpeta |
| Las preguntas del arquitecto salen como texto en vez de opciones | Contesta en el chat: el arquitecto acepta respuestas en texto |

## Referencias

- [Claude Code en VS Code](https://code.claude.com/docs/en/vs-code)
