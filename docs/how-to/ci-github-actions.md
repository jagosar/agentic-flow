# How-to: QA automático en GitHub Actions

Por qué lo recomiendo: el arquitecto necesita conversar contigo, pero QA no. Ejecutar el agente QA en cada pull request te da una segunda revisión contra `architecture.md` sin tener que lanzarla a mano.

## Requisitos

- Una API key de Anthropic guardada como secreto del repo: `Settings → Secrets and variables → Actions → New repository secret`, con el nombre `ANTHROPIC_API_KEY`. Créala tú en la consola de Anthropic y no la pegues en ningún chat.
- `architecture.md` con su manifiesto en la rama del PR.

## Workflow

Crea `.github/workflows/agentic-qa.yml`:

```yaml
name: agentic-qa
on:
  pull_request:
    paths-ignore: ["docs/**"]

jobs:
  qa:
    if: hashFiles('architecture.md') != ''
    runs-on: ubuntu-latest
    timeout-minutes: 30
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      # Aquí, los pasos para instalar las dependencias de tu proyecto (sección 3 de architecture.md).
      - run: npm install -g @anthropic-ai/claude-code
      - run: python3 .claude/bin/agentic.py validate
      - name: Agente QA
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python3 .claude/bin/agentic.py run-qa
      - name: Informe
        if: always()
        run: |
          python3 -c "import json;print(json.load(open('.claude/state/runs/QA.json'))['result'])" >> "$GITHUB_STEP_SUMMARY" || true
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: qa-report
          path: |
            qa/
            .claude/state/runs/
```

## Resultado

- El job falla si QA devuelve `FAIL`, `BLOCKER` o si escribe fuera de `qa/`.
- El informe aparece en el resumen del job, y los tests de QA se pueden descargar como artifact.
- Los tests que escribe QA no se commitean desde CI. Si quieres conservarlos, descarga el artifact y commitéalos tú.

## Sin probar

No he ejecutado este workflow. Los puntos a vigilar:

- Que el CLI use `ANTHROPIC_API_KEY` sin login interactivo en modo `-p`. Es lo habitual, pero no lo he comprobado aquí.
- Los costes: cada ejecución de QA con Opus cuesta dinero. En la prueba local, la QA de un proyecto mínimo con Sonnet costó unos 0,15 $. Uno real costará más.
- Existe también la action oficial `anthropics/claude-code-action`, pensada para responder a menciones en PRs. Para este caso, el script es más directo porque ya aplica los guardarraíles.
