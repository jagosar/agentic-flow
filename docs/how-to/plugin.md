# How-to: instalar y actualizar el flow con el plugin

> Revisado el 18-10-2026 con Claude Code 2.1.302. Lo común a todos los entornos está en el [README de las guías](README.md).

El plugin `agentic-flow` es la forma de llevar el flow a un repo que ya existe y de mantenerlo al día. Para un proyecto nuevo, la plantilla sigue siendo lo más rápido (`gh repo create --template`).

## Qué hace y qué no

El plugin trae un solo comando, `/agentic-flow:init`, que **copia el flow al repo** (`.claude/`) y lo actualiza cuando hay versión nueva. Los agentes, el workflow y el hook no se ejecutan desde el plugin, sino desde el repo, por cuatro motivos:

1. **Permisos y hook:** los permisos que necesitan los agentes y el hook de guardarraíles solo se pueden declarar en el `settings.json` del proyecto. Un plugin no puede añadir permisos.
2. **Nombres:** el workflow llama a los agentes por su nombre (`implementer`, `qa`…), y un plugin los renombraría con su prefijo (`agentic-flow:implementer`).
3. **Equipo, CI y nube:** el CI, las sesiones en la nube y tus compañeros necesitan el flow aunque no tengan el plugin.
4. **Reproducibilidad:** la versión del flow queda fijada junto al código que produce.

Desinstalar el plugin no quita el flow del repo.

## Requisitos

- Claude Code 2.1.275 o posterior, para instalarlo en un paso. Con versiones anteriores, usa los dos pasos de abajo.
- Acceso de lectura a `jagosar/agentic-flow`. Es un repo privado: Claude Code lo clona con git, así que tu git tiene que poder autenticarse en GitHub (por ejemplo, con `gh auth login` y `gh auth setup-git`).
- `python3` 3.9 o posterior y `git`, como el resto del flow.

## Instalar

En una sesión de Claude Code dentro de tu repo:

```
/plugin install agentic-flow --marketplace jagosar/agentic-flow
```

O en dos pasos, también desde la terminal:

```bash
claude plugin marketplace add jagosar/agentic-flow
```

```bash
claude plugin install agentic-flow@agentic-flow
```

Después, en la sesión:

```
/agentic-flow:init
```

`/agentic-flow:init` hace esto:
- **Copia el flow:** agentes, comandos, workflow, `agentic.py` y la librería de reglas, a `.claude/`. No copia los tests del propio flow.
- **Combina tu `.claude/settings.json`:** añade los permisos, las reglas `deny`, el hook y `enableWorkflows`, sin quitar nada tuyo.
- **Configuración y `.gitignore`:** crea `.claude/agentic.json` si no existe y añade al `.gitignore` `.claude/state/` y `.agentic-result.json`.
- **Reglas:** detecta tu lenguaje e instala sus reglas en `.claude/rules/agentic/`.
- **Registro:** guarda en `.claude/agentic-install.json` la versión y la huella de cada fichero instalado.

Con `--dry-run` enseña qué haría, sin escribir nada.

Luego:
1. **Abre una sesión nueva** en el repo y acepta el aviso de confianza. Sin él, Claude Code ignora los permisos del proyecto.
2. **En Pro, activa Dynamic workflows** en `/config`.
3. **Haz commit de `.claude/`.**
4. **Empieza** con `/architect`.

## Actualizar

```bash
claude plugin update agentic-flow@agentic-flow
```

Reinicia la sesión y vuelve a ejecutar `/agentic-flow:init`. Cada fichero del flow acaba en uno de estos estados:

| Estado | Qué pasa |
|---|---|
| nuevo | No existía: se copia |
| actualizado | Ha cambiado en la versión nueva y tú no lo habías tocado: se sustituye |
| igual | Ya está al día |
| modificado por ti (no se toca) | Lo has editado desde la última instalación: se conserva y se lista. Compáralo con la versión nueva, o repite con `--force` para sustituirlo |
| retirado | La versión nueva ya no lo trae y tú no lo habías tocado: se borra |

El instalador sabe qué has tocado porque compara cada fichero con la huella guardada en `.claude/agentic-install.json`. Un fichero que no tenía registro (por ejemplo, de una copia a mano) y que es distinto del nuevo cuenta como modificado: no se pisa sin `--force`.

## Probar sin instalar

Para probar una copia local del plugin en una sola sesión, sin tocar tu configuración:

```bash
claude --plugin-dir /ruta/a/agentic-flow
```

## Publicar una versión (mantenedores)

1. Sube `version` en `.claude-plugin/plugin.json`. La versión solo está ahí: la entrada del marketplace no la repite.
2. Comprueba el plugin, como hace el CI:

   ```bash
   claude plugin validate --strict .
   ```

3. Crea la etiqueta `agentic-flow--v<versión>`:

   ```bash
   claude plugin tag .
   ```

## Problemas frecuentes

| Síntoma | Causa y solución |
|---|---|
| `/plugin install` no encuentra el marketplace | El repo es privado y git no puede autenticarse. Configura tus credenciales de GitHub para git y repite |
| `/agentic-flow:init` no aparece | El plugin se carga al iniciar la sesión: reiníciala tras instalarlo o actualizarlo |
| Tras `init`, `/architect` no aparece | Abre una sesión nueva en el repo: los comandos y agentes del proyecto se cargan al inicio |
| `modificado por ti` en ficheros que no recuerdas haber tocado | El flow se copió a mano antes, sin registro. Revisa la diferencia y usa `--force` si no hay nada tuyo |
