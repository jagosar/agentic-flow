#!/usr/bin/env python3
"""Guardarraíles y lanzador paralelo del flow agéntico.

Subcomandos:
  validate            Valida el manifiesto de architecture.md.
  snapshot N          Guarda el estado de los ficheros antes de la ola N.
  check-wave N        Comprueba que la ola N solo tocó ficheros de sus WP.
  run-wave N          Lanza en paralelo un `claude -p --agent implementer` por WP de la ola N.
  claim WP-ID         Asocia el subagente actual a un WP (lo registra el hook).
  hook                Hook PreToolUse (lee JSON por stdin).

El manifiesto es un bloque ```json wp-manifest``` dentro de architecture.md.
"""
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
ARCH = ROOT / "architecture.md"
STATE = ROOT / ".claude" / "state"
CLAIMS = STATE / "claims.json"
IMPLEMENTER_MODEL = os.environ.get("AGENTIC_IMPLEMENTER_MODEL", "claude-sonnet-5-5")
BASE_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]

MANIFEST_RE = re.compile(r"```json\s+wp-manifest\s*\n(.*?)\n```", re.S)
CLAIM_RE = re.compile(r"agentic\.py\s+claim\s+(WP-\d+)\b")
FORBIDDEN_BASH = [
    (re.compile(r"\bgit\s+(commit|push|checkout|switch|reset|rebase|merge|stash|branch|tag|restore|clean|cherry-pick|revert)\b"),
     "un WP no puede ejecutar operaciones de git que cambien historia, ramas o el árbol de trabajo"),
    (re.compile(r"\b(npm|pnpm|yarn|bun)\s+(install|i|add|remove|uninstall|rm)\b"),
     "un WP no puede cambiar dependencias (sección 3)"),
    (re.compile(r"\b(pip3?|uv\s+pip)\s+install\b|\buv\s+add\b|\bpoetry\s+add\b|\bcargo\s+add\b|\bgo\s+get\b"),
     "un WP no puede cambiar dependencias (sección 3)"),
    (re.compile(r"\bclaude\b.*\s-p\b|\bclaude\s+--print\b"),
     "un WP no puede lanzar otras sesiones de Claude"),
]


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


# ---------- manifiesto ----------

def load_manifest():
    if not ARCH.exists():
        die(f"No existe {ARCH}. Lanza /architect primero.")
    m = MANIFEST_RE.search(ARCH.read_text(encoding="utf-8"))
    if not m:
        die("architecture.md no tiene un bloque ```json wp-manifest```.")
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        die(f"El manifiesto no es JSON válido: {e}")
    return data


def wps(manifest):
    return {wp["id"]: wp for wp in manifest.get("work_packages", [])}


def owns(pattern, path):
    """Ruta exacta, o prefijo de directorio si el patrón acaba en '/'."""
    return path.startswith(pattern) if pattern.endswith("/") else path == pattern


def owner_conflict(a, b):
    if a == b:
        return True
    if a.endswith("/") and b.startswith(a):
        return True
    if b.endswith("/") and a.startswith(b):
        return True
    return False


def validate(manifest):
    errors = []
    table = wps(manifest)
    if not table:
        errors.append("El manifiesto no tiene work_packages.")
    for wp in table.values():
        for key in ("id", "wave", "files"):
            if key not in wp:
                errors.append(f"{wp.get('id', '?')}: falta el campo '{key}'.")
        for dep in wp.get("depends_on", []):
            if dep not in table:
                errors.append(f"{wp['id']}: depende de {dep}, que no existe.")
            elif table[dep]["wave"] >= wp["wave"]:
                errors.append(f"{wp['id']} (ola {wp['wave']}) depende de {dep} (ola {table[dep]['wave']}): debe ser de una ola anterior.")
        for f in wp.get("files", []):
            if f.startswith("/") or ".." in Path(f).parts:
                errors.append(f"{wp['id']}: ruta no relativa al repo: {f}")
            if f == "architecture.md" or f.startswith(".claude/"):
                errors.append(f"{wp['id']}: no puede poseer {f}.")
    owners = [(f, wp["id"]) for wp in table.values() for f in wp.get("files", [])]
    for i, (fa, wa) in enumerate(owners):
        for fb, wb in owners[i + 1:]:
            if wa != wb and owner_conflict(fa, fb):
                errors.append(f"Fichero con dos propietarios: {fa} ({wa}) y {fb} ({wb}).")
    for rule in manifest.get("allow_bash", []):
        if not re.fullmatch(r"Bash\(.+\)", rule):
            errors.append(f"allow_bash: regla mal formada: {rule}")
    return errors


