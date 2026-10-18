"""Tests de los guardarraíles y del lanzador.

Ejecutar: python3 -m unittest discover -s .claude/bin -p "test_*.py"
Cada test trabaja en un repo git temporal; el lanzador usa un `claude` falso, sin llamadas reales.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "agentic.py"
AGENTS_DIR = SCRIPT.parents[1] / "agents"

MANIFEST = {
    "allow_bash": ["Bash(python3 -m unittest:*)"],
    "ignore": ["dist/"],
    "acceptance": {"files": ["acceptance/"], "command": "python3 acc.py"},
    "work_packages": [
        {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/a.py", "tests/test_a.py"]},
        {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["src/b/"]},
        {"id": "WP-03", "wave": 2, "depends_on": ["WP-01"], "files": ["src/c.py"]},
    ],
}

FAKE_CLAUDE = textwrap.dedent("""\
    #!/usr/bin/env python3
    import json, os, sys, time
    wp = os.environ["AGENTIC_WP"]
    with open(os.path.join(os.environ["FAKE_LOG_DIR"], wp + ".args"), "w") as f:
        json.dump(sys.argv[1:], f)
    with open(os.path.join(os.environ["FAKE_LOG_DIR"], wp + ".env"), "w") as f:
        json.dump({k: os.environ.get(k) for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}, f)
    time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
    status = os.environ.get("FAKE_STATUS", "DONE" if wp != "QA" else "PASS")
    print(json.dumps({"result": "STATUS: " + status + "\\nWP: " + wp}))
