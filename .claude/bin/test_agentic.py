"""Tests de los guardarraíles y del lanzador.

Ejecutar: python3 -m unittest discover -s .claude/bin -p "test_*.py"
Cada test trabaja en un repo git temporal; el lanzador usa un `claude` falso, sin coste.
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

MANIFEST = {
    "allow_bash": ["Bash(python3 -m unittest:*)"],
    "ignore": ["dist/"],
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
    time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
    status = os.environ.get("FAKE_STATUS", "DONE" if wp != "QA" else "PASS")
    print(json.dumps({"result": "STATUS: " + status + "\\nWP: " + wp, "total_cost_usd": 0.25}))
""")


class Repo:
    def __init__(self, manifest=MANIFEST, raw_manifest=None):
        self.dir = Path(tempfile.mkdtemp(prefix="agentic-test-"))
        body = raw_manifest if raw_manifest is not None else json.dumps(manifest, indent=2)
        (self.dir / "architecture.md").write_text(f"# A\n\n```json wp-manifest\n{body}\n```\n")
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
        self.assertIn("Coste de la etapa: 0.50 USD", r.stdout)

    def test_flags_de_cada_agente(self):
        self.repo.run("run-wave", "1")
        a = self.args("WP-01")
        self.assertEqual(a[a.index("--agent") + 1], "implementer")
        self.assertEqual(a[a.index("--model") + 1], "claude-sonnet-5-5")
        self.assertEqual(a[a.index("--max-budget-usd") + 1], "3")
        self.assertIn("--strict-mcp-config", a)
        self.assertIn("Bash(python3 -m unittest:*)", a)
        self.assertNotIn("Bash", a, "nunca Bash sin restricción")
        self.assertFalse((self.logs / "WP-03.args").exists(), "WP-03 es de la ola 2")

    def test_config_del_proyecto(self):
        (self.repo.dir / ".claude").mkdir(exist_ok=True)
        (self.repo.dir / ".claude/agentic.json").write_text(json.dumps({"max_budget_usd": {"qa": 1.5}, "models": {"qa": "m-qa"}}))
        self.repo.run("run-qa")
        a = self.args("QA")
        self.assertEqual(a[a.index("--max-budget-usd") + 1], "1.5")
        self.assertEqual(a[a.index("--model") + 1], "m-qa")

    def test_solo_un_wp(self):
        r = self.repo.run("run-wave", "1", "WP-02")
        self.assertEqual(r.returncode, 0)
        self.assertFalse((self.logs / "WP-01.args").exists())
        self.assertEqual(self.repo.run("run-wave", "1", "WP-03").returncode, 1)

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
