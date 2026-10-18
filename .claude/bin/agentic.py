#!/usr/bin/env python3
"""Guardarraíles y lanzador paralelo del flow agéntico.

Subcomandos:
  validate            Valida el manifiesto de architecture.md.
  snapshot L          Guarda el estado de los ficheros antes de la etapa L (número de ola o "qa").
  check-wave L        Comprueba que la etapa L solo tocó ficheros de sus propietarios.
  run-wave N [WP...] [--fix]
                      Lanza en paralelo un `claude -p --agent implementer` por WP de la ola N (o solo
                      los WP indicados). Con --fix, les pide corregir sus defectos del último informe de QA.
  run-qa              Lanza el agente QA (`claude -p --agent qa`) sobre el resultado integrado.
  claim ID            Asocia el subagente actual a un WP o a QA (lo registra el hook).
  hook                Hook PreToolUse (lee JSON por stdin).

El manifiesto es un bloque ```json wp-manifest``` dentro de architecture.md.
Timeout y autenticación del lanzador: .claude/agentic.json (opcional) y variables AGENTIC_*.
"""
import fcntl
import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
ARCH = ROOT / "architecture.md"
STATE = ROOT / ".claude" / "state"
CLAIMS = STATE / "claims.json"
CONFIG = ROOT / ".claude" / "agentic.json"
BASE_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]
QA_DEFAULT_FILES = ["qa/"]
# Todos los agentes orquestados (implementadores y QA) usan siempre el último Sonnet. `sonnet` es el alias
# que Claude Code resuelve al Sonnet más reciente que conoce; no se puede cambiar por config ni por entorno.
WORKER_MODEL = "sonnet"
# El arquitecto usa siempre el último Opus (alias `opus`, en el frontmatter de /architect).
ARCHITECT_MODEL = "opus"
DEFAULT_CONFIG = {
    "timeout_s": 1800,
    # "subscription": los agentes usan tu sesión de Claude (suscripción) aunque haya una API key en el entorno.
    # "inherit": heredan el entorno tal cual (útil en CI con API key).
    "auth": "subscription",
}
# Variables que harían que un agente facturase contra la API en vez de contra la suscripción.
API_AUTH_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
# Cachés y artefactos que generan las herramientas de test y build: no cuentan como cambios.
DEFAULT_IGNORE = ["__pycache__/", "*.pyc", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/",
                  "node_modules/", ".coverage", "coverage/", ".nyc_output/", ".DS_Store", ".tsbuildinfo"]

MANIFEST_RE = re.compile(r"```json\s+wp-manifest\s*\n(.*?)\n```", re.S)
CLAIM_RE = re.compile(r"agentic\.py\s+claim\s+(WP-\d+|QA)\b")
STATUS_RE = re.compile(r"STATUS:\s*(DONE|BLOCKER|PASS|FAIL)")
# Un subcomando de escritura en el mismo comando que `git`, aunque haya opciones delante (`git -C . commit`)
# o vaya dentro de comillas (`sh -c "git commit"`). Exige espacio antes para no confundir `src/add.py`.
GIT_WRITE_RE = re.compile(
    r"\bgit\b[^;&|\n]*?\s[\"']?(commit|push|pull|fetch|checkout|switch|reset|rebase|merge|stash|branch|tag|restore|"
    r"clean|cherry-pick|revert|am|apply|config|remote|worktree|update-ref|update-index|filter-branch|gc|rm|mv|add|"
    r"submodule)(?=$|[\s\"';&|])")
