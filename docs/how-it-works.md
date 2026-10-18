# Cómo funciona agentic-flow

Referencia técnica del flow: qué piezas hay, en qué orden actúan, quién puede escribir qué y dónde intervienes tú. Para usarlo en tu entorno, consulta los [how-to](how-to/README.md).

Contenido:

1. [Vista general](#1-vista-general)
2. [Secuencia de una ejecución](#2-secuencia-de-una-ejecución-modo-a)
3. [Ciclo de vida de un work package](#3-ciclo-de-vida-de-un-work-package)
4. [Guardarraíles: decisión del hook](#4-guardarraíles-decisión-del-hook)
5. [Matriz de permisos](#5-matriz-de-permisos)
6. [Modo A y modo B](#6-modo-a-y-modo-b)
7. [Ficheros y estado](#7-ficheros-y-estado)
8. [Glosario](#8-glosario)

## 1. Vista general

Tres fases y dos puertas humanas. Cada caja es un agente o un paso determinista del script `agentic.py`.

```mermaid
flowchart TD
    U(["Tú: petición"]) --> C

    subgraph A["Arquitectura (último Opus)"]
        C["Clasificar tipo y tamaño"] -->|trivial| X(["Fuera del flow: pídelo directamente"])
        C --> R["Investigar y reutilizar<br/>leer decisiones previas"]
        R --> I["Entrevista"]
        I --> D["architecture.md<br/>contratos + AC-NNN + manifiesto"]
        D --> V{"validate"}
        V -->|errores| D
        V -->|ok| PR["plan-reviewer<br/>contexto limpio"]
        PR -->|críticos| D
    end

    PR -->|listo| G1{{"Puerta 1: apruebas el diseño"}}
    G1 --> ARC[("docs/architecture")]

    subgraph B["Construcción (último Sonnet)"]
        AT["Ola 0: test-author<br/>escribe los tests de aceptación"] --> RED{"acceptance<br/>--expect red"}
        RED -->|ya pasan| STOP1(["Para: los tests no prueban nada"])
        RED -->|rojo| W1["Ola 1: implementers en paralelo"]
        W1 --> CW1{"check-wave"}
        CW1 --> W2["Ola N: implementers"]
        W2 --> CWN{"check-wave"}
    end

    G1 --> AT

    subgraph C2["Verificación (último Sonnet)"]
        VF["Fases: build · tipos · lint · tests"] --> GREEN{"acceptance<br/>--expect green"}
        GREEN --> RV["reviewer<br/>solo lectura"]
        RV --> QA["qa<br/>exploratorio"]
    end

    CWN --> VF
    GREEN -->|falla| FIX
    RV -->|crítico o alto| FIX
    QA -->|defecto de implementación| FIX["run-wave N WP --fix"]
    FIX -->|máx. 2 ciclos por WP| VF
    FIX -->|tope agotado| H(["Decides tú o /architect"])
    QA -->|defecto de diseño| H
    QA -->|PASS| G2{{"Puerta 2: apruebas el commit"}}
```

## 2. Secuencia de una ejecución (modo A)

El orquestador no bloquea la sesión. Lanza cada etapa en segundo plano y retoma cuando llega la notificación. Las flechas discontinuas son respuestas.

```mermaid
sequenceDiagram
    autonumber
    actor U as Tú
    participant AR as /architect (Opus)
    participant PR as plan-reviewer (Opus)
    participant O as /implement (Sonnet)
    participant S as agentic.py
    participant AT as test-author
    participant WP as implementers
    participant RV as reviewer
    participant QA as qa

    U->>AR: petición
    AR->>U: preguntas (por rondas)
    U-->>AR: respuestas
    AR->>S: validate
    AR->>PR: Revisa architecture.md
    PR-->>AR: LISTO o CORREGIR
    AR-->>U: resumen y petición de aprobación
    U->>AR: apruebo
    AR->>AR: archiva en docs/architecture/

    U->>O: /implement
    O->>S: run-acceptance (en segundo plano)
    S->>AT: claude -p --agent test-author
    AT-->>S: STATUS: DONE
    O->>S: acceptance --expect red
    S-->>O: ROJO
    loop por cada ola
        O->>S: run-wave N (en segundo plano)
        par un proceso por WP
            S->>WP: claude -p --agent implementer
        end
        WP-->>S: STATUS: DONE | BLOCKER
        S->>S: check-wave N y ledger
        S-->>O: RESULTADO: OK | REVISAR
    end
    O->>S: acceptance --expect green
    O->>S: run-review
    S->>RV: claude -p --agent reviewer
    RV-->>S: STATUS: PASS | FAIL
    O->>S: run-qa
    S->>QA: claude -p --agent qa
    QA-->>S: STATUS: PASS | FAIL
    O-->>U: informe y commits propuestos
    U->>O: apruebo el commit
```

## 3. Ciclo de vida de un work package

Estados tal como aparecen en el ledger (`agentic.py status`).

```mermaid
stateDiagram-v2
    [*] --> pendiente: aprobado en architecture.md
    pendiente --> running: run-wave N o claim (modo B)
    running --> done: STATUS DONE y check-wave OK
    running --> blocker: STATUS BLOCKER
    running --> error: escritura ajena, fallo del proceso
    running --> timeout: supera timeout_s
    running --> stopped: agentic.py stop
    done --> running: fix, ciclo 1 o 2
    done --> escalado: fix con el tope agotado
    blocker --> [*]: lo resuelves tú o /architect
    escalado --> [*]: lo resuelves tú o /architect
    done --> [*]: aceptación en verde y revisión y QA sin defectos suyos
```

## 4. Guardarraíles: decisión del hook

El hook `PreToolUse` (`agentic.py hook`) se ejecuta antes de cada Write, Edit, MultiEdit, NotebookEdit y Bash. **Falla cerrado**: dentro de un agente del flow, cualquier error bloquea.

```mermaid
flowchart TD
    E["Herramienta a punto de ejecutarse"] --> NV{"Bash con --no-verify,<br/>commit -n o core.hooksPath?"}
    NV -->|sí| BLK[["Bloquear · exit 2"]]
    NV -->|no| ID{"¿Quién es?"}
    ID -->|sesión principal| OK[["Permitir"]]
    ID -->|"AGENTIC_WP (modo A) o claim (modo B)"| T{"Tipo de herramienta"}
    T -->|Bash| GB{"git que escribe, instalar<br/>dependencias o claude -p?"}
    GB -->|sí| BLK
    GB -->|no| OK
    T -->|escritura| OWN{"¿El fichero es de su zona<br/>según el manifiesto?"}
    OWN -->|no| BLK
    OWN -->|sí| SEC{"¿Contiene un secreto?"}
    SEC -->|sí| BLK
    SEC -->|no| CFG{"¿Modifica config de calidad<br/>existente sin config_edit?"}
    CFG -->|sí| BLK
    CFG -->|no| SKIP{"¿Añade skip, xfail u only<br/>a un fichero de test?"}
    SKIP -->|sí| BLK
    SKIP -->|no| OK
```

Además, al cerrar cada etapa, `check-wave` compara todos los ficheros antes y después. Cualquier cambio fuera de la zona de esa etapa la deja en `REVISAR`, incluidos los que se hicieran por Bash esquivando el hook.

## 5. Matriz de permisos

| Agente | Modelo | Escribe en | Ejecuta | No puede |
|---|---|---|---|---|
| Arquitecto (`/architect`) | último Opus | `architecture.md`, `docs/architecture/` | `agentic.py validate` | código, tests |
| plan-reviewer | último Opus | nada | nada | escribir |
| Orquestador (`/implement`) | último Sonnet | nada (solo el ledger, vía script) | `agentic.py`, comandos de la sección 3 | código, tests, commit sin tu aprobación |
| test-author (`AT`) | último Sonnet | `acceptance.files` (por defecto `acceptance/`) | `allow_bash` + comando de aceptación | código de producción |
| implementer (`WP-NN`) | último Sonnet | los `files` de su WP | `allow_bash` + comando de aceptación | ficheros ajenos, `acceptance/`, git, dependencias |
| reviewer (`REVIEW`) | último Sonnet | nada | `git diff/status/log` + `allow_bash` | escribir |
| qa (`QA`) | último Sonnet | `qa.files` (por defecto `qa/`) | `allow_bash` | código de producción |

Para todos los agentes del flow: nada de secretos, de `--no-verify`, de relajar configuración existente ni de desactivar tests. Nadie puede poseer `architecture.md`, `.claude/` ni `docs/architecture/`.

## 6. Modo A y modo B

```mermaid
flowchart LR
    O["/implement"] --> Q{"¿claude CLI<br/>en el PATH?"}
    Q -->|sí| A["Modo A"]
    Q -->|no| B["Modo B"]
    A --> A1["agentic.py run-wave N<br/>un proceso claude -p por WP<br/>identidad: AGENTIC_WP<br/>stop mata el grupo de procesos"]
    B --> B1["herramienta Agent<br/>un subagente por WP, en segundo plano<br/>identidad: claim + agent_id<br/>stop marca y TaskStop"]
    A1 --> L[("ledger.md")]
    B1 --> L
```

| | Modo A | Modo B |
|---|---|---|
| Dónde | Terminal, Desktop, IDE con el CLI instalado | Nube, o sin el CLI |
| Paralelismo | Garantizado (procesos) | Depende de que el orquestador agrupe las llamadas |
| Identidad para el hook | Variable `AGENTIC_WP` | `claim` registrado por `agent_id` |
| Coste de contexto | Bajo: el orquestador solo lee resúmenes | Mayor: los informes pasan por su contexto |
| Estado probado | Pasada completa v1 y v2 con agentes reales | Pasada completa v1; v2 solo con tests |

### Experimental: workflow nativo

`.claude/workflows/agentic-wave.js` ejecuta una ola como [workflow dinámico](https://code.claude.com/docs/en/workflows) de Claude Code. Funciona así:
- **Paralelismo:** el script lanza los implementers con `parallel()`.
- **Informes:** valida cada informe contra un JSON Schema.
- **Pasos deterministas:** los delega en el agente `gatekeeper` (`open-wave` y `close-wave`), porque un workflow no tiene acceso a la shell.

Ya está probado con agentes reales: dos olas con paralelismo efectivo, hook activo dentro del workflow (bloqueo de una escritura ajena) y ledger cerrado al terminar. Todavía no está conectado a `/implement`.

En Pro hay que activar **Dynamic workflows** en `/config`, o poner `"enableWorkflows": true` en la configuración.

## 7. Ficheros y estado

```
.claude/
├── commands/
│   ├── architect.md        /architect   (último Opus)
│   └── implement.md        /implement   (último Sonnet)
├── agents/
│   ├── plan-reviewer.md    último Opus, solo lectura
│   ├── test-author.md      ola 0
│   ├── implementer.md      un WP
│   ├── reviewer.md         solo lectura
│   └── qa.md               exploratorio
├── bin/
│   ├── agentic.py          validate · run-* · acceptance · check-wave · status · stop · hook
│   └── test_agentic.py     tests del propio flow
├── settings.json           hook PreToolUse + permisos
├── agentic.json            timeout_s · auth · max_fix_cycles
└── state/                  (ignorado por git)
    ├── ledger.md           estado legible
    ├── runs/<ID>.json      informe de cada agente
    └── snapshot-*.json     huellas para check-wave
architecture.md             el contrato vigente
docs/architecture/          diseños aprobados + índice de decisiones
acceptance/  qa/            tests de aceptación y de QA
```

## 8. Glosario

- **WP (work package):** unidad de trabajo con ficheros propios, asignada a un implementer.
- **Ola:** grupo de WP que corren en paralelo. Una ola solo depende de olas anteriores.
- **AC-NNN:** criterio de aceptación observable, con su "no debe" y su verificación automática.
- **Ola 0:** el test-author convierte los AC en tests antes de que exista el código.
- **Manifiesto:** bloque `json wp-manifest` de `architecture.md` del que leen todos los guardarraíles.
- **Ledger:** `.claude/state/ledger.md`, el estado de agentes y etapas. Lo escribe el script, no el modelo.
- **check-wave:** comparación de huellas antes y después de una etapa para detectar escrituras fuera de zona.
- **Puertas humanas:** aprobar el diseño y aprobar el commit. Nada pasa de una fase a otra sin ti.
