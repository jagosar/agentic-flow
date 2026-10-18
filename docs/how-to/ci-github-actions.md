# How-to: QA automático en GitHub Actions

**Objetivo:** que el agente QA valide cada pull request contra `architecture.md`, sin lanzarlo a mano.
**Estado:** sin probar. El workflow sigue la documentación oficial de autenticación y de GitHub Actions.

**Por qué QA y no el resto:** el arquitecto necesita conversar contigo y los implementadores trabajan mejor con tu supervisión. QA, en cambio, puede correr solo: lee el diseño, prueba y emite un veredicto.

## Requisitos

- Un plan Pro, Max, Team o Enterprise.
- Un **token de tu suscripción** guardado como secreto del repo:
  1. Genera el token en tu máquina con el comando de abajo. Abre el navegador e imprime un token válido durante un año. No lo guarda en ningún sitio.

     ```bash
     claude setup-token
     ```

  2. En GitHub, ve a `Settings → Secrets and variables → Actions → New repository secret`, ponle de nombre `CLAUDE_CODE_OAUTH_TOKEN` y pega el token. No lo pegues en ningún chat ni lo subas al repo.
- `architecture.md`, con su manifiesto, en la rama del PR.

El token está ligado a **tu** suscripción: cada ejecución cuenta contra tus límites de uso. Para un equipo, la documentación oficial recomienda una API key de Console en un secreto `ANTHROPIC_API_KEY`. En ese caso, pon `"auth": "inherit"` en `.claude/agentic.json`.

## Workflow

Crea `.github/workflows/agentic-qa.yml`:

```yaml
name: agentic-qa
on:
  pull_request:
    types: [opened, synchronize, reopened, ready_for_review]
    paths-ignore: ["docs/**"]

concurrency:
  group: agentic-qa-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  qa:
    if: github.event.pull_request.draft == false && hashFiles('architecture.md') != ''
    runs-on: ubuntu-latest
    timeout-minutes: 40
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      # Aquí, la instalación de las dependencias de tu proyecto (sección 3 de architecture.md).
      - name: Instalar Claude Code
        run: |
          curl -fsSL https://claude.ai/install.sh | bash
          echo "$HOME/.local/bin" >> "$GITHUB_PATH"
      - run: python3 .claude/bin/agentic.py validate
      - name: Agente QA
        env:
          CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
        run: python3 .claude/bin/agentic.py run-qa
      - name: Informe en el resumen del job
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

Qué hace cada parte que no es estándar:

- **`concurrency`:** si haces push varias veces seguidas, solo corre la última ejecución, lo que ahorra límites de uso.
- **`if`:** no corre en borradores ni en ramas sin arquitectura.
- **`timeout-minutes`:** es el freno del job. El flow tiene además su propio `timeout_s`.
- **`CLAUDE_CODE_OAUTH_TOKEN`:** autentica con tu suscripción. El lanzador lo deja pasar a QA, porque solo quita `ANTHROPIC_API_KEY` y `ANTHROPIC_AUTH_TOKEN`.

## Resultado

- El job falla si QA devuelve `FAIL` o `BLOCKER`, o si escribe fuera de `qa/`.
- El informe aparece en el resumen del job, y los tests de QA se pueden descargar como artifact.
- Los tests de QA no se commitean desde CI. Si quieres conservarlos, descarga el artifact y haz tú el commit.

## Alternativa oficial

La action [`anthropics/claude-code-action@v1`](https://github.com/anthropics/claude-code-action), con la entrada `claude_code_oauth_token`, sirve para responder a menciones `@claude` y para automatizaciones con `prompt`. Ejecutarla con `prompt: "/qa"` debería funcionar, pero aquí se usa el script directamente porque da el código de salida y el informe con el formato del flow. También puedes configurar la action y su secreto con `/install-github-app` desde Claude Code.

## Puntos a vigilar

No he ejecutado este workflow. Antes de fiarte de él:

1. Pruébalo en un PR de prueba.
2. Comprueba en el log que QA usa tu suscripción. No debe aparecer ningún aviso de API key.
3. Ajusta los disparadores si tienes muchos PR, por ejemplo para que solo corra con una etiqueta.

## Referencias

- [Claude Code GitHub Actions](https://code.claude.com/docs/en/github-actions)
- [Token de larga duración](https://code.claude.com/docs/en/authentication#generate-a-long-lived-token)
