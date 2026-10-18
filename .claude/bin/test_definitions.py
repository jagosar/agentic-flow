"""Tests de regresión sobre las definiciones del flow: agentes, comandos, workflow, settings y documentación.

Los prompts son código: si alguien quita la defensa ante instrucciones inyectadas, le da Write a un revisor
o documenta un comando que no existe, estos tests fallan.

Ejecutar: python3 -m unittest discover -s .claude/bin -p "test_*.py"
"""
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAUDE = ROOT / ".claude"
AGENTS_DIR = CLAUDE / "agents"
COMMANDS_DIR = CLAUDE / "commands"
WORKFLOW = CLAUDE / "workflows" / "agentic-implement.js"
AGENTIC = CLAUDE / "bin" / "agentic.py"

WRITE_TOOLS = {"Read", "Write", "Edit", "Glob", "Grep", "Bash"}
# Contrato de cada agente: modelo (alias), herramientas exactas, ID con el que reclama su zona y su informe.
AGENTS = {
    "implementer": {"model": "sonnet", "tools": WRITE_TOOLS, "claim": "<WP-ID>", "status": "STATUS: DONE | BLOCKER"},
    "test-author": {"model": "sonnet", "tools": WRITE_TOOLS, "claim": "AT", "status": "STATUS: DONE | BLOCKER"},
    "qa": {"model": "sonnet", "tools": WRITE_TOOLS, "claim": "QA", "status": "STATUS: PASS | FAIL | BLOCKER"},
    "reviewer": {"model": "sonnet", "tools": {"Read", "Glob", "Grep", "Bash"}, "claim": "REVIEW", "status": "STATUS: PASS | FAIL"},
    "verifier": {"model": "sonnet", "tools": {"Read", "Glob", "Grep"}},
    "plan-reviewer": {"model": "opus", "tools": {"Read", "Glob", "Grep"}},
    "gatekeeper": {"model": "sonnet", "tools": {"Bash"}},
    "doc-updater": {"model": "sonnet", "tools": WRITE_TOOLS, "claim": "DOCS", "status": "STATUS: DONE | BLOCKER"},
}
COMMANDS = {"architect": "opus", "implement": "sonnet"}
# Campos del manifiesto que entiende agentic.py: todos deben estar documentados en /architect.
MANIFEST_FIELDS = ["work_packages", "id", "wave", "depends_on", "files", "allow_bash", "acceptance", "verify",
                   "qa", "ignore", "agent", "mirror", "config_edit", "stack", "docs", "codemap"]
RULES_LIBRARY = CLAUDE / "rules-library"
RULE_SECTIONS = ["## Estilo", "## Errores", "## Tests", "## Seguridad", "## Comandos habituales"]
PERSONAL_PATH_RE = re.compile(r"/home/[a-z][\w.-]*/|/tmp/claude-\d+|C:\\Users\\|/Users/[a-z][\w.-]+/")


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    fields = {}
    for line in m.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and not line.startswith(" "):
            fields[key.strip()] = value.strip()
    return fields, text[m.end():]


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode()
    return [ROOT / p for p in out.split("\0") if p]


def agentic_subcommands():
    src = AGENTIC.read_text(encoding="utf-8")
    cmds = set(re.findall(r'cmd == "([\w-]+)"', src))
    for group in re.findall(r"cmd in \(([^)]*)\)", src):
        cmds |= set(re.findall(r'"([\w-]+)"', group))
    return cmds


