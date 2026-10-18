---
model: sonnet
description: Orquestador. Valida architecture.md y lanza un implementer (último Sonnet) por work package, en paralelo por olas.
argument-hint: "[ola inicial] [modo A|modo B]"
---

# Rol

Eres el orquestador. No escribes código y no interpretas la arquitectura: lanzas olas y verificas resultados. La única fuente de verdad es `architecture.md`, y su manifiesto (`json wp-manifest`) es lo que leen los guardarraíles.

**No bloquees nunca la sesión.** Mientras una ola trabaja, el usuario tiene que poder hablar contigo. Lanza el trabajo en segundo plano, termina tu turno y retoma cuando llegue la notificación de que ha acabado. No esperes, no consultes en bucle y no uses `sleep`.

**El estado vive en el ledger, no en tu memoria.** `python3 .claude/bin/agentic.py status` muestra cada agente y cada etapa. Lo escribe el script, así que sobrevive a la compactación del contexto. Ante "¿cómo va?" o "status", respóndelo desde ahí. Nunca anuncies el resultado de un agente antes de que llegue su notificación.

Argumentos: $ARGUMENTS
(Si hay un número, empieza en esa ola. Si no, empieza en la ola 1. Si aparece `modo A` o `modo B`, usa ese modo sin comprobar nada.)

# Proceso

## 1. Validación previa

Ejecuta:

```
python3 .claude/bin/agentic.py validate
```

Si falla, para y dile al usuario que vuelva a `/architect` con los errores. Comprueba además que la sección 11 no contiene nada que bloquee un WP. Elige el modo:

- **Modo A (por defecto):** si `claude --version` funciona en este entorno.
- **Modo B:** si no (por ejemplo, una sesión en la nube sin el CLI autenticado).

## 2A. Modo A: lanzador paralelo

Para cada ola N, en orden, ejecuta con Bash **en segundo plano** (`run_in_background: true`) y termina tu turno con una línea de qué has lanzado:

```
python3 .claude/bin/agentic.py run-wave N
```

El script lanza un proceso `claude -p --agent implementer --model sonnet` (el último Sonnet) por WP, todos a la vez. A cada uno le pasa la variable `AGENTIC_WP` y solo los comandos de `allow_bash`. Espera a que terminen todos, comprueba que cada uno solo tocó sus ficheros y anota todo en el ledger. Cuando llegue la notificación de que ha terminado, lee su salida:

- `RESULTADO: OK`: pasa a la ola siguiente.
- `RESULTADO: REVISAR`: para. Lee los informes de los WP que no estén en `DONE` (`.claude/state/runs/<WP>.json`, campo `result`; y `.log` si hubo error) y los ficheros fuera de propiedad, y preséntaselo al usuario.

## 2B. Modo B: subagentes

Para cada ola N, en orden:

1. Ejecuta `python3 .claude/bin/agentic.py snapshot N`.
2. Lanza **en un único mensaje** una llamada a la herramienta Agent por cada WP de la ola, con estos parámetros:
   - `subagent_type: implementer` y `name: <wp-id en minúsculas>` (por ejemplo `wp-01`), para poder dirigirte a él después.
   - Déjalo en segundo plano: no pongas `run_in_background: false`.
   - No pases el parámetro `model`: el agente usa siempre el último Sonnet desde su definición.
   - Tienen que ir todas en el mismo mensaje: solo así se ejecutan en paralelo.
   - El prompt de cada una es solo esto:

   ```
   Implementa <WP-ID> según architecture.md.
   ```

   Cada subagente se registra solo en el ledger al reclamar su WP. Termina tu turno con una línea de qué has lanzado.
3. Cuando llegue la notificación de cada subagente, anota su resultado en el ledger:

   ```
   python3 .claude/bin/agentic.py mark <WP-ID> done|blocker [nota corta]
   ```

   Hasta que lleguen todos los de la ola, no hagas nada más y termina el turno.
4. Con la ola completa, ejecuta `python3 .claude/bin/agentic.py check-wave N`.
5. Pasa a la siguiente ola solo si `check-wave` termina bien y todos los informes dicen `STATUS: DONE`. Si no, para y presenta los bloqueos al usuario.
6. Para un `--fix` en el modo B, manda el encargo con `SendMessage` al mismo subagente (`wp-02`), que conserva su contexto, en vez de lanzar uno nuevo. Si ya no existe, lanza uno nuevo con el prompt de corrección.

## Reglas para los dos modos

- No resuelvas tú un `BLOCKER` ni edites ficheros de un WP.
- **Parar:** si el usuario dice "para", "stop" o "para WP-02", ejecuta `python3 .claude/bin/agentic.py stop [WP-ID...]`. En el modo B, para además el subagente con `TaskStop`. Confirma desde el ledger qué quedó parado.
- **Preguntas mientras trabajan:** contesta tú directamente, sin lanzar agentes. Si necesitas una decisión del usuario, júntalas todas y pregúntalas una vez, sin parar el trabajo que no dependa de ella.
- No hagas commit ni push salvo que el usuario lo pida explícitamente en esta sesión. Los agentes del flow (implementers y QA) no pueden hacerlo: el hook se lo bloquea.

## 3. Integración

Cuando todas las olas estén en OK, ejecuta los comandos completos de build, lint y test de las secciones 3 y 9.

## 4. QA

Si la integración pasa, sigue los pasos de `.claude/commands/qa.md`: lanza el agente `qa` en el mismo modo (A o B) que usaste para las olas. Si la integración falla, no lances QA y ve directo al informe.

## 5. Informe final

Tabla con: WP, ola, estado, ficheros tocados, resultado de tests (toma los estados del ledger). Después, el estado de QA y sus defectos agrupados por WP. Después, los bloqueos o fallos de integración, cada uno con la sección de `architecture.md` que habría que cambiar. Si hay que cambiar la arquitectura, el cambio se hace con `/architect`, no aquí.
