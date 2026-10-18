#!/usr/bin/env python3
"""Guardarraíles y lanzador paralelo del flow agéntico.

Subcomandos:
  validate            Valida el manifiesto de architecture.md.
  snapshot L          Guarda el estado de los ficheros antes de la etapa L (número de ola o "qa").
  check-wave L        Comprueba que la etapa L solo tocó ficheros de sus propietarios.
  run-wave N [WP...]  Lanza en paralelo un `claude -p --agent implementer` por WP de la ola N
                      (o solo los WP indicados, p. ej. para corregir defectos de QA).
  run-qa              Lanza el agente QA (`claude -p --agent qa`) sobre el resultado integrado.
  claim ID            Asocia el subagente actual a un WP o a QA (lo registra el hook).
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
QA_MODEL = os.environ.get("AGENTIC_QA_MODEL", "claude-opus-5-5")
BASE_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]
QA_DEFAULT_FILES = ["qa/"]

MANIFEST_RE = re.compile(r"```json\s+wp-manifest\s*\n(.*?)\n```", re.S)
CLAIM_RE = re.compile(r"agentic\.py\s+claim\s+(WP-\d+|QA)\b")
STATUS_RE = re.compile(r"STATUS:\s*(DONE|BLOCKER|PASS|FAIL)")
FORBIDDEN_BASH = [
    (re.compile(r"\bgit\s+(commit|push|checkout|switch|reset|rebase|merge|stash|branch|tag|restore|clean|cherry-pick|revert)\b"),
     "no se pueden ejecutar operaciones de git que cambien historia, ramas o el árbol de trabajo"),
    (re.compile(r"\b(npm|pnpm|yarn|bun)\s+(install|i|add|remove|uninstall|rm)\b"),
     "no se pueden cambiar dependencias (sección 3)"),
    (re.compile(r"\b(pip3?|uv\s+pip)\s+install\b|\buv\s+add\b|\bpoetry\s+add\b|\bcargo\s+add\b|\bgo\s+get\b"),
     "no se pueden cambiar dependencias (sección 3)"),
    (re.compile(r"\bclaude\b.*\s-p\b|\bclaude\s+--print\b"),
     "no se pueden lanzar otras sesiones de Claude"),
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
        return json.loads(m.group(1))
    except json.JSONDecodeError as e:
        die(f"El manifiesto no es JSON válido: {e}")


def wps(manifest):
    return {wp["id"]: wp for wp in manifest.get("work_packages", [])}


def qa_entity(manifest):
    qa = manifest.get("qa", {})
    return {"id": "QA", "files": qa.get("files", QA_DEFAULT_FILES), "allow_bash": qa.get("allow_bash", [])}


def entities(manifest):
    """Todo lo que puede reclamar propiedad de ficheros: los WP y QA."""
    table = wps(manifest)
    table["QA"] = qa_entity(manifest)
    return table


def owns(pattern, path):
    """Ruta exacta, o prefijo de directorio si el patrón acaba en '/'."""
    return path.startswith(pattern) if pattern.endswith("/") else path == pattern


def owner_conflict(a, b):
    return a == b or (a.endswith("/") and b.startswith(a)) or (b.endswith("/") and a.startswith(b))


def validate(manifest):
    errors = []
    table = wps(manifest)
    if not table:
        errors.append("El manifiesto no tiene work_packages.")
    if "QA" in table:
        errors.append("'QA' es un ID reservado.")
    for wp in table.values():
        for key in ("id", "wave", "files"):
            if key not in wp:
                errors.append(f"{wp.get('id', '?')}: falta el campo '{key}'.")
        for dep in wp.get("depends_on", []):
            if dep not in table:
                errors.append(f"{wp['id']}: depende de {dep}, que no existe.")
            elif table[dep]["wave"] >= wp["wave"]:
                errors.append(f"{wp['id']} (ola {wp['wave']}) depende de {dep} (ola {table[dep]['wave']}): debe ser de una ola anterior.")
    for ent in entities(manifest).values():
        for f in ent.get("files", []):
            if f.startswith("/") or ".." in Path(f).parts:
                errors.append(f"{ent['id']}: ruta no relativa al repo: {f}")
            if f == "architecture.md" or f.startswith(".claude/"):
                errors.append(f"{ent['id']}: no puede poseer {f}.")
    owners = [(f, e["id"]) for e in entities(manifest).values() for f in e.get("files", [])]
    for i, (fa, wa) in enumerate(owners):
        for fb, wb in owners[i + 1:]:
            if wa != wb and owner_conflict(fa, fb):
                errors.append(f"Fichero con dos propietarios: {fa} ({wa}) y {fb} ({wb}).")
    for rule in manifest.get("allow_bash", []) + qa_entity(manifest)["allow_bash"]:
        if not re.fullmatch(r"Bash\(.+\)", rule):
            errors.append(f"allow_bash: regla mal formada: {rule}")
    return errors


def require_valid(manifest):
    errors = validate(manifest)
    if errors:
        die("Manifiesto inválido:\n  " + "\n  ".join(errors))


# ---------- snapshot y comprobación de etapas ----------

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


def stage_owners(manifest, label):
    if label == "qa":
        return [qa_entity(manifest)]
    return [wp for wp in wps(manifest).values() if wp["wave"] == int(label)]


def snapshot(label):
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / f"snapshot-{label}.json").write_text(json.dumps(digest()))
    print(f"Snapshot de la etapa {label} guardado.")


def check_stage(manifest, label):
    snap_file = STATE / f"snapshot-{label}.json"
    if not snap_file.exists():
        die(f"No hay snapshot de la etapa {label}. Ejecuta `snapshot {label}` antes de lanzarla.")
    before = json.loads(snap_file.read_text())
    after = digest()
    changed = sorted({p for p in before.keys() | after.keys() if before.get(p) != after.get(p)})
    owners = stage_owners(manifest, label)
    report = {o["id"]: [] for o in owners}
    violations = []
    for path in changed:
        owner = next((o["id"] for o in owners if any(owns(f, path) for f in o["files"])), None)
        (report[owner] if owner else violations).append(path)
    for oid, files in report.items():
        print(f"{oid}: {len(files)} fichero(s) cambiado(s)" + (": " + ", ".join(files) if files else ""))
    if violations:
        print("FUERA DE PROPIEDAD (ningún propietario de esta etapa posee estos ficheros):")
        for v in violations:
            print(f"  {v}")
        return False
    print(f"Etapa {label}: todos los cambios están dentro de sus propietarios.")
    return True


# ---------- lanzadores ----------

def launch(label, jobs):
    """jobs: lista de (id, agent, model, prompt, allowed). Los lanza todos a la vez y espera."""
    runs = STATE / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    snapshot(label)
    procs = {}
    for jid, agent, model, prompt, allowed in jobs:
        cmd = ["claude", "-p", prompt, "--agent", agent, "--model", model,
               "--output-format", "json", "--permission-mode", "acceptEdits",
               "--strict-mcp-config",  # sin conectores MCP: un WP solo necesita el repo
               "--allowedTools", *allowed, "Bash(python3 .claude/bin/agentic.py claim:*)"]
        env = dict(os.environ, AGENTIC_WP=jid, CLAUDE_PROJECT_DIR=str(ROOT))
        out = open(runs / f"{jid}.json", "w")
        err = open(runs / f"{jid}.log", "w")
        proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=out, stderr=err, stdin=subprocess.DEVNULL)
        procs[jid] = (proc, out, err)
        print(f"Lanzado {jid} [{agent}, {model}] (pid {proc.pid})", flush=True)

    start = time.time()
    statuses = {}
    for jid, (proc, out, err) in procs.items():
        proc.wait()
        out.close()
        err.close()
        statuses[jid] = parse_status(runs / f"{jid}.json", proc.returncode)
        print(f"{jid}: {statuses[jid]} ({int(time.time() - start)}s)", flush=True)
    return statuses


def run_wave(manifest, wave, only=None):
    require_valid(manifest)
    wave_wps = sorted(stage_owners(manifest, wave), key=lambda w: w["id"])
    if only:
        unknown = set(only) - {wp["id"] for wp in wave_wps}
        if unknown:
            die(f"No son de la ola {wave}: {', '.join(sorted(unknown))}")
        wave_wps = [wp for wp in wave_wps if wp["id"] in only]
    if not wave_wps:
        die(f"No hay WP en la ola {wave}.")
    allowed = BASE_TOOLS + manifest.get("allow_bash", [])
    prompt = "Implementa {id} según architecture.md." + (
        " El código ya existe: corrige los defectos de .claude/state/runs/QA.json que te asignan, sin salirte del contrato."
        if only and (STATE / "runs" / "QA.json").exists() else "")
    statuses = launch(str(wave), [
        (wp["id"], wp.get("agent", "implementer"), IMPLEMENTER_MODEL, prompt.format(id=wp["id"]), allowed)
        for wp in wave_wps])
    finish(manifest, str(wave), statuses, "DONE")


def run_qa(manifest):
    require_valid(manifest)
    qa = qa_entity(manifest)
    allowed = BASE_TOOLS + manifest.get("allow_bash", []) + qa["allow_bash"]
    statuses = launch("qa", [("QA", "qa", QA_MODEL,
                              "Ejecuta la validación QA del sistema según architecture.md.", allowed)])
    finish(manifest, "qa", statuses, "PASS")


def finish(manifest, label, statuses, expected):
    ownership_ok = check_stage(manifest, label)
    print(f"\nRESUMEN ETAPA {label}")
    for jid, st in statuses.items():
        print(f"  {jid}: {st}   informe: .claude/state/runs/{jid}.json")
    ok = ownership_ok and all(s == expected for s in statuses.values())
    print("RESULTADO:", "OK" if ok else "REVISAR")
    sys.exit(0 if ok else 3)


def parse_status(path, returncode):
    try:
        result = json.loads(path.read_text()).get("result", "")
    except (json.JSONDecodeError, OSError):
        return f"ERROR (exit {returncode}, sin salida JSON)"
    m = STATUS_RE.search(result)
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
    owner_id = os.environ.get("AGENTIC_WP")

    if tool == "Bash" and agent_id:
        m = CLAIM_RE.search(tinput.get("command", ""))
        if m:
            locked_claims({agent_id: m.group(1)})
            sys.exit(0)

    if not owner_id and agent_id:
        owner_id = locked_claims().get(agent_id)
        if not owner_id and data.get("agent_type") in ("implementer", "qa"):
            block("Antes de nada, ejecuta `python3 .claude/bin/agentic.py claim <ID>` con tu WP-ID (o QA).")
    if not owner_id:
        sys.exit(0)  # hilo principal u otro subagente: sin restricciones

    if tool == "Bash":
        cmd = tinput.get("command", "")
        for rx, why in FORBIDDEN_BASH:
            if rx.search(cmd):
                block(f"{owner_id}: comando bloqueado, {why}: {cmd}")
        sys.exit(0)

    path = tinput.get("file_path") or tinput.get("notebook_path")
    if not path:
        sys.exit(0)
    abs_path = Path(path) if os.path.isabs(path) else Path(data.get("cwd") or ROOT) / path
    try:
        rel = abs_path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        block(f"{owner_id}: no puedes escribir fuera del repo: {path}")
    ent = entities(load_manifest()).get(owner_id)
    if not ent:
        block(f"{owner_id} no existe en el manifiesto de architecture.md.")
    if not any(owns(f, rel) for f in ent["files"]):
        block(f"{owner_id} no posee {rel}. Ficheros permitidos: {', '.join(ent['files'])}. "
              "Si necesitas tocarlo, devuelve STATUS: BLOCKER (o, si eres QA, repórtalo como defecto).")
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
            die("Uso: claim ID")
        print(f"{args[0]} reclamado." if os.environ.get("AGENTIC_WP") or args[0] in locked_claims().values()
              else f"Aviso: el hook no registró {args[0]}. ¿Están activos los hooks de .claude/settings.json?")
    elif cmd == "validate":
        require_valid(load_manifest())
        print("Manifiesto válido.")
    elif cmd == "run-qa":
        run_qa(load_manifest())
    elif cmd in ("snapshot", "check-wave", "run-wave"):
        if not args or not (args[0].isdigit() or (args[0] == "qa" and cmd != "run-wave")):
            die(f"Uso: {cmd} N" + ("" if cmd == "run-wave" else " | qa"))
        label = args[0]
        if cmd == "snapshot":
            snapshot(label)
        elif cmd == "check-wave":
            sys.exit(0 if check_stage(load_manifest(), label) else 3)
        else:
            run_wave(load_manifest(), int(label), only=args[1:])
    else:
        die(__doc__)


if __name__ == "__main__":
    main()
