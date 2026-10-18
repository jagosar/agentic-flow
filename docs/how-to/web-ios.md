# How-to: sesiones en la nube (web e iOS)

**Objetivo:** ejecutar el flow en una sesión en la nube de Claude Code, lanzada desde el navegador, el móvil, Desktop o la terminal.
**Estado:** sin probar. Esta guía sigue la documentación oficial de las sesiones en la nube.

Antes, lee los [requisitos comunes](README.md#requisitos-comunes). En la nube no necesitas instalar nada en tu máquina.

## Qué es una sesión en la nube

- Corre en una máquina virtual de Anthropic (Ubuntu 24.04, con Python 3, git y otras herramientas ya instaladas) sobre un clon de tu repo de GitHub.
- Sigue funcionando aunque cierres el portátil.
- Está disponible en Pro, Max y Team. Cuenta contra los límites de uso de tu plan, sin cargo aparte, y siempre usa tu suscripción.
- Carga los `.claude/agents/` del repo y el `.claude/settings.json` (hooks y permisos), así que los guardarraíles del flow se aplican también aquí.

## 1. Preparar

1. Conecta GitHub con una de estas opciones:
   - **En el navegador:** instala la **Claude GitHub App** durante la configuración inicial en [claude.ai/code](https://claude.ai/code).
   - **Desde la terminal:** ejecuta `/web-setup`, que reutiliza tu sesión de `gh`.
2. Haz push de la rama con `.claude/` y `architecture.md`, si ya existe. La nube clona lo que está en GitHub, no tu copia local.

## 2. Lanzar la sesión

Elige una de estas opciones:

- **Navegador:** [claude.ai/code](https://claude.ai/code), luego el repo y la rama.
- **iPhone:** pestaña **Code** de la app de Claude.
- **Desktop:** al crear la sesión, elige **Cloud** en vez de **Local**.
- **Terminal:**

  ```bash
  claude --cloud "/implement modo B"
  ```

## 3. Usar el flow

```
/architect <tu petición>
```

```
/implement modo B
```

- **Usa el modo B en la nube.** No está comprobado que dentro de la VM haya un CLI que pueda lanzar sesiones `claude -p`. El modo B reparte el trabajo en subagentes de la propia sesión, con los mismos guardarraíles.
- Los cambios aparecen con el indicador `+N -M`. Ábrelo para ver el diff y comentar líneas.
- Cuando termine, crea el PR desde la interfaz de la sesión.

## Recomendado desde el móvil

La entrevista del arquitecto encaja bien en el móvil: son preguntas cortas con opciones. Dos formas de aprovecharlo:

- **Diseño en el móvil, ejecución en Desktop:** haz `/architect` desde el iPhone y, cuando apruebes, lanza `/implement` en Desktop, donde el modo A garantiza el paralelismo. Para continuar una sesión en la nube en tu terminal: `claude --teleport`.
- **Todo en tu máquina:** empieza la sesión en Desktop o en la terminal y síguela desde el móvil con **Remote Control**.

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| La sesión no ve `.claude/` o el `architecture.md` | No hiciste push de esa rama. La nube clona el remoto |
| No aparecen repositorios | Revisa la conexión con GitHub (App instalada en el repo, o `/web-setup`) |
| La sesión no puede subir su rama porque `git push` está bloqueado | Las reglas `deny` de `.claude/settings.json` lo impiden a todos los agentes. Crea el PR desde la interfaz y, si eso tampoco funciona en tu caso, quita la regla de `git push` en la rama que uses en la nube |
| Se agotan los límites de uso | Las sesiones en la nube comparten límites con el resto de tu uso. Lanza menos WP por ola o espera a que se renueven |

## Referencias

- [Claude Code en la nube](https://code.claude.com/docs/en/claude-code-on-the-web)
- [Entornos en la nube](https://code.claude.com/docs/en/cloud-environments)
- [Remote Control](https://code.claude.com/docs/en/remote-control)
