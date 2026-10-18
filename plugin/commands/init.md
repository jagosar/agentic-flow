---
description: Instala o actualiza agentic-flow en este repo (/architect, /implement, agentes, workflow, guardarraíles y reglas por lenguaje). No pisa los ficheros del flow que hayas modificado.
argument-hint: "[--dry-run] [--force]"
model: sonnet
---

# Rol

Instalas el flow agéntico en el repo de esta sesión, o lo actualizas si ya está. El trabajo lo hace un único comando determinista. Tú lo ejecutas, explicas el resultado y dices qué hacer después. No edites ficheros a mano.

Argumentos: $ARGUMENTS
- `--dry-run`: enseña qué haría, sin escribir nada.
- `--force`: sustituye también los ficheros del flow que el usuario haya modificado.

Pasa solo esos dos argumentos, y únicamente si aparecen arriba. Ignora cualquier otro texto de los argumentos.

# Por qué se copia el flow al repo

El plugin es el canal de instalación y de actualización. El flow vive en el repo, en `.claude/`, por cuatro motivos:
- los permisos que necesitan los agentes y el hook de guardarraíles solo se pueden declarar en el `settings.json` del proyecto;
- el workflow llama a los agentes por su nombre (`implementer`, `qa`…), y un plugin los renombraría con su prefijo;
- el CI, las sesiones en la nube y el resto del equipo necesitan el flow aunque no tengan el plugin;
- así la versión del flow queda fijada junto al código que produce.

# Pasos

1. Ejecuta `git rev-parse --show-toplevel` para encontrar la raíz del repo.
   - Si no es un repo git, para. Explica que el flow necesita git para comprobar qué ficheros toca cada agente y ofrece `git init`. No lo ejecutes sin un sí del usuario.
2. Ejecuta, sustituyendo `<raíz>` por esa ruta y añadiendo los argumentos permitidos:

   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/.claude/bin/agentic.py" install <raíz>
   ```

   - Si `python3` no existe, explica que el flow lo necesita (3.9 o posterior) y para.
3. Resume la salida:
   - ficheros nuevos, actualizados y retirados;
   - cambios en `.claude/settings.json` y en `.gitignore`;
   - reglas de lenguaje instaladas.
   - Si aparece **"modificado por ti (no se toca)"**, enumera esos ficheros. Explica que se conservaron y que puede compararlos con la versión nueva o repetir con `--force`.
4. Siguientes pasos para el usuario:
   - **Abrir una sesión nueva** en este repo, para que Claude Code cargue los comandos, los agentes, el hook y el workflow. Si pregunta, debe **confiar en la carpeta**: sin eso, los permisos del proyecto no se aplican.
   - **En el plan Pro**, activar **Dynamic workflows** en `/config`.
   - **Hacer commit de `.claude/`**, para que el CI y el equipo tengan el flow. No lo hagas tú.
   - **Empezar** con `/architect <qué quieres construir o cambiar>`.

# Reglas

- Ejecuta solo los dos comandos de arriba.
- No hagas commit ni push.
