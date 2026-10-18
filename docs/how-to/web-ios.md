# How-to: Claude Code en web e iOS

Antes, lee los requisitos de [README.md](README.md).

Las sesiones de web (claude.ai/code) y de la app de iOS corren en la nube, sobre un clon de tu repo de GitHub. No usan tu máquina.

## 1. Preparar

1. Conecta GitHub a tu cuenta de Claude y dale acceso al repo.
2. Asegúrate de que `.claude/` está commiteado **y pusheado** en la rama con la que vas a trabajar. La nube solo ve lo que está en GitHub.

## 2. Usarlo

1. Abre claude.ai/code o la app de Claude en iOS → Code → nueva sesión → elige el repo y la rama.
2. Escribe lo mismo que en el resto de entornos:

```
/architect <tu petición>
```

```
/implement
```

3. Al acabar, la sesión puede subir los cambios a una rama y abrir un pull request desde la propia interfaz.

## Qué cambia respecto a tu máquina

- **Modo de ejecución:** si el entorno en la nube no tiene un `claude` CLI con sesión iniciada, `/implement` usa el **modo B** (subagentes dentro de la sesión). Los guardarraíles se aplican igual, a través del hook y de `claim`. El paralelismo depende de que el orquestador agrupe las llamadas a Agent.
- **`python3` y `git`:** se dan por hechos en el entorno en la nube. Si faltan, `validate` falla al principio y lo verás enseguida.
- **Push:** las reglas `deny` de `.claude/settings.json` bloquean `git push` a los agentes. Usa el botón de la interfaz para crear la rama o el PR. Si tu entorno en la nube solo puede entregar resultados con push, quita esa regla en tu copia.

## Uso recomendado desde el móvil

La entrevista del arquitecto es un buen trabajo para el móvil: son preguntas cortas con opciones. Puedes hacer `/architect` desde el iPhone y lanzar `/implement` después en Desktop, donde el modo A garantiza el paralelismo.

Alternativa: empieza la sesión en Desktop y sigue desde el móvil con **Remote Control**. Así la ejecución se queda en tu máquina, en modo A.

## Sin probar

No he probado este flow en sesiones de web ni de iOS. Tampoco he comprobado qué versión de Claude Code ni qué herramientas trae el entorno en la nube.
