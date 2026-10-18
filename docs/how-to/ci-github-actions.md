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

permissions:
  contents: read

concurrency:
  group: agentic-qa-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  qa:
    # Solo ramas del propio repo (nunca forks) y nunca borradores; sin architecture.md no hay nada que validar.
    if: >-
      github.event.pull_request.head.repo.full_name == github.repository &&
      github.event.pull_request.draft == false &&
      hashFiles('architecture.md') != ''
    runs-on: ubuntu-latest
    timeout-minutes: 40
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0
        with:
          python-version: "3.12"
      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0
        with:
          node-version: "22"
      # Aquí, la instalación de las dependencias de tu proyecto (sección 3 de architecture.md).
      - name: Instalar Claude Code (versión exacta desde npm)
        run: npm install -g @anthropic-ai/claude-code@2.1.302
      - run: python3 .claude/bin/agentic.py validate
      # Determinista, sin secretos y sin coste: los tests de aceptación de la ola 0 deben pasar.
      - run: python3 .claude/bin/agentic.py acceptance --expect green
      - name: Agente QA
        env:
          CLAUDE_CODE_OAUTH_TOKEN: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
        run: python3 .claude/bin/agentic.py run-qa
      - name: Informe en el resumen del job
        if: always()
        run: |
          python3 -c "import json;print(json.load(open('.claude/state/runs/QA.json'))['result'])" >> "$GITHUB_STEP_SUMMARY" || true
      - uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        if: always()
        with:
          name: qa-report
          path: |
            qa/
            .claude/state/runs/
```

Qué hace cada parte que no es estándar:

- **Actions fijadas por SHA:** una etiqueta como `@v7` se puede mover y apuntar a otro código; un SHA, no. La versión va en el comentario. Para actualizarlas, resuelve el SHA de la nueva versión con `gh api repos/<owner>/<action>/git/ref/tags/<versión>`.
- **`permissions: contents: read` y `persist-credentials: false`:** el job no puede escribir en el repo, y el token de GitHub no queda guardado en el checkout, al alcance del código que se ejecute.
- **Solo ramas del propio repo:** el agente QA ejecuta los tests del PR con tu token de suscripción en el entorno. Un PR malicioso de un fork podría intentar leerlo. GitHub no pasa secretos a los forks, y esta condición lo deja explícito.
- **El token solo en el paso de QA:** `validate` y la aceptación ejecutan el código del PR sin ningún secreto en el entorno.
- **Claude Code en versión exacta:** instalado desde npm con la versión fijada, en lugar de `curl | bash` con la última. Actualiza la versión a propósito, no por sorpresa.
- **`concurrency`:** si haces push varias veces seguidas, solo corre la última ejecución, lo que ahorra límites de uso.
- **`timeout-minutes`:** es el freno del job. El flow tiene además su propio `timeout_s`.

## Resultado

- El job falla si la aceptación no pasa (sin coste: no lanza ningún agente), o si QA devuelve `FAIL` o `BLOCKER` o escribe fuera de `qa/`.
- El informe aparece en el resumen del job, y los tests de QA se pueden descargar como artifact.
- Los tests de QA no se commitean desde CI. Si quieres conservarlos, descarga el artifact y haz tú el commit.

## Alternativa oficial

La action [`anthropics/claude-code-action@v1`](https://github.com/anthropics/claude-code-action), con la entrada `claude_code_oauth_token`, sirve para responder a menciones `@claude` y para automatizaciones con `prompt`. Aquí se usa el script directamente, porque aplica los guardarraíles del flow, separa la aceptación (determinista) de QA (agente) y da el código de salida y el informe con el formato del flow. También puedes configurar la action y su secreto con `/install-github-app` desde Claude Code.

## Puntos a vigilar

No he ejecutado este workflow. Antes de fiarte de él:

1. Pruébalo en un PR de prueba.
2. Comprueba en el log que QA usa tu suscripción. No debe aparecer ningún aviso de API key.
3. Ajusta los disparadores si tienes muchos PR, por ejemplo para que solo corra con una etiqueta.

## Referencias

- [Claude Code GitHub Actions](https://code.claude.com/docs/en/github-actions)
- [Token de larga duración](https://code.claude.com/docs/en/authentication#generate-a-long-lived-token)