FORBIDDEN_BASH = [
    (GIT_WRITE_RE, "no se pueden ejecutar operaciones de git que escriban (solo status, diff, log, show)"),
    (re.compile(r"\b(npm|pnpm|yarn|bun)\s+(install|i|add|remove|uninstall|rm|ci)\b"),
     "no se pueden cambiar dependencias (sección 3)"),
    (re.compile(r"\b(pip3?|uv\s+pip)\s+install\b|\buv\s+(add|sync)\b|\bpoetry\s+(add|install)\b|\bcargo\s+add\b|\bgo\s+get\b"),
     "no se pueden cambiar dependencias (sección 3)"),
    (re.compile(r"\bclaude\b(?=.*(\s-p\b|\s--print\b))", re.S),
     "no se pueden lanzar otras sesiones de Claude"),
]
# Primer token de una regla allow_bash que daría ejecución arbitraria si va solo.
OPEN_ENDED = {"bash", "sh", "zsh", "fish", "dash", "python", "python3", "node", "deno", "bun", "ruby", "perl",
              "php", "env", "xargs", "sudo", "eval", "exec", "npx", "npm", "pnpm", "yarn", "uv", "poetry",
              "cargo", "go", "make", "git", "claude", "find", "awk", "sed"}


class ManifestError(Exception):
    pass


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


# ---------- configuración ----------

def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if CONFIG.exists():
        user = json.loads(CONFIG.read_text(encoding="utf-8"))
        for key, value in user.items():
            if isinstance(value, dict) and isinstance(cfg.get(key), dict):
                cfg[key].update(value)
            else:
                cfg[key] = value
    env = os.environ
    if "AGENTIC_TIMEOUT_S" in env:
        cfg["timeout_s"] = int(env["AGENTIC_TIMEOUT_S"])
    return cfg


# ---------- manifiesto ----------

def load_manifest():
    if not ARCH.exists():
        raise ManifestError(f"No existe {ARCH}. Lanza /architect primero.")
    m = MANIFEST_RE.search(ARCH.read_text(encoding="utf-8"))
    if not m:
        raise ManifestError("architecture.md no tiene un bloque ```json wp-manifest```.")
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise ManifestError(f"El manifiesto no es JSON válido: {e}")
    if not isinstance(data, dict):
        raise ManifestError("El manifiesto debe ser un objeto JSON.")
    return data


def wps(manifest):
    return {wp["id"]: wp for wp in manifest.get("work_packages", []) if isinstance(wp, dict) and "id" in wp}


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


def ignored(path, patterns):
    parts = path.split("/")
    for pat in patterns:
        if pat.endswith("/"):
            if pat[:-1] in parts[:-1] or path.startswith(pat):
                return True
        elif fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(parts[-1], pat):
            return True
    return False


def open_ended_rule(rule):
    inner = rule[len("Bash("):-1].strip()
    prefix = inner[:-2] if inner.endswith(":*") else inner
    tokens = prefix.split()
    return inner in ("*", ":*", "") or not tokens or "*" in prefix or (len(tokens) == 1 and tokens[0] in OPEN_ENDED)