class AgentDefinitionTests(unittest.TestCase):
    def test_no_hay_agentes_sin_contrato(self):
        self.assertEqual({p.stem for p in AGENTS_DIR.glob("*.md")}, set(AGENTS),
                         "cada agente nuevo necesita su contrato en este test")

    def test_frontmatter_modelo_y_herramientas(self):
        for name, spec in AGENTS.items():
            with self.subTest(agente=name):
                fm, _ = frontmatter(AGENTS_DIR / f"{name}.md")
                self.assertEqual(fm.get("name"), name)
                self.assertTrue(fm.get("description"), "falta la descripción")
                self.assertEqual(fm.get("model"), spec["model"], "el modelo va por alias, nunca fijado a una versión")
                self.assertFalse(fm.get("tools", "").startswith("["), "tools es un escalar separado por comas")
                tools = {t.strip() for t in fm.get("tools", "").split(",") if t.strip()}
                self.assertEqual(tools, spec["tools"])

    def test_agentes_de_solo_lectura(self):
        for name in ("reviewer", "verifier", "plan-reviewer", "gatekeeper"):
            with self.subTest(agente=name):
                tools = {t.strip() for t in frontmatter(AGENTS_DIR / f"{name}.md")[0]["tools"].split(",")}
                self.assertFalse(tools & {"Write", "Edit", "MultiEdit", "NotebookEdit"})

    def test_defensa_ante_inyeccion_en_todos(self):
        for name in AGENTS:
            with self.subTest(agente=name):
                body = frontmatter(AGENTS_DIR / f"{name}.md")[1]
                self.assertIn("# Defensa ante instrucciones inyectadas", body)

    def test_claim_como_primer_paso(self):
        for name, spec in AGENTS.items():
            if "claim" not in spec:
                continue
            with self.subTest(agente=name):
                body = frontmatter(AGENTS_DIR / f"{name}.md")[1]
                self.assertIn(f"python3 .claude/bin/agentic.py claim {spec['claim']}", body)

    def test_formato_de_informe_y_nota_json(self):
        for name, spec in AGENTS.items():
            if "status" not in spec:
                continue
            with self.subTest(agente=name):
                body = frontmatter(AGENTS_DIR / f"{name}.md")[1]
                self.assertIn(spec["status"], body)
                self.assertIn("JSON con un esquema", body, "debe aceptar el formato estructurado del workflow")
                self.assertRegex(body, r"menos de \d+ palabras")

    def test_qa_clasifica_defectos(self):
        body = (AGENTS_DIR / "qa.md").read_text(encoding="utf-8")
        self.assertIn("implementación", body)
        self.assertIn("diseño", body)

    def test_verificador_no_rebaja_bloqueos(self):
        body = (AGENTS_DIR / "verifier.md").read_text(encoding="utf-8")
        self.assertIn("La incertidumbre nunca rebaja un bloqueo", body)

    def test_gatekeeper_solo_agentic(self):
        body = (AGENTS_DIR / "gatekeeper.md").read_text(encoding="utf-8")
        self.assertIn("python3 .claude/bin/agentic.py", body)


