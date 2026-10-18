#!/usr/bin/env python3
"""Render docs/assets/screens/*.png: real terminal output from the flow, in the same visual system as flow.gif.

Usage: python3 docs/assets/make_screens.py   (needs Pillow and the IBM Plex fonts)

Every transcript below was captured from real runs on 2026-10-18/19 (the shortener test project, a fresh
TypeScript repo for the installer). Long lists are shortened, marked with "…", and the /implement report is
condensed to its main sections (same facts and wording). The flow's own messages are in Spanish, so they appear
as they are.
"""
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).with_name("screens")
SS = 2
WIDTH = 920
PAD = 28
LINE = 21
WRAP = 84

C = {
    "bg": (241, 239, 234), "card": (250, 249, 246), "bar": (236, 233, 227), "hair": (207, 203, 194),
    "grey": (140, 136, 128), "ink": (29, 29, 27), "accent": (235, 106, 43), "ok": (62, 125, 82), "err": (192, 57, 43),
}


def font_path(family, style):
    name = f"IBMPlex{family}-{style}.ttf"
    for root in (Path("/usr/share/fonts"), Path("/Library/Fonts"), Path.home() / ".fonts",
                 Path.home() / ".local/share/fonts"):
        if root.exists():
            hit = next(root.rglob(name), None)
            if hit:
                return hit
    if shutil.which("fc-match"):
        out = subprocess.run(["fc-match", "-f", "%{file}", f"IBM Plex {family}:style={style}"], capture_output=True,
                             text=True)
        if out.stdout.endswith(name):
            return Path(out.stdout)
    raise SystemExit(f"{name} not found. Install IBM Plex (e.g. `apt install fonts-ibm-plex`) and run again.")


def font(family, style, size):
    return ImageFont.truetype(str(font_path(family, style)), size * SS)


MONO = font("Mono", "Regular", 13)
MONO_B = font("Mono", "SemiBold", 13)
TITLE = font("Sans", "Medium", 12)

GREEN = re.compile(r"\b(OK|PASS|DONE|done|pass|VERDE|válido)\b")
RED = re.compile(r"\b(REVISAR|BLOCKER|bloqueado|blocker)\b|\[agentic guard\]|Manifiesto inválido")

SCREENS = {
    "ledger": ("~/shortener — agentic.py status", """\
$ python3 .claude/bin/agentic.py status
# Ledger del flow

## Etapas

- línea base: OK (23:47)
- acceptance: OK (23:47)
- aceptación (red): OK (23:47)
- ola 1: OK (23:51)
- aceptación (green): OK (23:51)
- verificación: OK (23:51)
- review: OK (23:51)
- qa: OK (23:52)
- docs: OK (23:53)
- docs-check: OK (23:53)

## Agentes

- [done]    WP-01 (sonnet) — etapa 1 — modo workflow — inicio 23:50 — DONE
- [done]    WP-02 (sonnet) — etapa 1 — modo workflow — inicio 23:51 — DONE (fix)
- [done]    AT (sonnet) — etapa acceptance — modo workflow — inicio 23:47 — DONE
- [pass]    REVIEW (sonnet) — etapa review — modo workflow — inicio 23:51 — PASS
- [done]    DOCS (sonnet) — etapa docs — modo workflow — inicio 23:52 — DONE
- [pass]    QA (sonnet) — etapa qa — modo workflow — inicio 23:52 — PASS"""),
    "hook": ("~/shortener — PreToolUse hook", """\
# WP-02 tries to write before claiming its package
[agentic guard] Antes de nada, ejecuta `python3 .claude/bin/agentic.py claim <ID>` con tu WP-ID (o QA, AT, REVIEW, DOCS).

# WP-02, claimed, tries to write a file that belongs to WP-01
[agentic guard] WP-02 no posee shortener/storage.py. Ficheros permitidos: shortener/cli.py, tests/test_cli.py. Si necesitas tocarlo, devuelve STATUS: BLOCKER (o, si eres QA, repórtalo como defecto).

# WP-02 tries to commit
[agentic guard] WP-02: comando bloqueado, no se pueden ejecutar operaciones de git que escriban (solo status, diff, log, show): git commit -m wip"""),
    "install": ("~/shop — agentic.py install", """\
$ python3 ~/agentic-flow/.claude/bin/agentic.py install .
agentic-flow 1.0.0 -> shop
  nuevo: 23
    .claude/agents/doc-updater.md
    .claude/agents/gatekeeper.md
    .claude/agents/implementer.md
    …
    .claude/workflows/agentic-implement.js
  settings.json: allow Bash(python3 .claude/bin/agentic.py:*), allow Workflow(agentic-implement), deny Bash(git reset --hard:*), deny Bash(git clean:*), deny Bash(rm -rf:*), hook PreToolUse, enableWorkflows
  .gitignore: .claude/state/, .agentic-result.json
  .claude/agentic.json: creado con los valores por defecto
  reglas: common, typescript
RESULTADO: OK

$ python3 ~/agentic-flow/.claude/bin/agentic.py install .
agentic-flow 1.0.0 -> shop
  igual: 23
  settings.json: sin cambios
  reglas: common, typescript
RESULTADO: OK"""),
    "validate": ("~/shop — agentic.py validate", """\
$ python3 .claude/bin/agentic.py validate
Manifiesto inválido:
  Fichero con dos propietarios: src/cart.ts (WP-01) y src/ (WP-02).

$ python3 .claude/bin/agentic.py validate
Manifiesto inválido:
  stack: no hay reglas para 'cobol'. Disponibles: csharp, go, java, kotlin, php, python, ruby, rust, swift, typescript. Si el lenguaje no está, quítalo de 'stack' y pon sus convenciones en la sección 7."""),
    "report": ("~/shortener — /implement (condensed)", """\
> /implement 1

## Resultado: OK

### Work packages
| WP    | Estado | Ficheros                                    |
|-------|--------|---------------------------------------------|
| WP-01 | DONE   | shortener/stats.py, tests/test_stats.py     |
| WP-02 | DONE   | shortener/cli.py                            |

### Verificación
- Build: OK.  Tests: 61 OK.  Aceptación: VERDE (53 tests).

### QA: PASS
- Cobertura: contratos 6.1 y 6.2 y AC-001 a AC-005; --limit inválido (salida 2), fichero corrupto (salida 3).

### Correcciones
Hubo 1 ciclo de corrección, en WP-02 (cli.py).

### Documentación
- README.md y CHANGELOG.md: stats, list --limit N y la salida 2 para --limit inválido.
- docs/CODEMAP.md cambió (25 ficheros, 4 carpetas). docs-check: OK.

### Commits propuestos (esperan tu aprobación)
1. Estadísticas: módulo stats y compute (WP-01)
2. CLI: subcomando stats y list --limit (WP-02)
…"""),
    "fix": ("~/shortener — fix prompt sent to WP-02 by the workflow", """\
Corrige WP-02 según architecture.md. El código ya existe. Estos son los defectos que los jueces
(revisor y QA) atribuyen a tu WP, en JSON:

[{"source": "revisor", "severity": "alta", "wp": "WP-02", "file": "shortener/cli.py", "line": 71,
  "problem": "El subcomando stats se traga StorageError y devuelve ceros con salida 0. Esto contradice la sección 6.2 (errores de almacenamiento: 'error: storage: ...' y salida 3) y las reglas comunes (no tragarse errores)."},
 {"source": "qa", "id": "D1", "severity": "alta", "wp": "WP-02", "kind": "implementation",
  "repro": "Escribir '{no es json' en el --db y ejecutar `stats`: devuelve 0 con ceros, sin stderr, en vez de salida 3. Test: qa/test_qa_stats.py::test_d1_stats_con_fichero_corrupto_sale_3"}]"""),
}


