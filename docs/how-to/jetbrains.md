# How-to: JetBrains (IntelliJ IDEA, PyCharm, WebStorm, GoLand, PhpStorm, Android Studio)

**Objetivo:** usar el flow desde un IDE de JetBrains, con los diffs en el visor del IDE.
**Estado:** sin probar. El plugin ejecuta el mismo CLI, así que el flow debería comportarse igual que en [terminal.md](terminal.md).

Antes, cumple los [requisitos comunes](README.md#requisitos-comunes) e [instala el flow en tu proyecto](README.md#instalar-el-flow-en-un-proyecto).

## Requisitos de este entorno

- **El CLI instalado.** El plugin no trae su propia copia, así que es obligatorio.
- El plugin **Claude Code [Beta]** de JetBrains Marketplace.

## 1. Instalar

1. Instala el CLI:

   ```bash
   curl -fsSL https://claude.ai/install.sh | bash
   ```

2. Ve a `Settings → Plugins → Marketplace`, busca **Claude Code [Beta]**, pulsa Install y reinicia el IDE.

**Resultado esperado:** el botón de Claude Code en la interfaz del IDE.

## 2. Abrir Claude Code

- Usa el atajo `Ctrl+Esc` (`Cmd+Esc` en Mac) o el botón de Claude Code.
- O ejecuta `claude` en la terminal integrada, desde la raíz del proyecto.
- Si usas una terminal externa, conéctala al IDE con `/ide`.

Comprueba que los diffs se abren en el IDE: ejecuta `/config` y pon **Diff tool** en `auto`.

## 3. Usar el flow

Es el mismo que en [terminal.md](terminal.md):

```
/architect <tu petición>
```

```
/implement
```

- Los cambios del modo A se escriben directamente en disco. Revísalos en la ventana **Commit** (`Alt+0`) o en **Git → Local Changes**.
- Abre `qa/report.md` para ver el resultado de QA.

## Seguridad

La documentación oficial avisa de que, en JetBrains, el modo `acceptEdits` puede modificar ficheros de configuración del IDE que el IDE ejecuta. Por eso recomienda el modo Manual para editar.

- **En tu sesión interactiva:** sigue esa recomendación.
- **Los agentes del flow** usan `acceptEdits`, pero el hook solo les deja escribir los ficheros de su WP, así que no pueden tocar `.idea/` ni nada fuera del manifiesto.

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| "Cannot launch Claude Code" o "command not found" | Comprueba `claude --version`. Si el IDE no lo encuentra, pon la ruta completa en `Settings → Tools → Claude Code [Beta] → Claude command` |
| macOS: funciona en la terminal pero no desde el IDE | Si lanzas el IDE desde el Dock, puede no heredar el `PATH` de tu shell. Pon la ruta completa en **Claude command** |
| Windows con WSL | En **Claude command**, pon `wsl -d Ubuntu -- bash -lic "claude"`, con tu distribución |
| "No available IDEs detected" en WSL2 | Sigue la sección WSL de la guía oficial (regla de firewall o red en modo *mirrored*) |
| `Esc` no interrumpe | En `Settings → Tools → Terminal`, desmarca "Move focus to the editor with Escape" |

## Referencias

- [Claude Code en JetBrains](https://code.claude.com/docs/en/jetbrains)