def validate(manifest):
    errors = []
    table = wps(manifest)
    if not table:
        errors.append("El manifiesto no tiene work_packages.")
    if "QA" in table:
        errors.append("'QA' es un ID reservado.")
    seen = set()
    for wp in manifest.get("work_packages", []):
        if not isinstance(wp, dict) or "id" not in wp:
            errors.append(f"Work package sin id: {wp}")
            continue
        if wp["id"] in seen:
            errors.append(f"{wp['id']}: ID duplicado.")
        seen.add(wp["id"])
        if not re.fullmatch(r"WP-\d+", wp["id"]):
            errors.append(f"{wp['id']}: el ID debe tener la forma WP-<número>.")
        for key in ("wave", "files"):
            if key not in wp:
                errors.append(f"{wp['id']}: falta el campo '{key}'.")
        if not isinstance(wp.get("wave", 0), int):
            errors.append(f"{wp['id']}: 'wave' debe ser un entero.")
        for dep in wp.get("depends_on", []):
            if dep not in table:
                errors.append(f"{wp['id']}: depende de {dep}, que no existe.")
            elif table[dep].get("wave", 0) >= wp.get("wave", 0):
                errors.append(f"{wp['id']} (ola {wp.get('wave')}) depende de {dep} (ola {table[dep].get('wave')}): debe ser de una ola anterior.")
    for ent in entities(manifest).values():
        for f in ent.get("files", []):
            if f.startswith("/") or ".." in Path(f).parts:
                errors.append(f"{ent['id']}: ruta no relativa al repo: {f}")
            if f == "architecture.md" or f.startswith(".claude/") or f in ("", "./", "/"):
                errors.append(f"{ent['id']}: no puede poseer '{f}'.")
    owners = [(f, e["id"]) for e in entities(manifest).values() for f in e.get("files", [])]
    for i, (fa, wa) in enumerate(owners):
        for fb, wb in owners[i + 1:]:
            if wa != wb and owner_conflict(fa, fb):
                errors.append(f"Fichero con dos propietarios: {fa} ({wa}) y {fb} ({wb}).")
    for rule in manifest.get("allow_bash", []) + qa_entity(manifest)["allow_bash"]:
        if not re.fullmatch(r"Bash\(.+\)", rule):
            errors.append(f"allow_bash: regla mal formada: {rule}")
        elif open_ended_rule(rule):
            errors.append(f"allow_bash: regla demasiado amplia (daría ejecución arbitraria): {rule}. "
                          "Usa el comando concreto, p. ej. Bash(npm test:*) o Bash(python3 -m pytest:*).")
    if not isinstance(manifest.get("ignore", []), list):
        errors.append("'ignore' debe ser una lista de patrones.")
    errors += agent_model_errors(manifest)
    return errors


FRONTMATTER_MODEL_RE = re.compile(r"\A---\s*\n(.*?)\n---", re.S)


def frontmatter_model(path):
    fm = FRONTMATTER_MODEL_RE.match(path.read_text(encoding="utf-8"))
    if not fm:
        return None
    m = re.search(r"^model:\s*(\S+)\s*$", fm.group(1), re.M)
    return m.group(1).strip("\"'") if m else None


def agent_model_errors(manifest):
    """Agentes orquestados en el último Sonnet y arquitecto en el último Opus, declarados con su alias."""
    errors = []
    names = {"implementer", "qa"} | {wp.get("agent", "implementer") for wp in wps(manifest).values()}
    for name in sorted(names):
        f = ROOT / ".claude" / "agents" / f"{name}.md"
        if not f.exists():
            errors.append(f"Agente '{name}': no existe {f.relative_to(ROOT)}.")
            continue
        model = frontmatter_model(f)
        if model != WORKER_MODEL:
            errors.append(f"Agente '{name}': su frontmatter debe decir 'model: {WORKER_MODEL}' (el último Sonnet), "
                          f"no '{model}'.")
    architect = ROOT / ".claude" / "commands" / "architect.md"
    if architect.exists() and frontmatter_model(architect) != ARCHITECT_MODEL:
        errors.append(f"/architect: su frontmatter debe decir 'model: {ARCHITECT_MODEL}' (el último Opus), "
                      f"no '{frontmatter_model(architect)}'.")
    return errors


def require_valid():
    try:
        manifest = load_manifest()
    except ManifestError as e:
        die(str(e))
    errors = validate(manifest)
    if errors:
        die("Manifiesto inválido:\n  " + "\n  ".join(errors))
    return manifest


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
    CLAIMS.unlink(missing_ok=True)  # cada etapa empieza sin reclamaciones
    print(f"Snapshot de la etapa {label} guardado.")


def check_stage(manifest, label):
    snap_file = STATE / f"snapshot-{label}.json"
    if not snap_file.exists():
        die(f"No hay snapshot de la etapa {label}. Ejecuta `snapshot {label}` antes de lanzarla.")
    before = json.loads(snap_file.read_text())
    after = digest()
    patterns = DEFAULT_IGNORE + manifest.get("ignore", [])
    changed = sorted(p for p in before.keys() | after.keys()
                     if before.get(p) != after.get(p) and not ignored(p, patterns))
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