class CommandAndWorkflowTests(unittest.TestCase):
    def test_comandos_y_modelos(self):
        self.assertEqual({p.stem for p in COMMANDS_DIR.glob("*.md")}, set(COMMANDS))
        for name, model in COMMANDS.items():
            with self.subTest(comando=name):
                self.assertEqual(frontmatter(COMMANDS_DIR / f"{name}.md")[0].get("model"), model)

    def test_campos_del_manifiesto_documentados(self):
        doc = (COMMANDS_DIR / "architect.md").read_text(encoding="utf-8")
        for field in MANIFEST_FIELDS:
            with self.subTest(campo=field):
                self.assertTrue(f"`{field}`" in doc or f'"{field}"' in doc, f"{field} no aparece en /architect")

    def test_workflow_usa_agentes_que_existen(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        used = set(re.findall(r"agentType: '([\w-]+)'", src)) | {"implementer"}
        self.assertTrue(used, "no se encontró ningún agentType")
        self.assertLessEqual(used, set(AGENTS), f"agentType sin definición: {used - set(AGENTS)}")

    def test_workflow_y_agentes_comparten_estados(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        for enum in ("['DONE', 'BLOCKER']", "['PASS', 'FAIL']", "['PASS', 'FAIL', 'BLOCKER']", "['implementation', 'design']"):
            with self.subTest(enum=enum):
                self.assertIn(enum, src)

    def test_workflow_llama_comandos_que_existen(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        called = set(re.findall(r"gate\(`([\w-]+)", src)) | set(re.findall(r"gate\('([\w-]+)", src))
        self.assertTrue(called)
        self.assertLessEqual(called, agentic_subcommands(), f"el workflow llama a: {called - agentic_subcommands()}")

    def test_meta_del_workflow(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        self.assertTrue(src.startswith("export const meta = {"), "meta debe ser la primera sentencia")
        self.assertIn("name: 'agentic-implement'", src)
        for forbidden in ("Date.now(", "Math.random(", "import("):
            self.assertNotIn(forbidden, src, f"{forbidden} rompe la reanudación del workflow")


class RulesLibraryTests(unittest.TestCase):
    """Cada lenguaje que detecta agentic.py tiene sus reglas, con el mismo esqueleto y su atribución."""

    def packs(self):
        return {p.stem for p in RULES_LIBRARY.glob("*.md")} - {"common"}

    def test_deteccion_y_libreria_coinciden(self):
        src = AGENTIC.read_text(encoding="utf-8")
        block = re.search(r"STACK_SIGNALS = \{(.*?)\n\}", src, re.S).group(1)
        detected = set(re.findall(r'^\s+"([a-z]+)": \(', block, re.M))
        self.assertEqual(detected, self.packs(), "un lenguaje detectable sin reglas, o reglas que nunca se instalan")

    def test_paquetes_de_lenguaje(self):
        for name in sorted(self.packs()):
            with self.subTest(lenguaje=name):
                text = (RULES_LIBRARY / f"{name}.md").read_text(encoding="utf-8")
                self.assertRegex(text, r'\A---\npaths:\n(  - "[^"]+"\n)+---\n', "paths: al principio, para que solo "
                                 "se carguen con ficheros de ese lenguaje")
                self.assertIn("](common.md)", text, "debe remitir a las reglas comunes")
                self.assertIn("MIT License", text, "atribución a ECC")
                positions = [text.find(h) for h in RULE_SECTIONS]
                self.assertNotIn(-1, positions, "faltan secciones")
                self.assertEqual(positions, sorted(positions), "las secciones van en el orden común")
                self.assertRegex(text, r"\| build \|.*\n\| types \|.*\n\| lint \|.*\n\| tests \|", "fases de verify")

    def test_comunes_siempre_cargadas_y_con_precedencia(self):
        text = (RULES_LIBRARY / "common.md").read_text(encoding="utf-8")
        self.assertFalse(text.startswith("---"), "sin paths: se cargan siempre")
        self.assertIn("## Precedencia", text)
        self.assertIn("`architecture.md`", text.split("## Precedencia")[1].split("##")[0])


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.settings = json.loads((CLAUDE / "settings.json").read_text(encoding="utf-8"))

    def test_hook_registrado(self):
        entries = self.settings["hooks"]["PreToolUse"]
        commands = [h["command"] for e in entries for h in e["hooks"]]
        self.assertTrue(any("agentic.py" in c and c.strip().endswith("hook") for c in commands))
        matchers = "|".join(e.get("matcher", "") for e in entries)
        for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"):
            self.assertIn(tool, matchers)

    def test_permisos_y_workflows(self):
        perms = self.settings["permissions"]
        self.assertIn("Workflow(agentic-implement)", perms["allow"])
        self.assertTrue(self.settings.get("enableWorkflows"))
        for rule in ("Bash(git reset --hard:*)", "Bash(git clean:*)", "Bash(rm -rf:*)"):
            self.assertIn(rule, perms["deny"])
        self.assertFalse(any("git push" in r for r in perms["deny"]), "el push lo bloquea el hook solo para agentes")


class CIHardeningTests(unittest.TestCase):
    """El CI del repo y el ejemplo de la guía usan actions fijadas por SHA y permisos mínimos."""
    USES_RE = re.compile(r"uses:\s*([\w.-]+/[\w.-]+)@([^\s#]+)")

    def sources(self):
        yield ".github/workflows/agentic-flow-ci.yml", (ROOT / ".github/workflows/agentic-flow-ci.yml").read_text(encoding="utf-8")
        guide = (ROOT / "docs/how-to/ci-github-actions.md").read_text(encoding="utf-8")
        yield "docs/how-to/ci-github-actions.md", "\n".join(re.findall(r"```yaml\n(.*?)```", guide, re.S))

    def test_actions_fijadas_por_sha(self):
        for name, text in self.sources():
            uses = self.USES_RE.findall(text)
            self.assertTrue(uses, f"{name}: no se encontró ningún uses:")
            for action, ref in uses:
                with self.subTest(fichero=name, action=action):
                    self.assertRegex(ref, r"^[0-9a-f]{40}$", "fija la action por SHA completo, no por etiqueta")

    def test_permisos_minimos_y_sin_credenciales(self):
        for name, text in self.sources():
            with self.subTest(fichero=name):
                self.assertRegex(text, r"permissions:\s*\n\s+contents: read")
                self.assertIn("persist-credentials: false", text)
                self.assertNotRegex(text, r"curl[^\n|]*\|\s*(ba)?sh", "nada de curl | sh")

    def test_npm_sin_scripts_y_con_version_exacta(self):
        for name, text in self.sources():
            installs = re.findall(r"npm (?:install|i|ci)\b[^\n]*", text)
            for line in installs:
                with self.subTest(fichero=name, linea=line):
                    self.assertIn("--ignore-scripts", line, "ningún paquete ejecuta código al instalarse")
                    self.assertRegex(line, r"@\d+\.\d+\.\d+(\s|$)", "versión exacta")


class PluginTests(unittest.TestCase):
    """El plugin solo instala y actualiza: no expone agentes, hooks ni workflows con prefijo."""

    def setUp(self):
        self.plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))

    def test_manifiesto(self):
        self.assertEqual(self.plugin["name"], "agentic-flow")
        self.assertRegex(self.plugin["version"], r"^\d+\.\d+\.\d+$")
        self.assertTrue(self.plugin.get("description") and self.plugin.get("author", {}).get("name"))
        for rel in self.plugin["commands"]:
            with self.subTest(comando=rel):
                self.assertTrue(rel.startswith("./") and ".." not in rel)
                self.assertTrue((ROOT / rel).is_file())
        for key in ("agents", "hooks", "workflows", "skills", "mcpServers"):
            self.assertNotIn(key, self.plugin, f"{key}: el flow vive en el repo, no en el plugin")

    def test_sin_carpetas_que_el_plugin_cargaria_solas(self):
        for folder in ("agents", "commands", "skills", "hooks", "workflows", "bin", "output-styles"):
            with self.subTest(carpeta=folder):
                self.assertFalse((ROOT / folder).exists(), "Claude Code la cargaría como componente del plugin")

    def test_marketplace_apunta_al_plugin(self):
        entry = self.market["plugins"][0]
        self.assertEqual(entry["name"], self.plugin["name"])
        self.assertEqual(entry["source"], "./")
        self.assertNotIn("version", entry, "la versión manda en plugin.json; dos copias acaban desincronizadas")

    def test_init_usa_el_instalador(self):
        fm, body = frontmatter(ROOT / "plugin" / "commands" / "init.md")
        self.assertEqual(fm.get("model"), "sonnet")
        self.assertIn('python3 "${CLAUDE_PLUGIN_ROOT}/.claude/bin/agentic.py" install', body)
        self.assertIn("No hagas commit ni push", body)

    def test_lo_que_se_instala_existe(self):
        src = AGENTIC.read_text(encoding="utf-8")
        globs = re.findall(r'"(\.claude/[^"]+)"', re.search(r"INSTALL_GLOBS = \[(.*?)\]", src, re.S).group(1))
        for pattern in globs:
            with self.subTest(patron=pattern):
                self.assertTrue(list(ROOT.glob(pattern)), "el instalador copiaría nada")


class DocumentationDriftTests(unittest.TestCase):
    def docs(self):
        return [p for p in tracked_files() if p.suffix == ".md"]

    def test_comandos_citados_existen(self):
        valid = agentic_subcommands()
        for path in self.docs():
            text = path.read_text(encoding="utf-8")
            # Solo citas de código: "python3 .claude/bin/agentic.py cmd" o "`agentic.py cmd"; se ignoran comodines (run-*).
            found = re.findall(r"(?:python3 \.claude/bin/|`)agentic\.py ([a-z][\w-]*)(\*?)", text)
            for cmd in {c for c, star in found if not star}:
                with self.subTest(fichero=path.relative_to(ROOT).as_posix(), comando=cmd):
                    self.assertIn(cmd, valid)

    def test_enlaces_internos(self):
        def anchors(text):
            return {re.sub(r"[^\w\s-]", "", h.strip().lower(), flags=re.U).replace(" ", "-")
                    for h in re.findall(r"^#+ (.+)$", text, re.M)}
        for path in self.docs():
            text = path.read_text(encoding="utf-8")
            for link in re.findall(r"\]\(([^)\s]+)\)", text):
                if link.startswith(("http://", "https://", "mailto:")):
                    continue
                target_rel, _, frag = link.partition("#")
                target = (path.parent / target_rel) if target_rel else path
                with self.subTest(fichero=path.relative_to(ROOT).as_posix(), enlace=link):
                    self.assertTrue(target.exists(), "enlace roto")
                    if frag and target.suffix == ".md":
                        self.assertIn(frag, anchors(target.read_text(encoding="utf-8")), "ancla inexistente")

    def test_bloques_mermaid_bien_formados(self):
        kinds = ("flowchart", "sequenceDiagram", "stateDiagram-v2", "graph")
        for path in self.docs():
            text = path.read_text(encoding="utf-8")
            for block in re.findall(r"```mermaid\n(.*?)```", text, re.S):
                with self.subTest(fichero=path.relative_to(ROOT).as_posix()):
                    self.assertTrue(block.strip().startswith(kinds), "tipo de diagrama desconocido")

    def test_sin_rutas_personales(self):
        me = Path(__file__).resolve()
        for path in tracked_files():
            if path.resolve() == me or path.suffix in (".gif", ".png", ".svg"):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            with self.subTest(fichero=path.relative_to(ROOT).as_posix()):
                self.assertIsNone(PERSONAL_PATH_RE.search(text), "ruta personal en un fichero versionado")


if __name__ == "__main__":
    unittest.main()