""")


class Repo:
    def __init__(self, manifest=MANIFEST, raw_manifest=None):
        self.dir = Path(tempfile.mkdtemp(prefix="agentic-test-"))
        body = raw_manifest if raw_manifest is not None else json.dumps(manifest, indent=2)
        (self.dir / "architecture.md").write_text(f"# A\n\n```json wp-manifest\n{body}\n```\n")
        shutil.copytree(AGENTS_DIR, self.dir / ".claude" / "agents")
        subprocess.run(["git", "init", "-q"], cwd=self.dir, check=True)
        self.env = dict(os.environ, CLAUDE_PROJECT_DIR=str(self.dir))
        self.env.pop("AGENTIC_WP", None)

    def run(self, *args, stdin=None, env=None):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.dir, input=stdin,
                              capture_output=True, text=True, env=dict(self.env, **(env or {})))

    def hook(self, payload, wp=None):
        return self.run("hook", stdin=json.dumps(payload), env={"AGENTIC_WP": wp} if wp else None).returncode

    def write(self, rel, text="x"):
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def write_payload(path, agent_id=None, tool="Write"):
    data = {"tool_name": tool, "tool_input": {"file_path": path}}
    if agent_id:
        data.update(agent_id=agent_id, agent_type="implementer")
    return data


def bash_payload(command, agent_id=None):
    data = {"tool_name": "Bash", "tool_input": {"command": command}}
    if agent_id:
        data.update(agent_id=agent_id, agent_type="implementer")
    return data


class Base(unittest.TestCase):
    manifest = MANIFEST

    def setUp(self):
        self.repo = Repo(self.manifest)

    def tearDown(self):
        self.repo.cleanup()


class ValidateTests(unittest.TestCase):
    def errors(self, manifest):
        sys.path.insert(0, str(SCRIPT.parent))
        import agentic
        return agentic.validate(manifest)

    def test_manifiesto_valido(self):
        self.assertEqual(self.errors(MANIFEST), [])

    def test_solape_de_ficheros(self):
        m = json.loads(json.dumps(MANIFEST))
        m["work_packages"][2]["files"] = ["src/b/x.py"]
        self.assertTrue(any("dos propietarios" in e for e in self.errors(m)))

    def test_solape_con_qa(self):
        m = dict(MANIFEST, qa={"files": ["src/"]})
        self.assertTrue(any("dos propietarios" in e for e in self.errors(m)))

    def test_dependencia_misma_ola(self):
        m = json.loads(json.dumps(MANIFEST))
        m["work_packages"][1]["depends_on"] = ["WP-01"]
        self.assertTrue(any("ola anterior" in e for e in self.errors(m)))

    def test_reglas_amplias_rechazadas(self):
        for rule in ["Bash(*)", "Bash(python3:*)", "Bash(npm:*)", "Bash(bash:*)", "Bash(sh)", "Bash(git:*)", "Bash(np*)"]:
            with self.subTest(rule=rule):
                m = dict(MANIFEST, allow_bash=[rule])
                self.assertTrue(any("demasiado amplia" in e for e in self.errors(m)))

    def test_reglas_concretas_aceptadas(self):
        m = dict(MANIFEST, allow_bash=["Bash(npm test:*)", "Bash(python3 -m pytest:*)", "Bash(pytest:*)", "Bash(make test)"])
        self.assertEqual(self.errors(m), [])

    def test_no_puede_poseer_claude_ni_architecture(self):
        for f in [".claude/settings.json", "architecture.md"]:
            m = json.loads(json.dumps(MANIFEST))
            m["work_packages"][0]["files"] = [f]
            self.assertTrue(self.errors(m), f)

    def test_id_duplicado_y_reservado(self):
        m = json.loads(json.dumps(MANIFEST))
        m["work_packages"][1]["id"] = "WP-01"
        self.assertTrue(any("duplicado" in e for e in self.errors(m)))
        m["work_packages"][1]["id"] = "QA"
        self.assertTrue(any("reservado" in e for e in self.errors(m)))


class HookWriteTests(Base):
    def test_hilo_principal_sin_restricciones(self):
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "cualquiera.py"))), 0)

    def test_modo_a_propio_y_ajeno(self):
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/a.py")), wp="WP-01"), 0)
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/b/x.py")), wp="WP-01"), 2)
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/b/x.py")), wp="WP-02"), 0)

    def test_ruta_relativa_y_fuera_del_repo(self):
        self.assertEqual(self.repo.hook({**write_payload("src/a.py"), "cwd": str(self.repo.dir)}, wp="WP-01"), 0)
        self.assertEqual(self.repo.hook(write_payload("/tmp/fuera.py"), wp="WP-01"), 2)
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/../src/b/x.py")), wp="WP-01"), 2)

    def test_qa_solo_su_zona(self):
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "qa/t.py")), wp="QA"), 0)
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/a.py")), wp="QA"), 2)

    def test_modo_b_necesita_claim(self):
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/a.py"), agent_id="ag1")), 2)
        self.assertEqual(self.repo.hook(bash_payload("python3 .claude/bin/agentic.py claim WP-01", agent_id="ag1")), 0)
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/a.py"), agent_id="ag1")), 0)
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/c.py"), agent_id="ag1")), 2)

    def test_claim_exclusivo(self):
        claim = "python3 .claude/bin/agentic.py claim WP-01"
        self.assertEqual(self.repo.hook(bash_payload(claim, agent_id="ag1")), 0)
        self.assertEqual(self.repo.hook(bash_payload(claim, agent_id="ag1")), 0, "reclamar de nuevo lo propio es válido")
        self.assertEqual(self.repo.hook(bash_payload(claim, agent_id="ag2")), 2, "otro agente no puede reclamarlo")
        self.assertEqual(self.repo.hook(bash_payload("python3 .claude/bin/agentic.py claim WP-02", agent_id="ag1")), 2,
                         "un agente no puede reclamar dos WP")
        self.assertEqual(self.repo.hook(bash_payload("python3 .claude/bin/agentic.py claim WP-99", agent_id="ag3")), 2)

    def test_snapshot_reinicia_claims(self):
        claim = "python3 .claude/bin/agentic.py claim WP-01"
        self.assertEqual(self.repo.hook(bash_payload(claim, agent_id="ag1")), 0)
        self.repo.run("snapshot", "1")
        self.assertEqual(self.repo.hook(bash_payload(claim, agent_id="ag2")), 0)


class V2EntityTests(Base):
    """Ola 0 (AT), revisor de solo lectura y validaciones del flow v2."""

    def p(self, rel):
        return str(self.repo.dir / rel)

    def test_implementer_no_toca_la_aceptacion(self):
        self.assertEqual(self.repo.hook(write_payload(self.p("acceptance/test_ac_001.py")), wp="WP-01"), 2)
        self.assertEqual(self.repo.hook(write_payload(self.p("acceptance/test_ac_001.py")), wp="AT"), 0)
        self.assertEqual(self.repo.hook(write_payload(self.p("src/a.py")), wp="AT"), 2, "el test-author no implementa")

    def test_revisor_no_escribe_nada(self):
        for rel in ("src/a.py", "review.md", "acceptance/x.py", "qa/x.py"):
            with self.subTest(rel=rel):
                self.assertEqual(self.repo.hook(write_payload(self.p(rel)), wp="REVIEW"), 2)
        self.assertEqual(self.repo.hook(bash_payload("git diff"), wp="REVIEW"), 0)

    def test_claim_at_y_review_en_modo_b(self):
        for ident, agent in (("AT", "a1"), ("REVIEW", "a2")):
            self.assertEqual(self.repo.hook(bash_payload(f"python3 .claude/bin/agentic.py claim {ident}", agent_id=agent)), 0)
        self.assertEqual(self.repo.hook(write_payload(self.p("acceptance/t.py"), agent_id="a1")), 0)
        self.assertEqual(self.repo.hook(write_payload(self.p("src/a.py"), agent_id="a2")), 2)

    def write_manifest(self, m):
        (self.repo.dir / "architecture.md").write_text(f"```json wp-manifest\n{json.dumps(m)}\n```")

    def test_validaciones_v2(self):
        cases = {
            "IDs reservados": lambda m: m["work_packages"][0].update(id="AT"),
            "acceptance sin command": lambda m: m.update(acceptance={"files": ["acceptance/"]}),
            "WP dueño del archivo de decisiones": lambda m: m["work_packages"][0].update(files=["docs/architecture/x.md"]),
            "solape con acceptance": lambda m: m["work_packages"][0].update(files=["acceptance/"]),
        }
        for name, mutate in cases.items():
            with self.subTest(name):
                m = json.loads(json.dumps(MANIFEST))
                mutate(m)
                self.write_manifest(m)
                self.assertEqual(self.repo.run("validate").returncode, 1)

    def test_modelos_de_los_agentes_v2(self):
        agents = self.repo.dir / ".claude/agents"
        for name, wrong in (("test-author", "opus"), ("reviewer", "opus"), ("plan-reviewer", "sonnet")):
            with self.subTest(name):
                f = agents / f"{name}.md"
                original = f.read_text()
                good = "model: opus" if name == "plan-reviewer" else "model: sonnet"
                f.write_text(original.replace(good, f"model: {wrong}"))
                r = self.repo.run("validate")
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertIn(name, r.stderr)
                f.write_text(original)
        self.assertEqual(self.repo.run("validate").returncode, 0)

    def acc(self, code):
        (self.repo.dir / "acc.py").write_text(f"import sys\nprint('tests')\nsys.exit({code})\n")

    def test_aceptacion_rojo_y_verde(self):
        self.acc(1)
        self.assertEqual(self.repo.run("acceptance", "--expect", "red").returncode, 0)
        self.assertEqual(self.repo.run("acceptance", "--expect", "green").returncode, 3)
        self.acc(0)
        r = self.repo.run("acceptance", "--expect", "red")
        self.assertEqual(r.returncode, 3)
        self.assertIn("YA PASAN SIN CÓDIGO", r.stdout)
        self.assertEqual(self.repo.run("acceptance", "--expect", "green").returncode, 0)
        self.assertIn("aceptación (green): OK", self.repo.run("status").stdout)

    def test_aceptacion_comando_inexistente_no_cuenta_como_rojo(self):
        m = json.loads(json.dumps(MANIFEST))
        m["acceptance"]["command"] = "comando-que-no-existe --x"
        self.write_manifest(m)
        r = self.repo.run("acceptance", "--expect", "red")
        self.assertEqual(r.returncode, 3)
        self.assertIn("ERROR", r.stdout)


class ContentGuardTests(Base):
    """Guardarraíles de contenido adaptados de ECC: bypass de hooks, config, tests desactivados y secretos."""
    manifest = dict(MANIFEST, work_packages=[
        {"id": "WP-01", "wave": 1, "depends_on": [], "files": ["src/a.py", "tests/test_a.py", "pyproject.toml", "setup.cfg"]},
        {"id": "WP-02", "wave": 1, "depends_on": [], "files": ["ruff.toml"], "config_edit": True},
    ])

    def w(self, rel, content, wp="WP-01", tool="Write", old=None):
        tinput = {"file_path": str(self.repo.dir / rel)}
        if tool == "Write":
            tinput["content"] = content
        else:
            tinput.update(new_string=content, old_string=old or "")
        return self.repo.hook({"tool_name": tool, "tool_input": tinput}, wp=wp)

    def test_no_verify_bloqueado_para_todos(self):
        for cmd in ["git commit --no-verify -m x", "git commit -n -m x", "git -c core.hooksPath=/dev/null commit -m x", "sh -c 'git commit --no-verify'",
                    "git push --no-verify"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.repo.hook(bash_payload(cmd)), 2, "también en la sesión principal")
        for cmd in ["git commit -m 'arregla -n'", "git log -n 5", "git commit -m x"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.repo.hook(bash_payload(cmd)), 0)

    def test_config_existente_protegida(self):
        self.repo.write("pyproject.toml", "[tool.ruff]\nline-length = 88\n")
        self.assertEqual(self.w("pyproject.toml", "[tool.ruff]\nline-length = 300\n"), 2)
        self.assertEqual(self.w("setup.cfg", "x"), 0, "crear configuración nueva está permitido")
        self.repo.write("ruff.toml", "a")
        self.assertEqual(self.w("ruff.toml", "b", wp="WP-02"), 0, "config_edit: true lo permite")

    def test_no_se_desactivan_tests(self):
        self.assertEqual(self.w("tests/test_a.py", "import unittest\n@unittest.skip('x')\ndef test(): pass\n"), 2)
        self.assertEqual(self.w("tests/test_a.py", "import pytest\n@pytest.mark.xfail\ndef test(): pass\n"), 2)
        self.assertEqual(self.w("tests/test_a.py", "it.only('x', () => {})", tool="Edit"), 2)
        self.assertEqual(self.w("tests/test_a.py", "@unittest.skipIf(os.geteuid() == 0, 'root')\ndef test(): pass\n"), 0)
        self.assertEqual(self.w("src/a.py", "# pytest.mark.skip en un comentario de código\n"), 0, "solo en ficheros de test")
        self.assertEqual(self.w("tests/test_a.py", "@unittest.skip('ya estaba')\nX", tool="Edit",
                                old="@unittest.skip('ya estaba')\n"), 0, "no cuenta lo que ya existía")

    def test_secretos(self):
        for secret in ["AKIA" + "A" * 16, "ghp_" + "a" * 36, "sk-ant-" + "a" * 30,
                       "-----BEGIN RSA PRIVATE KEY-----", "xoxb-" + "1" * 12]:
            with self.subTest(secret=secret[:8]):
                self.assertEqual(self.w("src/a.py", f"TOKEN = '{secret}'\n"), 2)
        self.assertEqual(self.w("src/a.py", "TOKEN = os.environ['API_TOKEN']\n"), 0)


class WorkflowCommandTests(Base):
    """Comandos deterministas que usa el workflow nativo a través del agente gatekeeper."""

    def test_open_wave_snapshot_y_json(self):
        self.repo.hook(bash_payload("python3 .claude/bin/agentic.py claim WP-01", agent_id="viejo"))
        r = self.repo.run("open-wave", "1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), {"wave": 1, "work_packages": ["WP-01", "WP-02"]}, "solo JSON en stdout")
        self.assertTrue((self.repo.dir / ".claude/state/snapshot-1.json").exists())
        self.assertEqual(self.repo.hook(bash_payload("python3 .claude/bin/agentic.py claim WP-01", agent_id="nuevo")), 0,
                         "open-wave reinicia los claims de la etapa anterior")
        self.assertEqual(self.repo.run("open-wave", "9").returncode, 3)

    def test_close_wave(self):
        self.repo.run("open-wave", "1")
        self.repo.write("src/a.py")
        r = self.repo.run("close-wave", "1", "WP-01=done", "WP-02=done")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = self.repo.run("status").stdout
        self.assertIn("ola 1: OK", st)
        self.assertIn("[done]", st)
        self.repo.run("open-wave", "1")
        self.assertEqual(self.repo.run("close-wave", "1", "WP-01=done", "WP-02=blocker").returncode, 3)
        self.assertIn("ola 1: REVISAR", self.repo.run("status").stdout)
        self.repo.run("open-wave", "1")
        self.repo.write("README.md")
        self.assertEqual(self.repo.run("close-wave", "1", "WP-01=done", "WP-02=done").returncode, 3, "escritura ajena")
        self.assertEqual(self.repo.run("close-wave", "1", "WP-77=done").returncode, 1)


class PipelineCommandTests(Base):
    """Comandos que usa el workflow agentic-implement (los ejecuta el gatekeeper)."""
    manifest = dict(MANIFEST, verify={"tests": "python3 ok.py", "lint": "python3 lint.py"})

    def setUp(self):
        super().setUp()
        self.repo.write("ok.py", "print('tests ok')\n")
        self.repo.write("lint.py", "import sys\nsys.exit(0)\n")
        self.repo.write("acc.py", "import sys\nsys.exit(0)\n")

    def test_pipeline_plan(self):
        (self.repo.dir / "architecture.md").write_text(
            "# A\nTipo: fix · Tamaño: pequeño\n\n```json wp-manifest\n" + json.dumps(self.manifest) + "\n```\n")
        r = self.repo.run("pipeline-plan")
        self.assertEqual(r.returncode, 0, r.stderr)
        plan = json.loads(r.stdout)
        self.assertEqual(plan["waves"], [1, 2])
        self.assertEqual(plan["work_packages"]["1"], ["WP-01", "WP-02"])
        self.assertEqual(plan["type"], "fix")
        self.assertTrue(plan["acceptance"])
        self.assertEqual(plan["max_fix_cycles"], 2)
        self.assertEqual(plan["wave_of"]["WP-03"], 2)
        self.assertEqual(plan["agents"]["WP-01"], "implementer")

    def test_open_y_close_stage_con_etiquetas(self):
        (self.repo.dir / "acc.py").write_text("import sys\nsys.exit(1)\n")  # antes del snapshot: no es de nadie
        r = self.repo.run("open-stage", "acceptance")
        self.assertEqual(json.loads(r.stdout), {"stage": "acceptance", "owners": ["AT"]})
        self.repo.write("acceptance/test_ac_001.py")
        r = self.repo.run("close-stage", "acceptance", "AT=done", "--expect", "red")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("ROJO", r.stdout)
        (self.repo.dir / "acc.py").write_text("import sys\nsys.exit(0)\n")
        self.repo.run("open-stage", "acceptance")
        self.assertEqual(self.repo.run("close-stage", "acceptance", "AT=done", "--expect", "red").returncode, 3,
                         "si ya pasan sin código, la ola 0 falla")
        self.assertEqual(self.repo.run("open-stage", "inventada").returncode, 1)

    def test_close_stage_fix_cuenta_ciclos(self):
        for _ in range(2):
            self.repo.run("open-stage", "1")
            self.repo.run("close-stage", "1", "WP-02=done", "--fix")
        ledger = json.loads((self.repo.dir / ".claude/state/ledger.json").read_text())
        self.assertEqual(ledger["WP-02"]["fix_count"], 2)

    def test_verify_json(self):
        r = self.repo.run("verify")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        names = [p["name"] for p in out["phases"]]
        self.assertEqual(names, ["build", "types", "lint", "tests", "acceptance"])
        self.assertTrue(out["phases"][0]["skipped"])
        self.repo.write("lint.py", "import sys\nsys.exit(2)\n")
        r = self.repo.run("verify")
        self.assertEqual(r.returncode, 3)
        self.assertFalse(json.loads(r.stdout)["ok"])

    def test_verify_mal_formado(self):
        m = dict(self.manifest, verify={"deploy": "x"})
        (self.repo.dir / "architecture.md").write_text("```json wp-manifest\n" + json.dumps(m) + "\n```")
        self.assertEqual(self.repo.run("validate").returncode, 1)

    def test_sync_permissions(self):
        local = self.repo.dir / ".claude/settings.local.json"
        local.write_text(json.dumps({"permissions": {"allow": ["Read"]}, "otra": 1}))
        r = self.repo.run("sync-permissions")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(local.read_text())
        allow = data["permissions"]["allow"]
        for rule in ["Read", "Workflow(agentic-implement)", "Bash(python3 -m unittest:*)", "Bash(python3 acc.py)",
                     "Bash(python3 ok.py:*)"]:
            self.assertIn(rule, allow)
        self.assertEqual(data["otra"], 1, "conserva el resto del fichero")
        self.repo.run("sync-permissions")
        self.assertEqual(len(json.loads(local.read_text())["permissions"]["allow"]), len(allow), "idempotente")


class BrownfieldTests(Base):
    """Plan estilo PRP (referencias mirror validadas) y línea base de regresión."""
    manifest = dict(MANIFEST, verify={"tests": "python3 t.py", "lint": "python3 l.py"})

    def set_manifest(self, m):
        (self.repo.dir / "architecture.md").write_text("```json wp-manifest\n" + json.dumps(m) + "\n```")

    def test_mirror_validado(self):
        self.repo.write("legacy/orders.py", "\n".join(f"linea {i}" for i in range(1, 41)))
        cases = {
            "legacy/orders.py": 0, "legacy/orders.py:5": 0, "legacy/orders.py:1-40": 0,
            "legacy/orders.py:30-41": 1, "legacy/inventado.py": 1, "legacy/orders.py:abc": 1, "../fuera.py": 1,
            "legacy/orders.py:20-10": 1,
        }
        for ref, expected in cases.items():
            with self.subTest(ref=ref):
                m = json.loads(json.dumps(self.manifest))
                m["work_packages"][0]["mirror"] = [ref]
                self.set_manifest(m)
                r = self.repo.run("validate")
                self.assertEqual(r.returncode, expected, r.stderr)

    def scripts(self, tests, lint):
        self.repo.write("t.py", f"import sys\nsys.exit({tests})\n")
        self.repo.write("l.py", f"import sys\nsys.exit({lint})\n")
        self.repo.write("acc.py", "import sys\nsys.exit(0)\n")

    def test_regresion_frente_a_fallo_previo(self):
        self.scripts(tests=0, lint=1)  # antes de tocar nada: lint ya falla
        r = self.repo.run("baseline")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["preexisting_failures"], ["lint"])
        out = json.loads(self.repo.run("verify").stdout)
        self.assertTrue(out["ok"], "un fallo previo no bloquea")
        self.assertEqual(out["preexisting_failures"], ["lint"])
        self.scripts(tests=1, lint=1)  # ahora los tests, que pasaban, fallan
        r = self.repo.run("verify")
        self.assertEqual(r.returncode, 3)
        out = json.loads(r.stdout)
        self.assertEqual(out["blocking"], ["tests"])
        status = {p["name"]: p.get("status") for p in out["phases"]}
        self.assertEqual(status["tests"], "regresión")
        self.assertEqual(status["lint"], "fallo previo")
        self.assertIn("línea base: con fallos previos: lint", self.repo.run("status").stdout)

    def test_sin_linea_base_un_fallo_bloquea(self):
        self.scripts(tests=0, lint=1)
        r = self.repo.run("verify")
        self.assertEqual(r.returncode, 3)
        self.assertEqual(json.loads(r.stdout)["blocking"], ["lint"])

    def test_baseline_con_comando_inexistente_falla(self):
        m = dict(self.manifest, verify={"tests": "comando-que-no-existe"})
        self.set_manifest(m)
        self.assertEqual(self.repo.run("baseline").returncode, 1)

    def test_pipeline_plan_indica_linea_base(self):
        self.scripts(0, 0)
        self.assertTrue(json.loads(self.repo.run("pipeline-plan").stdout)["baseline"])


@unittest.skipUnless(shutil.which("node"), "node no está instalado")
class WorkflowLogicTests(unittest.TestCase):
    def test_escenarios_del_workflow(self):
        r = subprocess.run(["node", str(SCRIPT.parent / "test_workflow.mjs")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class HookFailClosedTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(raw_manifest='{"work_packages": [ roto')

    def tearDown(self):
        self.repo.cleanup()

    def test_manifiesto_roto_bloquea_dentro_de_un_wp(self):
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/a.py")), wp="WP-01"), 2)

    def test_manifiesto_roto_bloquea_subagente(self):
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/a.py"), agent_id="ag1")), 2)

    def test_manifiesto_roto_no_bloquea_hilo_principal(self):
        self.assertEqual(self.repo.hook(write_payload(str(self.repo.dir / "src/a.py"))), 0)

    def test_stdin_ilegible_dentro_de_un_wp(self):
        r = self.repo.run("hook", stdin="no es json", env={"AGENTIC_WP": "WP-01"})
        self.assertEqual(r.returncode, 2)


class HookBashTests(Base):
    BLOCKED = [
        "git commit -am x", "git -C . commit -am x", "git -c user.name=x commit -m y", "command git push",
        "sh -c 'git commit -m x'", 'bash -c "git checkout main"', "cd src && git add .", "git stash",
        "npm install lodash", "cd x && pnpm add zod", "pip install requests", "uv add httpx",
        "claude -p hola", "claude --print hola",
    ]
    ALLOWED = [
        "git status", "git diff src/add.py", "git log --oneline -5", "git show HEAD:src/a.py",
        "python3 -m unittest tests.test_a", "npm test", "npm run build", "grep -r commit src",
        "claude --version",
    ]

    def test_bloqueados(self):
        for cmd in self.BLOCKED:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.repo.hook(bash_payload(cmd), wp="WP-01"), 2)

    def test_permitidos(self):
        for cmd in self.ALLOWED:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.repo.hook(bash_payload(cmd), wp="WP-01"), 0)

    def test_hilo_principal_puede_usar_git(self):
        self.assertEqual(self.repo.hook(bash_payload("git commit -am x")), 0)


class CheckStageTests(Base):
    def setUp(self):
        super().setUp()
        self.repo.write("src/a.py", "v1")
        subprocess.run(["git", "add", "-A"], cwd=self.repo.dir, check=True)
        self.repo.run("snapshot", "1")

    def test_cambios_propios_ok(self):
        self.repo.write("src/a.py", "v2")
        self.repo.write("src/b/nuevo.py")
        self.assertEqual(self.repo.run("check-wave", "1").returncode, 0)

    def test_cambio_ajeno_y_borrado_fallan(self):
        self.repo.write("README.md")
        r = self.repo.run("check-wave", "1")
        self.assertEqual(r.returncode, 3)
        self.assertIn("README.md", r.stdout)

    def test_borrado_cuenta_como_cambio(self):
        (self.repo.dir / "src/a.py").unlink()
        self.repo.run("snapshot", "2")
        self.repo.write("src/a.py", "v1")
        self.assertEqual(self.repo.run("check-wave", "2").returncode, 3, "src/a.py es de la ola 1, no de la 2")

    def test_artefactos_ignorados(self):
        self.repo.write("src/__pycache__/a.cpython-314.pyc")
        self.repo.write("node_modules/x/index.js")
        self.repo.write("dist/out.js")  # ignorado por el manifiesto
        self.repo.write("coverage/lcov.info")
        self.assertEqual(self.repo.run("check-wave", "1").returncode, 0)

    def test_ola_siguiente_no_puede_tocar_la_anterior(self):
        self.repo.run("snapshot", "2")
        self.repo.write("src/a.py", "v3")
        self.assertEqual(self.repo.run("check-wave", "2").returncode, 3)


class LauncherTests(Base):
    def setUp(self):
        super().setUp()
        self.bin = Path(tempfile.mkdtemp(prefix="fake-claude-"))
        fake = self.bin / "claude"
        fake.write_text(FAKE_CLAUDE)
        fake.chmod(0o755)
        self.logs = Path(tempfile.mkdtemp(prefix="fake-logs-"))
        self.repo.env.update(PATH=f"{self.bin}{os.pathsep}{os.environ['PATH']}", FAKE_LOG_DIR=str(self.logs))

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.bin, ignore_errors=True)
        shutil.rmtree(self.logs, ignore_errors=True)

    def args(self, wp):
        return json.loads((self.logs / f"{wp}.args").read_text())

    def test_ola_en_paralelo(self):
        start = time.time()
        r = self.repo.run("run-wave", "1", env={"FAKE_SLEEP": "1.5"})
        elapsed = time.time() - start
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertLess(elapsed, 2.8, "los dos WP deberían correr a la vez")
        self.assertNotIn("USD", r.stdout, "sin información de coste")

    def test_flags_de_cada_agente(self):
        self.repo.run("run-wave", "1")
        a = self.args("WP-01")
        self.assertEqual(a[a.index("--agent") + 1], "implementer")
        self.assertEqual(a[a.index("--model") + 1], "sonnet")
        self.assertNotIn("--max-budget-usd", a)
        self.assertIn("--strict-mcp-config", a)
        self.assertIn("Bash(python3 -m unittest:*)", a)
        self.assertNotIn("Bash", a, "nunca Bash sin restricción")
        self.assertFalse((self.logs / "WP-03.args").exists(), "WP-03 es de la ola 2")

    def test_modelo_no_se_puede_cambiar(self):
        (self.repo.dir / ".claude/agentic.json").write_text(json.dumps({"models": {"qa": "claude-opus-5-5"}}))
        self.repo.run("run-qa", env={"AGENTIC_QA_MODEL": "opus", "AGENTIC_IMPLEMENTER_MODEL": "opus"})
        a = self.args("QA")
        self.assertEqual(a[a.index("--model") + 1], "sonnet")
        self.assertEqual(a[a.index("--agent") + 1], "qa")

    def test_agente_con_otro_modelo_no_valida(self):
        f = self.repo.dir / ".claude/agents/qa.md"
        f.write_text(f.read_text().replace("model: sonnet", "model: claude-opus-5-5"))
        r = self.repo.run("run-wave", "1")
        self.assertEqual(r.returncode, 1)
        self.assertIn("model: sonnet", r.stderr)
        self.assertFalse((self.logs / "WP-01.args").exists())

    def test_arquitecto_debe_ser_opus(self):
        cmds = self.repo.dir / ".claude/commands"
        cmds.mkdir(parents=True, exist_ok=True)
        (cmds / "architect.md").write_text("---\ndescription: x\nmodel: opus\n---\nx")
        self.assertEqual(self.repo.run("validate").returncode, 0)
        (cmds / "architect.md").write_text("---\ndescription: x\nmodel: claude-opus-5-5\n---\nx")
        r = self.repo.run("validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("último Opus", r.stderr)

    def test_definiciones_reales_usan_alias(self):
        sys.path.insert(0, str(SCRIPT.parent))
        import agentic
        root = SCRIPT.parents[2]
        self.assertEqual(agentic.frontmatter_model(root / ".claude/commands/architect.md"), "opus")
        for name in ("implementer", "qa"):
            self.assertEqual(agentic.frontmatter_model(root / f".claude/agents/{name}.md"), "sonnet")
        for name in ("implement",):
            self.assertEqual(agentic.frontmatter_model(root / f".claude/commands/{name}.md"), "sonnet")

    def test_orquestador_debe_ser_sonnet(self):
        cmds = self.repo.dir / ".claude/commands"
        cmds.mkdir(parents=True, exist_ok=True)
        (cmds / "implement.md").write_text("---\ndescription: x\nmodel: opus\n---\nx")
        r = self.repo.run("validate")
        self.assertEqual(r.returncode, 1)
        self.assertIn("/implement", r.stderr)

    def test_agente_especializado_debe_existir_y_ser_sonnet(self):
        m = json.loads(json.dumps(MANIFEST))
        m["work_packages"][0]["agent"] = "frontend"
        (self.repo.dir / "architecture.md").write_text(f"```json wp-manifest\n{json.dumps(m)}\n```")
        r = self.repo.run("validate")
        self.assertIn("no existe", r.stderr)
        (self.repo.dir / ".claude/agents/frontend.md").write_text("---\nname: frontend\nmodel: haiku\n---\nx")
        self.assertIn("no 'haiku'", self.repo.run("validate").stderr)
        (self.repo.dir / ".claude/agents/frontend.md").write_text("---\nname: frontend\nmodel: sonnet\n---\nx")
        self.assertEqual(self.repo.run("validate").returncode, 0)

    def env_of(self, wp):
        return json.loads((self.logs / f"{wp}.env").read_text())

    def test_suscripcion_no_hereda_api_key(self):
        self.repo.run("run-wave", "1", env={"ANTHROPIC_API_KEY": "sk-test", "ANTHROPIC_AUTH_TOKEN": "tok"})
        self.assertEqual(self.env_of("WP-01"), {"ANTHROPIC_API_KEY": None, "ANTHROPIC_AUTH_TOKEN": None})

    def test_auth_inherit_mantiene_api_key(self):
        (self.repo.dir / ".claude").mkdir(exist_ok=True)
        (self.repo.dir / ".claude/agentic.json").write_text(json.dumps({"auth": "inherit"}))
        self.repo.run("run-wave", "1", env={"ANTHROPIC_API_KEY": "sk-test"})
        self.assertEqual(self.env_of("WP-01")["ANTHROPIC_API_KEY"], "sk-test")

    def test_solo_un_wp(self):
        r = self.repo.run("run-wave", "1", "WP-02")
        self.assertEqual(r.returncode, 0)
        self.assertFalse((self.logs / "WP-01.args").exists())
        self.assertEqual(self.repo.run("run-wave", "1", "WP-03").returncode, 1)

    def prompt_of(self, wp):
        return self.args(wp)[1]

    def test_fix_solo_si_se_pide(self):
        runs = self.repo.dir / ".claude/state/runs"
        runs.mkdir(parents=True, exist_ok=True)
        (runs / "QA.json").write_text(json.dumps({"result": "STATUS: FAIL"}))
        self.repo.run("run-wave", "1", "WP-02")
        self.assertNotIn("QA.json", self.prompt_of("WP-02"), "sin --fix no debe usar un informe de QA viejo")
        self.repo.run("run-wave", "1", "WP-02", "--fix")
        self.assertIn("QA.json", self.prompt_of("WP-02"))

    def test_fix_sin_informe_falla(self):
        r = self.repo.run("run-wave", "1", "WP-01", "--fix")
        self.assertEqual(r.returncode, 1)
        self.assertIn("run-review o run-qa", r.stderr)

    # ---------- ledger, mark y stop ----------

    def status(self):
        return self.repo.run("status").stdout

    def test_ledger_tras_una_ola(self):
        self.assertEqual(self.repo.run("run-wave", "1").returncode, 0)
        st = self.status()
        self.assertIn("[done]", st)
        self.assertIn("WP-01 (sonnet)", st)
        self.assertIn("modo A", st)
        self.assertIn("ola 1: OK", st)
        self.assertNotIn("WP-03", st, "WP-03 es de la ola 2 y no se ha lanzado")

    def test_mark(self):
        r = self.repo.run("mark", "WP-02", "blocker", "falta", "el", "contrato")
        self.assertEqual(r.returncode, 0, r.stderr)
        st = self.status()
        self.assertIn("[blocker]", st)
        self.assertIn("falta el contrato", st)
        self.assertEqual(self.repo.run("mark", "WP-02", "raro").returncode, 1)
        self.assertEqual(self.repo.run("mark", "WP-99", "done").returncode, 1)

    def test_claim_registra_modo_workflow(self):
        self.repo.hook(bash_payload("python3 .claude/bin/agentic.py claim WP-01", agent_id="ag1"))
        st = self.status()
        self.assertIn("[running]", st)
        self.assertIn("WP-01 (sonnet)", st)
        self.assertIn("modo workflow", st)

    def test_stop_para_la_ola(self):
        proc = subprocess.Popen([sys.executable, str(SCRIPT), "run-wave", "1"], cwd=self.repo.dir,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                env=dict(self.repo.env, FAKE_SLEEP="30"))
        ledger = self.repo.dir / ".claude/state/ledger.json"
        deadline = time.time() + 10
        while time.time() < deadline:
            try:
                d = json.loads(ledger.read_text())
                if all(d.get(w, {}).get("pid") for w in ("WP-01", "WP-02")):
                    break
            except (OSError, json.JSONDecodeError):
                pass
            time.sleep(0.1)
        start = time.time()
        r = self.repo.run("stop")
        self.assertIn("parado", r.stdout)
        out, _ = proc.communicate(timeout=15)
        self.assertLess(time.time() - start, 10, "stop debe cortar la ola sin esperar a los agentes")
        self.assertEqual(proc.returncode, 3)
        self.assertIn("STOPPED", out)
        self.assertIn("[stopped]", self.status())
        self.assertIn("No hay agentes en marcha", self.repo.run("stop").stdout)

    def test_ola_0_lanza_test_author(self):
        self.assertEqual(self.repo.run("run-acceptance").returncode, 0)
        a = self.args("AT")
        self.assertEqual(a[a.index("--agent") + 1], "test-author")
        self.assertEqual(a[a.index("--model") + 1], "sonnet")

    def test_revision_sin_herramientas_de_escritura(self):
        (self.logs / "x").write_text("")
        r = self.repo.run("run-review", env={"FAKE_STATUS": "PASS"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        a = self.args("REVIEW")
        self.assertEqual(a[a.index("--agent") + 1], "reviewer")
        for tool in ("Write", "Edit"):
            self.assertNotIn(tool, a)

    def test_implementers_pueden_ejecutar_la_aceptacion(self):
        self.repo.run("run-wave", "1")
        self.assertIn("Bash(python3 acc.py:*)", self.args("WP-01"))

    def test_tope_de_fix(self):
        runs = self.repo.dir / ".claude/state/runs"
        runs.mkdir(parents=True, exist_ok=True)
        (runs / "REVIEW.json").write_text(json.dumps({"result": "STATUS: FAIL"}))
        for _ in range(2):
            self.assertEqual(self.repo.run("run-wave", "1", "WP-02", "--fix").returncode, 0)
            self.assertIn("REVIEW.json", self.prompt_of("WP-02"))
        r = self.repo.run("run-wave", "1", "WP-02", "--fix")
        self.assertEqual(r.returncode, 4)
        self.assertIn("agotó", r.stderr)
        self.assertEqual(self.repo.run("run-wave", "1", "WP-01", "--fix").returncode, 0, "el tope es por WP")

    def test_timeout(self):
        start = time.time()
        r = self.repo.run("run-wave", "1", env={"FAKE_SLEEP": "30", "AGENTIC_TIMEOUT_S": "1"})
        self.assertLess(time.time() - start, 10)
        self.assertEqual(r.returncode, 3)
        self.assertIn("TIMEOUT", r.stdout)

    def test_blocker_marca_revisar(self):
        r = self.repo.run("run-wave", "1", env={"FAKE_STATUS": "BLOCKER"})
        self.assertEqual(r.returncode, 3)
        self.assertIn("RESULTADO: REVISAR", r.stdout)

    def test_manifiesto_invalido_no_lanza(self):
        m = json.loads(json.dumps(MANIFEST))
        m["allow_bash"] = ["Bash(*)"]
        (self.repo.dir / "architecture.md").write_text(f"```json wp-manifest\n{json.dumps(m)}\n```")
        self.assertEqual(self.repo.run("run-wave", "1").returncode, 1)
        self.assertFalse((self.logs / "WP-01.args").exists())


if __name__ == "__main__":
    unittest.main()