def child_env(cfg, **extra):
    env = dict(os.environ, **extra)
    if cfg.get("auth", "subscription") == "subscription":
        for var in API_AUTH_VARS:
            env.pop(var, None)
    return env


def launch(label, jobs, cfg):
    """jobs: lista de (id, agent, prompt, allowed). Los lanza todos a la vez y espera."""
    runs = STATE / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    snapshot(label)
    procs = {}
    for jid, agent, prompt, allowed in jobs:
        cmd = ["claude", "-p", prompt, "--agent", agent, "--model", WORKER_MODEL,
               "--output-format", "json", "--permission-mode", "acceptEdits",
               "--strict-mcp-config",  # sin conectores MCP: un WP solo necesita el repo
               "--allowedTools", *allowed, "Bash(python3 .claude/bin/agentic.py claim:*)"]
        env = child_env(cfg, AGENTIC_WP=jid, CLAUDE_PROJECT_DIR=str(ROOT))
        out = open(runs / f"{jid}.json", "w")
        err = open(runs / f"{jid}.log", "w")
        proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=out, stderr=err, stdin=subprocess.DEVNULL)
        procs[jid] = (proc, out, err)
        print(f"Lanzado {jid} [{agent}, {WORKER_MODEL}] (pid {proc.pid})", flush=True)

    start = time.time()
    deadline = start + cfg["timeout_s"]
    statuses = {}
    for jid, (proc, out, err) in procs.items():
        try:
            proc.wait(timeout=max(0, deadline - time.time()))
            timed_out = False
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            timed_out = True
        out.close()
        err.close()
        statuses[jid] = (f"TIMEOUT ({cfg['timeout_s']}s)" if timed_out
                         else parse_status(runs / f"{jid}.json", proc.returncode))
        print(f"{jid}: {statuses[jid]} ({int(time.time() - start)}s)", flush=True)
    return statuses


def run_wave(manifest, wave, only=None, fix=False):
    cfg = load_config()
    wave_wps = sorted(stage_owners(manifest, wave), key=lambda w: w["id"])
    if only:
        unknown = set(only) - {wp["id"] for wp in wave_wps}
        if unknown:
            die(f"No son de la ola {wave}: {', '.join(sorted(unknown))}")
        wave_wps = [wp for wp in wave_wps if wp["id"] in only]
    if not wave_wps:
        die(f"No hay WP en la ola {wave}.")
    allowed = BASE_TOOLS + manifest.get("allow_bash", [])
    if fix and not (STATE / "runs" / "QA.json").exists():
        die("--fix necesita un informe de QA (.claude/state/runs/QA.json). Ejecuta run-qa antes.")
    prompt = "Implementa {id} según architecture.md." + (
        " El código ya existe: corrige los defectos de .claude/state/runs/QA.json que te asignan, sin salirte del contrato."
        if fix else "")
    statuses = launch(str(wave), [
        (wp["id"], wp.get("agent", "implementer"), prompt.format(id=wp["id"]),
         allowed)
        for wp in wave_wps], cfg)
    finish(manifest, str(wave), statuses, "DONE")


def run_qa(manifest):
    cfg = load_config()
    qa = qa_entity(manifest)
    allowed = BASE_TOOLS + manifest.get("allow_bash", []) + qa["allow_bash"]
    statuses = launch("qa", [("QA", "qa",
                              "Ejecuta la validación QA del sistema según architecture.md.",
                              allowed)], cfg)
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
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return f"ERROR (exit {returncode}, sin salida JSON)"
    m = STATUS_RE.search(data.get("result") or "")
    if m:
        return m.group(1)
    return f"SIN INFORME ({data.get('subtype') or 'exit ' + str(returncode)})"


# ---------- hook PreToolUse ----------

