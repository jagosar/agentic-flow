---
description: Lanza el agente QA (Opus 5.5) sobre el sistema integrado. Decide qué tests hacen falta, los ejecuta y reporta defectos por WP.
---

# Rol

Eres el orquestador de QA. No escribes tests ni corriges código: lanzas al agente `qa` y presentas su informe.

# Proceso

1. Ejecuta `python3 .claude/bin/agentic.py validate`. Si falla, para.
2. Elige el modo, igual que en `/implement`:
   - **Modo A**, si `claude --version` funciona: ejecuta con Bash en segundo plano (`run_in_background: true`) `python3 .claude/bin/agentic.py run-qa`. Cuando termine, lee `.claude/state/runs/QA.json` (campo `result`).
   - **Modo B**, si no: ejecuta `python3 .claude/bin/agentic.py snapshot qa`, lanza un subagente con la herramienta Agent (`subagent_type: qa`, prompt: `Ejecuta la validación QA del sistema según architecture.md.`) y, cuando acabe, ejecuta `python3 .claude/bin/agentic.py check-wave qa`.
3. Presenta al usuario:
   - El estado **tal como lo devolvió QA** (`PASS`, `FAIL` o `BLOCKER`) y si QA tocó solo su zona. No lo cambies: `PASS` significa "sin defectos críticos ni altos" y puede venir con tests en rojo de defectos medios o bajos. Si es así, dilo ("PASS con 2 defectos bajos y 3 tests en rojo").
   - Los defectos agrupados por WP responsable, de mayor a menor severidad.
   - Por cada defecto, el siguiente paso: un defecto de implementación se arregla volviendo a lanzar ese WP; uno de diseño se arregla con `/architect`.
4. No arregles nada tú. No hagas commit salvo que el usuario lo pida.
