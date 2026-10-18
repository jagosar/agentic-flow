# How-to: Claude Code en terminal

Antes, lee los requisitos de [README.md](README.md). Es el entorno donde está probado el modo paralelo.

## 1. Instalar

```bash
npm install -g @anthropic-ai/claude-code
```

```bash
claude update
```

La primera vez que ejecutes `claude` te pedirá iniciar sesión.

## 2. Flujo interactivo

```bash
cd ~/code/mi-proyecto
```

```bash
claude --model claude-opus-5-5
```

Dentro de la sesión:

```
/architect Quiero migrar el módulo de pagos de REST a gRPC
```

Después de aprobar `architecture.md`:

```
/implement
```

Mientras se ejecuta una ola, puedes seguir el avance desde otra terminal:

```bash
tail -f .claude/state/runs/*.log
```

## 3. Flujo manual (sin orquestador)

Una vez aprobado `architecture.md`, puedes saltarte `/implement` y lanzar todo desde la shell. El resultado es el mismo y tienes más control:

```bash
python3 .claude/bin/agentic.py validate
```

```bash
python3 .claude/bin/agentic.py run-wave 1
```

```bash
python3 .claude/bin/agentic.py run-wave 2
```

```bash
python3 .claude/bin/agentic.py run-qa
```

Cada comando termina con código `0` si todo está bien y `3` si hay que revisar. Eso permite encadenarlos.

Script para todas las olas (guárdalo como `run-all.sh` en tu proyecto si lo quieres reutilizar):

```bash
set -e; for n in $(python3 -c "import json,re;m=json.loads(re.search(r'\`\`\`json\s+wp-manifest\s*\n(.*?)\n\`\`\`',open('architecture.md').read(),re.S).group(1));print(' '.join(map(str,sorted({w['wave'] for w in m['work_packages']}))))"); do python3 .claude/bin/agentic.py run-wave $n; done; python3 .claude/bin/agentic.py run-qa
```

## 4. Corregir defectos de QA

```bash
python3 -c "import json;print(json.load(open('.claude/state/runs/QA.json'))['result'])"
```

```bash
python3 .claude/bin/agentic.py run-wave 1 WP-01 --fix
```

```bash
python3 .claude/bin/agentic.py run-qa
```

Con `--fix`, el implementador recibe la instrucción de corregir los defectos que QA le asignó en el último informe. Sin `--fix`, el WP se implementa desde cero, aunque haya un informe de QA anterior.

## 5. Servidor remoto (SSH)

El flow funciona igual en una máquina remota. Usa `tmux` o `screen` para que una ola larga no se corte si se cae la conexión:

```bash
tmux new -s agentic
```