def with_claims(fn):
    """Ejecuta fn(claims) con el fichero de reclamaciones bloqueado; si devuelve un dict, lo guarda."""
    STATE.mkdir(parents=True, exist_ok=True)
    with open(CLAIMS, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        raw = fh.read()
        claims = json.loads(raw) if raw.strip() else {}
        new = fn(claims)
        if new is not None:
            fh.seek(0)
            fh.truncate()
            fh.write(json.dumps(new, indent=2))
        return claims


def block(msg):
    print(f"[agentic guard] {msg}", file=sys.stderr)
    sys.exit(2)


def claim(agent_id, wanted):
    if wanted not in entities(load_manifest()):
        block(f"{wanted} no existe en el manifiesto.")
    conflict = {}

    def update(claims):
        current = claims.get(agent_id)
        holder = next((a for a, w in claims.items() if w == wanted and a != agent_id), None)
        if current and current != wanted:
            conflict["msg"] = f"este agente ya reclamó {current}; no puede reclamar también {wanted}."
        elif holder:
            conflict["msg"] = f"{wanted} ya lo reclamó otro agente en esta etapa."
        else:
            return dict(claims, **{agent_id: wanted})
        return None

    with_claims(update)
    if conflict:
        block(conflict["msg"])


def guard(data):
    tool = data.get("tool_name", "")
    tinput = data.get("tool_input", {}) or {}
    agent_id = data.get("agent_id")
    owner_id = os.environ.get("AGENTIC_WP")

    if tool == "Bash" and agent_id and not owner_id:
        m = CLAIM_RE.search(tinput.get("command", ""))
        if m:
            claim(agent_id, m.group(1))
            return

    if not owner_id and agent_id:
        owner_id = with_claims(lambda c: None).get(agent_id)
        if not owner_id and data.get("agent_type") in ("implementer", "qa"):
            block("Antes de nada, ejecuta `python3 .claude/bin/agentic.py claim <ID>` con tu WP-ID (o QA).")
    if not owner_id:
        return  # hilo principal u otro subagente: sin restricciones

    if tool == "Bash":
        cmd = tinput.get("command", "")
        for rx, why in FORBIDDEN_BASH:
            if rx.search(cmd):
                block(f"{owner_id}: comando bloqueado, {why}: {cmd}")
        return

    path = tinput.get("file_path") or tinput.get("notebook_path")
    if not path:
        return
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


def hook():
    """Falla cerrado: cualquier error dentro de un WP o de QA bloquea la herramienta."""
    restricted = bool(os.environ.get("AGENTIC_WP"))
    try:
        data = json.load(sys.stdin)
        restricted = restricted or bool(data.get("agent_id"))
        guard(data)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 - cualquier fallo es motivo de bloqueo
        if restricted:
            block(f"error del guardarraíl, bloqueo por seguridad: {type(e).__name__}: {e}")
        print(f"[agentic guard] aviso: {type(e).__name__}: {e}", file=sys.stderr)
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
        registered = os.environ.get("AGENTIC_WP") or args[0] in with_claims(lambda c: None).values()
        print(f"{args[0]} reclamado." if registered
              else f"Aviso: el hook no registró {args[0]}. ¿Están activos los hooks de .claude/settings.json?")
    elif cmd == "validate":
        require_valid()
        print("Manifiesto válido.")
    elif cmd == "run-qa":
        run_qa(require_valid())
    elif cmd in ("snapshot", "check-wave", "run-wave"):
        if not args or not (args[0].isdigit() or (args[0] == "qa" and cmd != "run-wave")):
            die(f"Uso: {cmd} N" + ("" if cmd == "run-wave" else " | qa"))
        label = args[0]
        if cmd == "snapshot":
            snapshot(label)
        elif cmd == "check-wave":
            sys.exit(0 if check_stage(require_valid(), label) else 3)
        else:
            rest = args[1:]
            run_wave(require_valid(), int(label), only=[a for a in rest if a != "--fix"], fix="--fix" in rest)
    else:
        die(__doc__)


if __name__ == "__main__":
    main()
