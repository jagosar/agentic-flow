# How-to: Claude Code en terminal

**Objetivo:** ejecutar el flow completo desde una terminal, de forma interactiva o por scripts.
**Estado:** probado. Pasada completa (`/architect`, `/implement` y QA) en modo A y en modo B con Claude Code 2.1.302.

Antes, cumple los [requisitos comunes](README.md#requisitos-comunes) e [instala el flow en tu proyecto](README.md#instalar-el-flow-en-un-proyecto).

## 1. Instalar y entrar

Instalador nativo (recomendado, se actualiza solo):

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Abre una terminal nueva y comprueba la instalación:

```bash
claude --version
```

Entra en el proyecto y arranca Claude Code:

```bash
cd ~/code/mi-proyecto && claude
```

**Resultado esperado:** la primera vez se abre el navegador para iniciar sesión y aparece el aviso de confianza de la carpeta. Acéptalo.

## 2. Diseñar

Dentro de la sesión:

```
/architect Quiero migrar el módulo de pagos de REST a gRPC, manteniendo la API pública
```

- El comando cambia solo al último Opus. No hace falta `/model`.
- Responde a las rondas de preguntas, eligiendo con las flechas y `Enter`.
- **Resultado esperado:** `architecture.md` escrito, `Manifiesto válido` y una petición de aprobación.

Revisa el documento en tu editor y haz commit:

```bash
git add architecture.md && git commit -m "Architecture: pagos gRPC"
```

## 3. Implementar

```
/implement
```

- El orquestador cambia solo al último Sonnet, comprueba que `claude` existe y usa el modo A.
- Cada ola corre en segundo plano y la sesión te avisa cuando termina.
- **Resultado esperado:** una tabla de WP en `DONE`, la integración en verde y el estado de QA.

Para ver el avance en directo desde otra terminal:

```bash
tail -f .claude/state/runs/*.log
```

## 4. Flujo manual, sin orquestador

Con `architecture.md` aprobado puedes lanzar cada etapa desde la shell. Cada comando devuelve `0` si todo va bien y `3` si hay que revisar.

```bash
python3 .claude/bin/agentic.py validate
```

```bash
python3 .claude/bin/agentic.py run-wave 1
```

```bash
python3 .claude/bin/agentic.py run-qa
```

Todas las olas seguidas, y QA al final:

```bash
set -e; for n in $(python3 -c "import json,re;m=json.loads(re.search(r'\`\`\`json\s+wp-manifest\s*\n(.*?)\n\`\`\`',open('architecture.md').read(),re.S).group(1));print(' '.join(map(str,sorted({w['wave'] for w in m['work_packages']}))))"); do python3 .claude/bin/agentic.py run-wave $n; done; python3 .claude/bin/agentic.py run-qa
```

## 5. Corregir defectos de QA

Lee el informe:

```bash
python3 -c "import json;print(json.load(open('.claude/state/runs/QA.json'))['result'])"
```

Relanza el WP afectado en modo corrección:

```bash
python3 .claude/bin/agentic.py run-wave 1 WP-01 --fix
```

Vuelve a pasar QA:

```bash
python3 .claude/bin/agentic.py run-qa
```

Sin `--fix`, el WP se implementa como si fuera nuevo y no lee el informe de QA.

## 6. Servidor remoto por SSH

Usa `tmux` para que una ola larga no se corte si se cae la conexión:

```bash
tmux new -s agentic
```

Para seguir la sesión desde el móvil, activa Remote Control dentro de Claude Code con `/remote-control`.

## Verificación

- `git status`: solo deben aparecer los ficheros de los WP y `qa/`.
- La salida de cada etapa termina en `RESULTADO: OK`.
- Ejecuta tú mismo la suite del proyecto, con el comando de la sección 3 de `architecture.md`.

## Problemas frecuentes

| Síntoma | Solución |
|---|---|
| `claude: command not found` tras instalar | Abre una terminal nueva. Si sigue, añade `~/.local/bin` al `PATH` |
| `claude update` da un error de permisos | Si instalaste con npm y usas nvm, la shell puede estar usando el npm del sistema: `$(dirname $(which node))/npm install -g @anthropic-ai/claude-code@latest`. O pásate al instalador nativo |
| `/architect` no aparece | Ejecuta `claude` desde la raíz del repo, donde está `.claude/` |

Para el resto de errores, consulta la [tabla común](README.md#problemas-frecuentes).

## Referencias

- [Instalación](https://code.claude.com/docs/en/setup)
- [Remote Control](https://code.claude.com/docs/en/remote-control)
