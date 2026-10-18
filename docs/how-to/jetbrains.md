# How-to: JetBrains (IntelliJ IDEA, PyCharm, WebStorm, GoLand…)

Antes, lee los requisitos de [README.md](README.md).

## 1. Instalar

1. Instala el CLI, porque el plugin lo usa por debajo:

```bash
npm install -g @anthropic-ai/claude-code
```

2. `Settings → Plugins → Marketplace` → busca **Claude Code** (de Anthropic) → Install → reinicia el IDE.

## 2. Usarlo

1. Abre el proyecto con `.claude/` commiteado.
2. Lanza Claude Code desde el botón del plugin o ejecutando `claude` en la terminal integrada (`Alt+F12`). Se abre una sesión CLI dentro del IDE.
3. A partir de ahí, el flujo es el de [terminal.md](terminal.md):

```
/model opus
/architect <tu petición>
/implement
```

## 3. Revisar

- Los diffs que propone Claude se abren en el visor de diferencias del IDE.
- Los cambios del modo A se escriben directamente en disco: míralos en la ventana **Commit** (`Alt+0`) o en **Git → Local Changes**.
- Abre `qa/report.md` para ver el resultado de QA.

## Notas

- Si el plugin no detecta el CLI, comprueba que `claude` está en el `PATH` del IDE. En macOS, un IDE lanzado desde el Dock no siempre hereda el `PATH` de tu shell.
- **Sin probar:** no he probado este flow en JetBrains. Como el plugin ejecuta el mismo CLI, debería comportarse igual que en la terminal.