def wrap(lines):
    out = []
    for line in lines:
        if len(line) <= WRAP:
            out.append(line)
            continue
        indent = len(line) - len(line.lstrip()) + 2
        parts = textwrap.wrap(line, WRAP, subsequent_indent=" " * indent, break_on_hyphens=False)
        out.extend(parts or [line])
    return out


def colour_runs(line):
    """[(text, colour, bold)] for one line, with simple, predictable highlighting."""
    s = line.lstrip()
    if s.startswith("$ ") or s.startswith("> "):
        return [(line[: len(line) - len(s)] + s[:2], "accent", True), (s[2:], "ink", True)]
    if s.startswith("# ") and not s.startswith("# Ledger"):
        return [(line, "grey", False)]
    if s.startswith("#"):
        return [(line, "ink", True)]
    runs, pos = [], 0
    for m in sorted(list(GREEN.finditer(line)) + list(RED.finditer(line)), key=lambda m: m.start()):
        if m.start() < pos:
            continue
        runs.append((line[pos:m.start()], "ink", False))
        runs.append((m.group(0), "ok" if GREEN.fullmatch(m.group(0)) else "err", True))
        pos = m.end()
    runs.append((line[pos:], "ink", False))
    return runs


def render(name, title, body):
    lines = wrap(body.splitlines())
    bar = 38
    h = bar + PAD + len(lines) * LINE + PAD - 6
    img = Image.new("RGB", ((WIDTH + 48) * SS, (h + 48) * SS), C["bg"])
    d = ImageDraw.Draw(img)
    x0, y0 = 24 * SS, 24 * SS
    d.rounded_rectangle((x0, y0, x0 + WIDTH * SS, y0 + h * SS), radius=12 * SS, fill=C["card"], outline=C["hair"],
                        width=SS)
    d.rounded_rectangle((x0, y0, x0 + WIDTH * SS, y0 + bar * SS), radius=12 * SS, fill=C["bar"])
    d.rectangle((x0, y0 + (bar - 12) * SS, x0 + WIDTH * SS, y0 + bar * SS), fill=C["bar"])
    d.line((x0, y0 + bar * SS, x0 + WIDTH * SS, y0 + bar * SS), fill=C["hair"], width=SS)
    for k in range(3):
        cx, cy = x0 + (20 + k * 16) * SS, y0 + bar // 2 * SS
        d.ellipse((cx - 5 * SS, cy - 5 * SS, cx + 5 * SS, cy + 5 * SS), fill=C["hair"])
    d.text((x0 + WIDTH * SS // 2, y0 + bar // 2 * SS), title, font=TITLE, fill=C["grey"], anchor="mm")
    y = y0 + (bar + PAD) * SS
    for line in lines:
        x = x0 + PAD * SS
        for text, colour, bold in colour_runs(line):
            f = MONO_B if bold else MONO
            d.text((x, y), text, font=f, fill=C[colour], anchor="ls")
            x += d.textlength(text, font=f)
        y += LINE * SS
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{name}.png"
    img.save(path, optimize=True)
    return path


if __name__ == "__main__":
    for name, (title, body) in SCREENS.items():
        p = render(name, title, body)
        print(f"{p} · {p.stat().st_size // 1024} KB")
