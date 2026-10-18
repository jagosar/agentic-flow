# How-to: Visual Studio Code

Antes, lee los requisitos de [README.md](README.md).

## 1. Instalar

1. Extensiones (`Ctrl+Shift+X`) → busca **Claude Code** (editor: Anthropic) → Instalar.
2. Inicia sesión desde el panel de la extensión con tu cuenta de Claude.
3. Instala también el CLI si no lo tienes, porque lo necesita el modo paralelo A:

```bash
npm install -g @anthropic-ai/claude-code
```

```bash
claude --version
```

Mantenla actualizada (`claude update`): los alias `opus` y `sonnet` del flow apuntan a los modelos más recientes que conoce tu versión.

## 2. Abrir el proyecto

`File → Open Folder` → la carpeta del repo, con `.claude/` commiteado. La extensión lee los mismos `.claude/commands`, `.claude/agents` y `.claude/settings.json` que el CLI.

## 3. Usarlo

Abre el panel de Claude Code (icono en la barra lateral, o la paleta de comandos `Ctrl+Shift+P` → "Claude Code").

```
/model opus
/architect Quiero añadir exportación a PDF de las facturas
```

- Responde a las preguntas del arquitecto en el panel.
- Revisa `architecture.md` en el editor y apruébalo.

```
/implement
```

- Los cambios de los agentes aparecen como diffs en el editor. Los del modo A se escriben directamente en disco, así que míralos en **Source Control** (`Ctrl+Shift+G`).
- Si prefieres ver la ejecución en bruto, abre la terminal integrada (`` Ctrl+` ``) y lanza las olas tú mismo:

```bash
python3 .claude/bin/agentic.py run-wave 1
```

## 4. Revisar y commit

- **Source Control** muestra cada fichero tocado. Abre `qa/report.md` para ver los defectos.
- Haz el commit desde la propia vista de Source Control.

## Notas

- **Alternativa sin extensión:** ejecuta `claude` en la terminal integrada. Es el flujo de [terminal.md](terminal.md), con el editor al lado.
- **Sin probar:** no he comprobado que las tarjetas de preguntas del arquitecto (AskUserQuestion) se vean igual en la extensión que en Desktop. Si no aparecen, el arquitecto hará las preguntas en texto y le respondes en el chat.
