---
paths:
  - "**/*.kt"
  - "**/*.kts"
---
<!-- Adaptado de ECC (rules/kotlin), https://github.com/affaan-m/ECC — MIT License, Copyright (c) 2026 Affaan Mustafa. -->
# Kotlin

Amplía las [reglas comunes](common.md).

## Estilo

- Estilo oficial de Kotlin, con ktlint o Detekt si el proyecto los usa.
- `val` por defecto; `data class` para valores y `copy()` para cambiar el estado.
- Colecciones inmutables (`List`, `Map`) en el API público.
- `sealed` para estados y resultados cerrados, con `when` exhaustivo.
- Funciones de extensión en un fichero con el nombre del tipo receptor y nunca sobre `Any`. Como mucho dos niveles de funciones de ámbito (`let`, `apply`…) anidadas.

## Errores

- Nunca `!!`: `?.`, `?:`, `requireNotNull()` o `checkNotNull()`.
- `Result<T>` o un tipo sellado propio para errores esperables. Las excepciones no se usan para el control de flujo.
- En corrutinas, `CancellationException` siempre se relanza.

## Tests

- `kotlin.test` o JUnit 5; `kotlinx-coroutines-test` (`runTest`) para corrutinas y Turbine para `Flow`, si están en el proyecto.
- Fakes escritos a mano mejor que mocks cuando la interfaz es pequeña.

## Seguridad

- Secretos fuera del código: `local.properties` ignorado por git en local y variables de CI para la release.
- Consultas parametrizadas en Room, SQLDelight o JDBC.
- Timeouts explícitos en todos los clientes HTTP; solo HTTPS.

## Comandos habituales

| Fase de `verify` | Comando típico |
|---|---|
| build | `./gradlew assemble` |
| types | (lo cubre el compilador en build) |
| lint | `./gradlew ktlintCheck` o `./gradlew detekt` |
| tests | `./gradlew test` |