# ---------- snapshot y comprobación de olas ----------

def tracked_files():
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"],
                         cwd=ROOT, capture_output=True, check=True).stdout
    return [p for p in out.decode().split("\0") if p and not p.startswith(".claude/state/")]


def digest():
    result = {}
    for rel in tracked_files():
        p = ROOT / rel
        if p.is_file():
            result[rel] = hashlib.sha1(p.read_bytes()).hexdigest()
    return result


def snapshot(wave):
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / f"snapshot-wave-{wave}.json").write_text(json.dumps(digest()))
    print(f"Snapshot de la ola {wave} guardado.")


def check_wave(manifest, wave):
    snap_file = STATE / f"snapshot-wave-{wave}.json"
    if not snap_file.exists():
        die(f"No hay snapshot de la ola {wave}. Ejecuta `snapshot {wave}` antes de lanzarla.")
    before = json.loads(snap_file.read_text())
    after = digest()
    changed = sorted({p for p in before.keys() | after.keys() if before.get(p) != after.get(p)})
    wave_wps = [wp for wp in wps(manifest).values() if wp["wave"] == wave]
    violations = []
    report = {wp["id"]: [] for wp in wave_wps}
    for path in changed:
        owner = next((wp["id"] for wp in wave_wps if any(owns(f, path) for f in wp["files"])), None)
        if owner:
            report[owner].append(path)
        else:
            violations.append(path)
    for wid, files in report.items():
        print(f"{wid}: {len(files)} fichero(s) cambiado(s)" + (": " + ", ".join(files) if files else ""))
    if violations:
        print("FUERA DE PROPIEDAD (ningún WP de esta ola posee estos ficheros):")
        for v in violations:
            print(f"  {v}")
        return False
    print(f"Ola {wave}: todos los cambios están dentro de sus WP.")
    return True


# ---------- lanzador paralelo ----------

def run_wave(manifest, wave):
    errors = validate(manifest)
    if errors:
        die("Manifiesto inválido:\n  " + "\n  ".join(errors))
    wave_wps = sorted((wp for wp in wps(manifest).values() if wp["wave"] == wave), key=lambda w: w["id"])
    if not wave_wps:
        die(f"No hay WP en la ola {wave}.")
    runs = STATE / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    snapshot(wave)

    allowed = BASE_TOOLS + manifest.get("allow_bash", []) + ["Bash(python3 .claude/bin/agentic.py claim:*)"]
    procs = {}
    for wp in wave_wps:
        wid = wp["id"]
        cmd = ["claude", "-p", f"Implementa {wid} según architecture.md.",
               "--agent", "implementer", "--model", IMPLEMENTER_MODEL,
               "--output-format", "json", "--permission-mode", "acceptEdits",
               "--allowedTools", *allowed]
        env = dict(os.environ, AGENTIC_WP=wid, CLAUDE_PROJECT_DIR=str(ROOT))
        out = open(runs / f"{wid}.json", "w")
        err = open(runs / f"{wid}.log", "w")
        procs[wid] = (subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=out, stderr=err, stdin=subprocess.DEVNULL), out, err)
        print(f"Lanzado {wid} (pid {procs[wid][0].pid})", flush=True)

    start = time.time()
    statuses = {}
    for wid, (proc, out, err) in procs.items():
        proc.wait()
        out.close()
        err.close()
        statuses[wid] = parse_status(runs / f"{wid}.json", proc.returncode)
        print(f"{wid}: {statuses[wid]} ({int(time.time() - start)}s)", flush=True)

    ownership_ok = check_wave(manifest, wave)
    print("\nRESUMEN OLA", wave)
    for wid, st in statuses.items():
        print(f"  {wid}: {st}   informe: .claude/state/runs/{wid}.json")
    ok = ownership_ok and all(s == "DONE" for s in statuses.values())
    print("RESULTADO:", "OK" if ok else "REVISAR")
    sys.exit(0 if ok else 3)


