# agentic-flow

Flow agéntico para Claude Code: un arquitecto (Opus 5.5) define `architecture.md` y varios implementadores (Sonnet 5.5) desarrollan en paralelo usando solo ese documento.

```
.claude/commands/architect.md    → /architect  (Opus 5.5)
.claude/commands/implement.md    → /implement  (orquestador)
.claude/agents/implementer.md    → subagente   (Sonnet 5.5, uno por WP)
```

## Uso

1. `/architect <qué quieres desarrollar o mejorar>`: entrevista por rondas y escribe `architecture.md`.
2. Revisa y aprueba `architecture.md`.
3. `/implement`: lanza un `implementer` por work package, por olas, en paralelo.

## En otros proyectos

- Proyecto nuevo: "Use this template" en GitHub.
- Proyecto existente: copia la carpeta `.claude/` y haz commit en la rama que vayas a usar (las sesiones de iOS solo ven lo commiteado).
