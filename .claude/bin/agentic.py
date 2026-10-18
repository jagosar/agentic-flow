#!/usr/bin/env python3
"""Guardarraíles y lanzador paralelo del flow agéntico.

Subcomandos:
  validate            Valida el manifiesto de architecture.md.
  snapshot L          Guarda el estado de los ficheros antes de la etapa L (número de ola o "qa").
  check-wave L        Comprueba que la etapa L solo tocó ficheros de sus propietarios.
  run-wave N [WP...] [--fix]
                      Lanza en paralelo un `claude -p --agent implementer` por WP de la ola N (o solo
                      los WP indicados). Con --fix, les pide corregir sus defectos del último informe de QA.
  pipeline-plan       JSON con olas, WP, aceptación, tipo, fases de verify y tope de fix (workflow).
  open-stage L        Snapshot de la etapa L (ola, acceptance, review, qa) y sus propietarios en JSON.
  close-stage L ID=estado... [--expect red|green] [--fix]
                      Propiedad + estados en el ledger (+ aceptación) (+ cuenta de fix), en una llamada.
  baseline            Línea base: fases de verify ANTES de tocar nada (separa regresiones de fallos previos).
  verify              Fases build/types/lint/tests + aceptación en verde, comparadas con la línea base. JSON.
  sync-permissions    Añade a .claude/settings.local.json los permisos que necesitan los agentes.
  wave-plan N         Imprime en JSON los WP de la ola N.
  open-wave N         Valida, toma el snapshot de la ola N e imprime sus WP en JSON (workflow nativo).
  close-wave N ID=estado...
                      check-wave N + estados finales en el ledger, en una sola llamada (workflow nativo).
  run-acceptance      Ola 0: lanza el agente test-author, que escribe los tests de aceptación antes del código.
  acceptance --expect red|green
                      Ejecuta el comando de aceptación del manifiesto. En la ola 0 deben fallar (red);
                      tras las olas, pasar (green).
  run-review          Lanza el revisor de código (solo lectura) sobre el resultado integrado.
  run-qa              Lanza el agente QA (`claude -p --agent qa`) sobre el resultado integrado.
  claim ID            Asocia el subagente actual a un WP o a QA (lo registra el hook).
  status              Muestra el ledger: estado de cada agente y de cada etapa.
  mark ID ESTADO [NOTA]
                      Actualiza el ledger a mano: running, done, blocker, pass, fail, stopped.
  stop [ID...]        Para los agentes en marcha (todos si no se indica ninguno) y lo anota en el ledger.
  hook                Hook PreToolUse (lee JSON por stdin).

El ledger (.claude/state/ledger.md) lo escribe este script, no el modelo: sobrevive a la compactación
del contexto y es la fuente para responder "¿cómo va?".

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
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
ARCH = ROOT / "architecture.md"
STATE = ROOT / ".claude" / "state"
CLAIMS = STATE / "claims.json"
LEDGER_JSON = STATE / "ledger.json"
LEDGER_MD = STATE / "ledger.md"
LEDGER_STATES = ("running", "done", "blocker", "pass", "fail", "timeout", "stopped", "error")
CONFIG = ROOT / ".claude" / "agentic.json"
BASE_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]
QA_DEFAULT_FILES = ["qa/"]
AT_DEFAULT_FILES = ["acceptance/"]
RESERVED_IDS = {"QA", "AT", "REVIEW"}
ARCHIVE_DIR = "docs/architecture/"  # archivo de decisiones: lo escribe /architect, nunca un WP
VERIFY_PHASES = ("build", "types", "lint", "tests")
BASELINE = STATE / "baseline.json"
MIRROR_RE = re.compile(r"^([^:]+?)(?::(\d+)(?:-(\d+))?)?$")  # ruta[:inicio[-fin]]
WORKFLOW_NAME = "agentic-implement"
TYPE_RE = re.compile(r"^Tipo:\s*(feature|change|fix|refactor)\b", re.M | re.I)
REVIEW_TOOLS = ["Read", "Glob", "Grep", "Bash(git diff:*)", "Bash(git status:*)", "Bash(git log:*)"]
# Todos los agentes orquestados (implementadores y QA) usan siempre el último Sonnet. `sonnet` es el alias
# que Claude Code resuelve al Sonnet más reciente que conoce; no se puede cambiar por config ni por entorno.
WORKER_MODEL = "sonnet"
# El arquitecto usa siempre el último Opus (alias `opus`, en el frontmatter de /architect).
# El orquestador (/implement) también va en el último Sonnet, desde su frontmatter.
ARCHITECT_MODEL = "opus"
DEFAULT_CONFIG = {
    "timeout_s": 1800,
    # "subscription": los agentes usan tu sesión de Claude (suscripción) aunque haya una API key en el entorno.
    # "inherit": heredan el entorno tal cual (útil en CI con API key).
    "auth": "subscription",
    "max_fix_cycles": 2,  # más ciclos --fix sobre el mismo WP se escalan al humano o a /architect
}
# Variables que harían que un agente facturase contra la API en vez de contra la suscripción.
API_AUTH_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
# Cachés y artefactos que generan las herramientas de test y build: no cuentan como cambios.
DEFAULT_IGNORE = ["__pycache__/", "*.pyc", ".pytest_cache/", ".mypy_cache/", ".ruff_cache/",
                  "node_modules/", ".coverage", "coverage/", ".nyc_output/", ".DS_Store", ".tsbuildinfo"]

MANIFEST_RE = re.compile(r"```json\s+wp-manifest\s*\n(.*?)\n```", re.S)
CLAIM_RE = re.compile(r"agentic\.py\s+claim\s+(WP-\d+|QA|AT|REVIEW)\b")
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
# ---- Guardarraíles de contenido (adaptados de ECC: config-protection, block-no-verify, governance-capture) ----
# Saltarse los hooks de git: prohibido para todos, también para la sesión principal.
GIT_HOOK_BYPASS_RE = re.compile(r"\bgit\b[^;&|\n]*?(\s--no-verify\b|\s-c\s*core\.hookspath=)", re.I)
GIT_COMMIT_N_RE = re.compile(r"\bgit\b[^;&|\n]*?\scommit\b[^;&|\n]*?\s-n\b")  # se aplica sin el texto entre comillas
QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
# Configuración de calidad: crearla está permitido; modificar la existente, no (salvo "config_edit": true en el WP).
PROTECTED_CONFIG_RE = re.compile(
    r"^(\.eslintrc(\.(js|cjs|json|ya?ml))?|eslint\.config\.[cm]?[jt]s|\.prettierrc(\.(js|cjs|json|ya?ml))?|"
    r"prettier\.config\.[cm]?js|\.?biome\.jsonc?|\.?ruff\.toml|\.flake8|\.pylintrc|pylintrc|\.?mypy\.ini|"
    r"pytest\.ini|tox\.ini|setup\.cfg|\.coveragerc|pyproject\.toml|tsconfig(\.[\w-]+)?\.json|"
    r"(jest|vitest|playwright)\.config\.[cm]?[jt]s|\.stylelintrc(\.\w+)?|\.golangci\.ya?ml|\.?rustfmt\.toml|"
    r"clippy\.toml|\.editorconfig|\.shellcheckrc|\.(eslint|prettier|stylelint)ignore)$", re.I)
# Desactivar tests sin condición para ponerlos en verde (skipIf/skipUnless condicionales sí se permiten).
SKIP_MARKER_RE = re.compile(
    r"@unittest\.skip\b(?!If|Unless)|\bunittest\.skip\(|@skip\(|\bexpectedFailure\b|"
    r"pytest\.mark\.(skip|xfail)\b(?!if)|\bpytest\.(skip|xfail)\(|"
    r"\b(it|test|describe|context)\.(skip|only|todo)\(|\bx(it|describe|test)\(|\bf(it|describe)\(|"
    r"\bt\.Skip(Now)?\(|#\[ignore\]")
TEST_PATH_RE = re.compile(r"(^|/)(tests?|spec|__tests__|acceptance|qa)/|(^|/)test_[^/]*$|_test\.\w+$|\.(test|spec)\.\w+$")
SECRET_RES = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "clave de acceso de AWS"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,}"), "token de GitHub"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "clave de Anthropic"),
    (re.compile(r"\bsk-(proj-)?[A-Za-z0-9]{32,}"), "clave de API tipo sk-"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "token de Slack"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "clave de Google"),
    (re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY"), "clave privada"),
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


def at_entity(manifest):
    at = manifest.get("acceptance", {})
    return {"id": "AT", "files": at.get("files", AT_DEFAULT_FILES), "allow_bash": at.get("allow_bash", []),
            "command": at.get("command")}


def review_entity(manifest):
    return {"id": "REVIEW", "files": [], "allow_bash": []}  # solo lectura: el hook bloquea cualquier escritura


def entities(manifest):
    """Todo lo que puede reclamar propiedad de ficheros: los WP, QA, los tests de aceptación y el revisor."""
    table = wps(manifest)
    table["QA"] = qa_entity(manifest)
    table["AT"] = at_entity(manifest)
    table["REVIEW"] = review_entity(manifest)
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
    for rid in RESERVED_IDS & set(table):
        errors.append(f"'{rid}' es un ID reservado.")
    at = manifest.get("acceptance")
    if at is not None and not (isinstance(at, dict) and isinstance(at.get("command"), str) and at["command"].strip()):
        errors.append("acceptance: necesita 'command', el comando que ejecuta los tests de aceptación.")
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
        errors += mirror_errors(wp)
        if "config_edit" in wp and not isinstance(wp["config_edit"], bool):
            errors.append(f"{wp['id']}: 'config_edit' debe ser true o false.")
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
            if f == "architecture.md" or f.startswith(".claude/") or f.startswith(ARCHIVE_DIR) or f in ("", "./", "/"):
                errors.append(f"{ent['id']}: no puede poseer '{f}'.")
    owners = [(f, e["id"]) for e in entities(manifest).values() for f in e.get("files", [])]
    for i, (fa, wa) in enumerate(owners):
        for fb, wb in owners[i + 1:]:
            if wa != wb and owner_conflict(fa, fb):
                errors.append(f"Fichero con dos propietarios: {fa} ({wa}) y {fb} ({wb}).")
    for rule in manifest.get("allow_bash", []) + qa_entity(manifest)["allow_bash"] + at_entity(manifest)["allow_bash"]:
        if not re.fullmatch(r"Bash\(.+\)", rule):
            errors.append(f"allow_bash: regla mal formada: {rule}")
        elif open_ended_rule(rule):
            errors.append(f"allow_bash: regla demasiado amplia (daría ejecución arbitraria): {rule}. "
                          "Usa el comando concreto, p. ej. Bash(npm test:*) o Bash(python3 -m pytest:*).")
    if not isinstance(manifest.get("ignore", []), list):
        errors.append("'ignore' debe ser una lista de patrones.")
    verify_cfg = manifest.get("verify", {})
    if not isinstance(verify_cfg, dict) or any(k not in VERIFY_PHASES or not isinstance(v, str) or not v.strip()
                                                  for k, v in verify_cfg.items()):
        errors.append(f"'verify' debe ser un objeto con comandos (texto) para {', '.join(VERIFY_PHASES)}.")
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
    names = {"implementer", "qa", "test-author", "reviewer", "gatekeeper", "verifier"} | {wp.get("agent", "implementer") for wp in wps(manifest).values()}
    for name in sorted(names):
        f = ROOT / ".claude" / "agents" / f"{name}.md"
        if not f.exists():
            errors.append(f"Agente '{name}': no existe {f.relative_to(ROOT)}.")
            continue
        model = frontmatter_model(f)
        if model != WORKER_MODEL:
            errors.append(f"Agente '{name}': su frontmatter debe decir 'model: {WORKER_MODEL}' (el último Sonnet), "
                          f"no '{model}'.")
    plan_reviewer = ROOT / ".claude" / "agents" / "plan-reviewer.md"
    if plan_reviewer.exists() and frontmatter_model(plan_reviewer) != ARCHITECT_MODEL:
        errors.append(f"Agente 'plan-reviewer': su frontmatter debe decir 'model: {ARCHITECT_MODEL}' (el último Opus), "
                      f"no '{frontmatter_model(plan_reviewer)}'.")
    for command, expected, label in (("architect", ARCHITECT_MODEL, "el último Opus"),
                                     ("implement", WORKER_MODEL, "el último Sonnet")):
        f = ROOT / ".claude" / "commands" / f"{command}.md"
        if f.exists() and frontmatter_model(f) != expected:
            errors.append(f"/{command}: su frontmatter debe decir 'model: {expected}' ({label}), "
                          f"no '{frontmatter_model(f)}'.")
    return errors


def mirror_errors(wp):
    """Las referencias a código existente ("mirror") deben existir de verdad: atrapa rutas o líneas inventadas."""
    errors = []
    mirror = wp.get("mirror", [])
    if not isinstance(mirror, list):
        return [f"{wp['id']}: 'mirror' debe ser una lista de 'ruta[:inicio[-fin]]'."]
    for ref in mirror:
        m = MIRROR_RE.match(str(ref))
        if not m:
            errors.append(f"{wp['id']}: referencia mirror mal formada: {ref}")
            continue
        rel, start, end = m.group(1), m.group(2), m.group(3)
        f = ROOT / rel
        if ".." in Path(rel).parts or rel.startswith("/") or not f.is_file():
            errors.append(f"{wp['id']}: mirror apunta a un fichero que no existe: {rel}")
            continue
        if start:
            n = sum(1 for _ in f.open(encoding="utf-8", errors="replace"))
            a, b = int(start), int(end or start)
            if not (1 <= a <= b <= n):
                errors.append(f"{wp['id']}: mirror {ref} fuera de rango ({rel} tiene {n} líneas).")
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


STAGE_LABELS = {"qa": qa_entity, "acceptance": at_entity, "review": review_entity}


def stage_owners(manifest, label):
    if label in STAGE_LABELS:
        return [STAGE_LABELS[label](manifest)]
    return [wp for wp in wps(manifest).values() if wp["wave"] == int(label)]


def snapshot(label):
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / f"snapshot-{label}.json").write_text(json.dumps(digest()))
    CLAIMS.unlink(missing_ok=True)  # cada etapa empieza sin reclamaciones
    ledger_stage(label, "en curso")
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
        proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=out, stderr=err, stdin=subprocess.DEVNULL,
                                start_new_session=True)  # su propio grupo: stop y timeout lo matan entero
        procs[jid] = (proc, out, err)
        ledger_update(jid, state="running", stage=label, mode="A", pid=proc.pid, started=now_hm(), note="")
        print(f"Lanzado {jid} [{agent}, {WORKER_MODEL}] (pid {proc.pid})", flush=True)

    start = time.time()
    deadline = start + cfg["timeout_s"]
    statuses = {}
    for jid, (proc, out, err) in procs.items():
        try:
            proc.wait(timeout=max(0, deadline - time.time()))
            timed_out = False
        except subprocess.TimeoutExpired:
            kill_group(proc.pid)
            proc.wait()
            timed_out = True
        out.close()
        err.close()
        if timed_out:
            statuses[jid] = f"TIMEOUT ({cfg['timeout_s']}s)"
        elif ledger_read().get(jid, {}).get("state") == "stopped":
            statuses[jid] = "STOPPED"
        else:
            statuses[jid] = parse_status(runs / f"{jid}.json", proc.returncode)
        ledger_update(jid, state=status_to_state(statuses[jid]), pid=None, note=statuses[jid])
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
    at_cmd = at_entity(manifest)["command"]
    if at_cmd:  # los implementers pueden ver sus tests de aceptación en verde, pero no editarlos
        allowed = allowed + [f"Bash({at_cmd}:*)", f"Bash({at_cmd})"]
    reports = [r for r in ("QA", "REVIEW") if (STATE / "runs" / f"{r}.json").exists()]
    if fix and not reports:
        die("--fix necesita un informe de revisión o de QA (.claude/state/runs/REVIEW.json o QA.json). "
            "Ejecuta run-review o run-qa antes.")
    if fix:
        cap = int(cfg.get("max_fix_cycles", 2))
        ledger = ledger_read()
        over = [wp["id"] for wp in wave_wps if ledger.get(wp["id"], {}).get("fix_count", 0) >= cap]
        if over:
            die(f"{', '.join(over)} ya agotó sus {cap} ciclos --fix. No es un fallo de implementación que se arregle "
                "insistiendo: decide tú, o revisa el contrato con /architect.", code=4)
        for wp in wave_wps:
            ledger_update(wp["id"], fix_count=ledger.get(wp["id"], {}).get("fix_count", 0) + 1)
    prompt = "Implementa {id} según architecture.md." + (
        " El código ya existe: corrige los defectos que te asignan "
        + " y ".join(f".claude/state/runs/{r}.json" for r in reports)
        + ", sin salirte del contrato, y deja en verde sus tests de aceptación." if fix else "")
    statuses = launch(str(wave), [
        (wp["id"], wp.get("agent", "implementer"), prompt.format(id=wp["id"]),
         allowed)
        for wp in wave_wps], cfg)
    finish(manifest, str(wave), statuses, "DONE")


def run_acceptance(manifest):
    at = at_entity(manifest)
    if not at["command"]:
        die("El manifiesto no tiene sección 'acceptance': no hay ola 0 que lanzar.")
    cfg = load_config()
    allowed = BASE_TOOLS + manifest.get("allow_bash", []) + at["allow_bash"]
    statuses = launch("acceptance", [("AT", "test-author",
                                      "Escribe los tests de aceptación según architecture.md.", allowed)], cfg)
    finish(manifest, "acceptance", statuses, "DONE")


def run_review(manifest):
    cfg = load_config()
    allowed = REVIEW_TOOLS + manifest.get("allow_bash", [])
    statuses = launch("review", [("REVIEW", "reviewer",
                                  "Revisa el código integrado según architecture.md.", allowed)], cfg)
    finish(manifest, "review", statuses, "PASS")


def run_command(cmd, timeout=900):
    """Ejecuta un comando del manifiesto sin shell. Devuelve (código, últimas líneas de salida)."""
    try:
        r = subprocess.run(shlex.split(cmd), cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                           env=child_env(load_config(), CLAUDE_PROJECT_DIR=str(ROOT)))
        return r.returncode, (r.stdout + r.stderr).strip().splitlines()[-8:]
    except FileNotFoundError:
        return 127, [f"comando no encontrado: {cmd}"]
    except subprocess.TimeoutExpired:
        return 124, [f"el comando superó {timeout // 60} minutos"]


def acceptance_check(manifest, expect, quiet=False):
    """red: deben fallar (ola 0). green: deben pasar (tras las olas). Devuelve (ok, veredicto)."""
    cmd = at_entity(manifest)["command"]
    if not cmd:
        die("El manifiesto no tiene sección 'acceptance'.")
    code, tail = run_command(cmd)
    if not quiet:
        print(f"$ {cmd}  ->  exit {code}")
        for line in tail:
            print("  " + line)
    if code in (124, 126, 127):
        ok, verdict = False, "ERROR: el comando no se pudo ejecutar; eso no cuenta como rojo ni como verde"
    elif expect == "red":
        ok = code != 0
        verdict = "ROJO, como debe ser antes del código" if ok else "YA PASAN SIN CÓDIGO: los tests no prueban nada"
    else:
        ok = code == 0
        verdict = "VERDE" if ok else "SIGUEN FALLANDO"
    ledger_stage(f"aceptación ({expect})", "OK" if ok else "REVISAR")
    return ok, verdict


def acceptance(manifest, expect):
    ok, verdict = acceptance_check(manifest, expect)
    print(f"ACEPTACIÓN: {verdict}")
    print("RESULTADO:", "OK" if ok else "REVISAR")
    sys.exit(0 if ok else 3)


# ---------- comandos del workflow nativo (los ejecuta el agente gatekeeper) ----------

def architecture_type():
    m = TYPE_RE.search(ARCH.read_text(encoding="utf-8")) if ARCH.exists() else None
    return m.group(1).lower() if m else None


def pipeline_plan(manifest):
    waves = sorted({wp["wave"] for wp in wps(manifest).values()})
    plan = {"waves": waves, "acceptance": bool(at_entity(manifest)["command"]), "type": architecture_type(),
            "verify": sorted(manifest.get("verify", {})), "max_fix_cycles": int(load_config().get("max_fix_cycles", 2)),
            "agents": {wp["id"]: wp.get("agent", "implementer") for wp in wps(manifest).values()},
            "baseline": bool(manifest.get("verify")),
            "wave_of": {wp["id"]: wp["wave"] for wp in wps(manifest).values()},
            "work_packages": {str(w): sorted(wp["id"] for wp in stage_owners(manifest, str(w))) for w in waves}}
    print(json.dumps(plan))


def stage_label(arg):
    if not (arg.isdigit() or arg in STAGE_LABELS):
        die(f"Etapa desconocida: {arg}. Usa un número de ola o {', '.join(STAGE_LABELS)}.")
    return arg


def open_stage(manifest, label):
    owners = sorted(o["id"] for o in stage_owners(manifest, label))
    if owners:
        with open(os.devnull, "w") as quiet:  # el snapshot no debe ensuciar la salida JSON
            old, sys.stdout = sys.stdout, quiet
            try:
                snapshot(label)
            finally:
                sys.stdout = old
    print(json.dumps({"stage": label, "owners": owners}))
    sys.exit(0 if owners else 3)


def close_stage(manifest, label, items):
    """close-stage L ID=estado... [--expect red|green] [--fix]: propiedad, estados, aceptación y ciclos de fix."""
    expect = None
    if "--expect" in items:
        i = items.index("--expect")
        expect = items[i + 1] if i + 1 < len(items) else None
        if expect not in ("red", "green"):
            die("close-stage: --expect necesita red o green")
        items = items[:i] + items[i + 2:]
    fix = "--fix" in items
    items = [x for x in items if x != "--fix"]
    known = entities(manifest)
    marks = []
    for item in items:
        jid, _, state = item.partition("=")
        if jid not in known or state not in LEDGER_STATES:
            die(f"close-stage: entrada inválida '{item}' (ID del manifiesto y estado en {', '.join(LEDGER_STATES)})")
        marks.append((jid, state))
    ledger = ledger_read()
    for jid, state in marks:
        extra = {"fix_count": ledger.get(jid, {}).get("fix_count", 0) + 1} if fix else {}
        ledger_update(jid, state=state, stage=stage_of(jid), pid=None, note=state.upper() + (" (fix)" if fix else ""), **extra)
    ok = check_stage(manifest, label) and all(state in ("done", "pass") for _, state in marks)
    if expect:
        acc_ok, verdict = acceptance_check(manifest, expect, quiet=True)
        print(f"ACEPTACIÓN ({expect}): {verdict}")
        ok = ok and acc_ok
    ledger_stage(label, "OK" if ok else "REVISAR")
    print("RESULTADO:", "OK" if ok else "REVISAR")
    sys.exit(0 if ok else 3)


def run_phases(manifest):
    cfg = manifest.get("verify", {})
    phases = []
    for name in VERIFY_PHASES:
        if name not in cfg:
            phases.append({"name": name, "skipped": True})
            continue
        code, tail = run_command(cfg[name])
        phases.append({"name": name, "command": cfg[name], "exit": code, "passed": code == 0, "tail": tail})
    return phases


def baseline(manifest):
    """Línea base: estado de las fases de verify ANTES de tocar nada. Separa regresiones de fallos previos."""
    phases = run_phases(manifest)
    STATE.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps({"phases": phases}, ensure_ascii=False, indent=2))
    failing = [p["name"] for p in phases if p.get("passed") is False]
    ledger_stage("línea base", "OK" if not failing else "con fallos previos: " + ", ".join(failing))
    print(json.dumps({"phases": phases, "preexisting_failures": failing}, ensure_ascii=False))
    errored = [p["name"] for p in phases if p.get("exit") in (124, 126, 127)]
    sys.exit(1 if errored else 0)


def verify(manifest):
    """Fases de verify y aceptación en verde. Con línea base, una fase que ya fallaba es 'fallo previo'
    (se informa, no bloquea) y una que pasaba y ahora falla es 'regresión' (bloquea). Salida JSON."""
    base = {p["name"]: p for p in json.loads(BASELINE.read_text()).get("phases", [])} if BASELINE.exists() else {}
    phases = run_phases(manifest)
    for ph in phases:
        if ph.get("skipped"):
            continue
        was = base.get(ph["name"], {}).get("passed")
        ph["baseline_passed"] = was
        if ph["passed"]:
            ph["status"] = "ok"
        elif was is False:
            ph["status"] = "fallo previo"
        else:
            ph["status"] = "regresión" if was else "falla"
    if at_entity(manifest)["command"]:
        acc_ok, verdict = acceptance_check(manifest, "green", quiet=True)
        phases.append({"name": "acceptance", "command": at_entity(manifest)["command"], "passed": acc_ok,
                       "verdict": verdict, "status": "ok" if acc_ok else "falla"})
    blocking = [p["name"] for p in phases if p.get("status") in ("regresión", "falla")]
    preexisting = [p["name"] for p in phases if p.get("status") == "fallo previo"]
    ok = not blocking
    ledger_stage("verificación", "OK" if ok else "REVISAR: " + ", ".join(blocking))
    print(json.dumps({"ok": ok, "blocking": blocking, "preexisting_failures": preexisting, "phases": phases},
                     ensure_ascii=False))
    sys.exit(0 if ok else 3)


def sync_permissions(manifest):
    """Escribe en .claude/settings.local.json los permisos que necesitan los agentes, para que no pregunten."""
    rules = {"Workflow(" + WORKFLOW_NAME + ")", "Bash(python3 .claude/bin/agentic.py:*)"}
    rules |= set(manifest.get("allow_bash", [])) | set(qa_entity(manifest)["allow_bash"]) | set(at_entity(manifest)["allow_bash"])
    for cmd in [at_entity(manifest)["command"], *manifest.get("verify", {}).values()]:
        if cmd:
            rules |= {f"Bash({cmd})", f"Bash({cmd}:*)"}
    local = ROOT / ".claude" / "settings.local.json"
    data = json.loads(local.read_text(encoding="utf-8")) if local.exists() else {}
    allow = data.setdefault("permissions", {}).setdefault("allow", [])
    added = sorted(r for r in rules if r not in allow)
    allow.extend(added)
    local.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(added)} regla(s) añadidas a .claude/settings.local.json" + (": " + ", ".join(added) if added else ""))


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
    ledger_stage(label, "OK" if ok else "REVISAR")
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

def locked_json(path, fn):
    """Ejecuta fn(datos) con el fichero JSON bloqueado; si devuelve un dict, lo guarda. Devuelve los datos previos."""
    STATE.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        raw = fh.read()
        data = json.loads(raw) if raw.strip() else {}
        new = fn(data)
        if new is not None:
            fh.seek(0)
            fh.truncate()
            fh.write(json.dumps(new, indent=2))
        return data


def with_claims(fn):
    return locked_json(CLAIMS, fn)


# ---------- ledger ----------

def now_hm():
    return time.strftime("%H:%M")


def ledger_read():
    return locked_json(LEDGER_JSON, lambda d: None)


def ledger_update(jid, **fields):
    def upd(d):
        entry = dict(d.get(jid, {}), **fields, updated=now_hm())
        return dict(d, **{jid: entry})
    locked_json(LEDGER_JSON, upd)
    ledger_render()


def ledger_stage(label, result):
    def upd(d):
        stages = dict(d.get("_stages", {}), **{str(label): f"{result} ({now_hm()})"})
        return dict(d, _stages=stages)
    locked_json(LEDGER_JSON, upd)
    ledger_render()


def status_to_state(status):
    head = status.split()[0] if status else ""
    return {"DONE": "done", "BLOCKER": "blocker", "PASS": "pass", "FAIL": "fail",
            "TIMEOUT": "timeout", "STOPPED": "stopped"}.get(head, "error")


def stage_of(jid):
    if jid in ("QA", "AT", "REVIEW"):
        return {"QA": "qa", "AT": "acceptance", "REVIEW": "review"}[jid]
    try:
        return str(wps(load_manifest()).get(jid, {}).get("wave", "?"))
    except ManifestError:
        return "?"


def ledger_render():
    d = ledger_read()
    stages = d.get("_stages", {})
    agents = {k: v for k, v in d.items() if not k.startswith("_")}
    order = lambda kv: (kv[1].get("stage") == "qa", str(kv[1].get("stage")), kv[0])
    lines = ["# Ledger del flow", "", f"Actualizado: {now_hm()}", "", "## Etapas", ""]
    pipeline = {"acceptance": 0, "aceptación (red)": 1, "aceptación (green)": 3, "review": 4, "qa": 5}
    order_st = lambda k: (2, k.zfill(4)) if k.isdigit() else (pipeline.get(k, 6), k)  # orden del pipeline
    lines += [f"- {'ola ' + k if k.isdigit() else k}: {stages[k]}" for k in sorted(stages, key=order_st)] or ["- (ninguna)"]
    lines += ["", "## Agentes", ""]
    for jid, e in sorted(agents.items(), key=order):
        parts = [f"- [{e.get('state', '?')}]".ljust(11) + f" {jid} ({WORKER_MODEL})",
                 f"etapa {e.get('stage', '?')}", f"modo {e.get('mode', '?')}", f"inicio {e.get('started', '?')}"]
        if e.get("pid"):
            parts.append(f"pid {e['pid']}")
        if e.get("note"):
            parts.append(e["note"])
        lines.append(" — ".join(parts))
    if not agents:
        lines.append("- (ninguno)")
    LEDGER_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def kill_group(pid):
    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


def stop(ids):
    d = ledger_read()
    targets = [k for k, v in d.items() if not k.startswith("_") and v.get("state") == "running"
               and (not ids or k in ids)]
    if not targets:
        print("No hay agentes en marcha" + (f" con esos ID: {', '.join(ids)}." if ids else "."))
        return
    for jid in targets:
        e = d[jid]
        ledger_update(jid, state="stopped", note="parado a petición")
        if e.get("pid"):
            kill_group(e["pid"])
            print(f"{jid}: parado (pid {e['pid']}).")
        else:
            print(f"{jid}: marcado como parado. Es un agente del workflow: páralo desde /workflows (tecla x).")


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
    try:  # el ledger es informativo: un fallo aquí no debe bloquear la reclamación
        ledger_update(wanted, state="running", stage=stage_of(wanted), mode="workflow", pid=None, started=now_hm(), note="")
    except Exception:  # noqa: BLE001
        pass


def written_text(tool, tinput):
    """Lo que la herramienta va a escribir, y lo que sustituye (para comparar)."""
    if tool == "Write":
        return tinput.get("content") or "", None
    if tool == "Edit":
        return tinput.get("new_string") or "", tinput.get("old_string") or ""
    if tool == "MultiEdit":
        edits = tinput.get("edits") or []
        return ("\n".join(e.get("new_string", "") for e in edits),
                "\n".join(e.get("old_string", "") for e in edits))
    if tool == "NotebookEdit":
        return tinput.get("new_source") or "", None
    return "", None


def content_checks(owner_id, ent, rel, abs_path, tool, tinput):
    new, old = written_text(tool, tinput)
    for rx, what in SECRET_RES:
        if rx.search(new):
            block(f"{owner_id}: lo que vas a escribir en {rel} contiene lo que parece una {what}. "
                  "Usa un valor sintético o una variable de entorno; nunca un secreto real.")
    if PROTECTED_CONFIG_RE.match(Path(rel).name) and abs_path.exists() and not ent.get("config_edit"):
        block(f"{owner_id}: {rel} es configuración de calidad ya existente. No se relaja una regla para pasar "
              "una comprobación: arregla el código. Si de verdad hay que cambiarla, devuelve STATUS: BLOCKER.")
    if TEST_PATH_RE.search(rel):
        if old is None:
            try:
                old = abs_path.read_text(encoding="utf-8", errors="replace") if tool == "Write" and abs_path.exists() else ""
            except OSError:
                old = ""
        if len(SKIP_MARKER_RE.findall(new)) > len(SKIP_MARKER_RE.findall(old)):
            block(f"{owner_id}: no se desactivan tests para ponerlos en verde (skip, xfail, only…) en {rel}. "
                  "Un test que falla se arregla o se reporta: devuelve STATUS: BLOCKER. "
                  "Los saltos condicionales de plataforma (skipIf/skipUnless) sí están permitidos.")


def guard(data):
    tool = data.get("tool_name", "")
    tinput = data.get("tool_input", {}) or {}
    agent_id = data.get("agent_id")
    owner_id = os.environ.get("AGENTIC_WP")

    bash_cmd = tinput.get("command", "") if tool == "Bash" else ""
    if bash_cmd and (GIT_HOOK_BYPASS_RE.search(bash_cmd) or GIT_COMMIT_N_RE.search(QUOTED_RE.sub("''", bash_cmd))):
        block("saltarse los hooks de git (--no-verify, commit -n, core.hooksPath) no está permitido a ningún agente. "
              "Si un hook falla, arregla la causa o pídele al usuario que decida.")

    if tool == "Bash" and agent_id and not owner_id:
        m = CLAIM_RE.search(tinput.get("command", ""))
        if m:
            claim(agent_id, m.group(1))
            return

    if not owner_id and agent_id:
        owner_id = with_claims(lambda c: None).get(agent_id)
        if not owner_id and data.get("agent_type") in ("implementer", "qa", "test-author", "reviewer"):
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
    content_checks(owner_id, ent, rel, abs_path, tool, tinput)


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
    elif cmd == "status":
        ledger_render()
        print(LEDGER_MD.read_text(encoding="utf-8"), end="")
    elif cmd == "mark":
        if len(args) < 2 or args[1] not in LEDGER_STATES:
            die(f"Uso: mark ID ESTADO [NOTA]  (estados: {', '.join(LEDGER_STATES)})")
        jid, state = args[0], args[1]
        if jid not in entities(require_valid()):
            die(f"{jid} no existe en el manifiesto.")
        prev = ledger_read().get(jid, {})
        fields = dict(state=state, stage=stage_of(jid), mode=prev.get("mode", "workflow"), note=" ".join(args[2:]))
        if not prev:
            fields["started"] = now_hm()
        ledger_update(jid, **fields)
        print(f"{jid}: {state}")
    elif cmd == "stop":
        stop(args)
    elif cmd == "validate":
        require_valid()
        print("Manifiesto válido.")
    elif cmd == "run-qa":
        run_qa(require_valid())
    elif cmd == "pipeline-plan":
        pipeline_plan(require_valid())
    elif cmd == "open-stage":
        if not args:
            die("Uso: open-stage N|acceptance|review|qa")
        open_stage(require_valid(), stage_label(args[0]))
    elif cmd == "close-stage":
        if not args:
            die("Uso: close-stage N|acceptance|review|qa ID=estado... [--expect red|green] [--fix]")
        close_stage(require_valid(), stage_label(args[0]), args[1:])
    elif cmd == "verify":
        verify(require_valid())
    elif cmd == "baseline":
        baseline(require_valid())
    elif cmd == "sync-permissions":
        sync_permissions(require_valid())
    elif cmd in ("wave-plan", "open-wave"):
        if not args or not args[0].isdigit():
            die(f"Uso: {cmd} N")
        manifest = require_valid()
        ids = sorted(wp["id"] for wp in stage_owners(manifest, args[0]))
        if cmd == "open-wave" and ids:
            with open(os.devnull, "w") as quiet:  # el snapshot no debe ensuciar la salida JSON
                old, sys.stdout = sys.stdout, quiet
                try:
                    snapshot(args[0])
                finally:
                    sys.stdout = old
        print(json.dumps({"wave": int(args[0]), "work_packages": ids}))
        sys.exit(0 if ids else 3)
    elif cmd == "close-wave":
        # close-wave N WP-01=done WP-02=blocker ...: check-wave + estados en el ledger, en una sola llamada.
        if not args or not args[0].isdigit():
            die("Uso: close-wave N ID=estado [ID=estado...]")
        manifest = require_valid()
        known = entities(manifest)
        marks = []
        for item in args[1:]:
            jid, _, state = item.partition("=")
            if jid not in known or state not in LEDGER_STATES:
                die(f"close-wave: entrada inválida '{item}' (ID del manifiesto y estado en {', '.join(LEDGER_STATES)})")
            marks.append((jid, state))
        for jid, state in marks:
            ledger_update(jid, state=state, stage=stage_of(jid), pid=None, note=state.upper())
        ok = check_stage(manifest, args[0]) and all(state == "done" for _, state in marks)
        ledger_stage(args[0], "OK" if ok else "REVISAR")
        print("RESULTADO:", "OK" if ok else "REVISAR")
        sys.exit(0 if ok else 3)
    elif cmd == "run-acceptance":
        run_acceptance(require_valid())
    elif cmd == "run-review":
        run_review(require_valid())
    elif cmd == "acceptance":
        if args[:1] != ["--expect"] or args[1:2] not in (["red"], ["green"]):
            die("Uso: acceptance --expect red|green")
        acceptance(require_valid(), args[1])
    elif cmd in ("snapshot", "check-wave", "run-wave"):
        if not args or not (args[0].isdigit() or (args[0] in STAGE_LABELS and cmd != "run-wave")):
            die(f"Uso: {cmd} N" + ("" if cmd == "run-wave" else " | " + " | ".join(STAGE_LABELS)))
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