def parse_status(path, returncode):
    try:
        result = json.loads(path.read_text()).get("result", "")
    except (json.JSONDecodeError, OSError):
        return f"ERROR (exit {returncode}, sin salida JSON)"
    m = re.search(r"STATUS:\s*(DONE|BLOCKER)", result)
    return m.group(1) if m else f"SIN INFORME (exit {returncode})"


# ---------- hook PreToolUse ----------

def locked_claims(update=None):
    STATE.mkdir(parents=True, exist_ok=True)
    with open(CLAIMS, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        raw = fh.read()
        claims = json.loads(raw) if raw.strip() else {}
        if update:
            claims.update(update)
            fh.seek(0)
            fh.truncate()
            fh.write(json.dumps(claims, indent=2))
        return claims


def block(msg):
    print(f"[agentic guard] {msg}", file=sys.stderr)
    sys.exit(2)


def hook():
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    tinput = data.get("tool_input", {}) or {}
    agent_id = data.get("agent_id")
    wp_id = os.environ.get("AGENTIC_WP")

    if tool == "Bash" and agent_id:
        m = CLAIM_RE.search(tinput.get("command", ""))
        if m:
            locked_claims({agent_id: m.group(1)})
            sys.exit(0)

    if not wp_id and agent_id:
        wp_id = locked_claims().get(agent_id)
        if not wp_id and data.get("agent_type") == "implementer":
            block("Antes de nada, ejecuta `python3 .claude/bin/agentic.py claim <WP-ID>` con tu WP.")
    if not wp_id:
        sys.exit(0)  # hilo principal u otro subagente: sin restricciones de WP

    if tool == "Bash":
        cmd = tinput.get("command", "")
        for rx, why in FORBIDDEN_BASH:
            if rx.search(cmd):
                block(f"{wp_id}: comando bloqueado, {why}: {cmd}")
        sys.exit(0)

    path = tinput.get("file_path") or tinput.get("notebook_path")
    if not path:
        sys.exit(0)
    abs_path = Path(path) if os.path.isabs(path) else Path(data.get("cwd") or ROOT) / path
    try:
        rel = abs_path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        block(f"{wp_id}: no puedes escribir fuera del repo: {path}")
    wp = wps(load_manifest()).get(wp_id)
    if not wp:
        block(f"{wp_id} no existe en el manifiesto de architecture.md.")
    if not any(owns(f, rel) for f in wp["files"]):
        block(f"{wp_id} no posee {rel}. Ficheros permitidos: {', '.join(wp['files'])}. "
              "Si necesitas tocarlo, devuelve STATUS: BLOCKER.")
    sys.exit(0)


# ---------- CLI ----------

def main():
    if len(sys.argv) < 2:
        die(__doc__)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "hook":
        hook()
    elif cmd == "claim":
        if not args:
            die("Uso: claim WP-ID")
        print(f"{args[0]} reclamado." if os.environ.get("AGENTIC_WP") or args[0] in locked_claims().values()
              else f"Aviso: el hook no registró {args[0]}. ¿Están activos los hooks de .claude/settings.json?")
    elif cmd == "validate":
        errors = validate(load_manifest())
        if errors:
            die("Manifiesto inválido:\n  " + "\n  ".join(errors))
        print("Manifiesto válido.")
    elif cmd in ("snapshot", "check-wave", "run-wave"):
        if not args or not args[0].isdigit():
            die(f"Uso: {cmd} N")
        wave = int(args[0])
        if cmd == "snapshot":
            snapshot(wave)
        elif cmd == "check-wave":
            sys.exit(0 if check_wave(load_manifest(), wave) else 3)
        else:
            run_wave(load_manifest(), wave)
    else:
        die(__doc__)


if __name__ == "__main__":
    main()
