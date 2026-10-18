---
paths:
  - "**/*.java"
  - "**/pom.xml"
  - "**/build.gradle"
---
<!-- Adaptado de ECC (rules/java), https://github.com/affaan-m/ECC — MIT License, Copyright (c) 2026 Affaan Mustafa. -->
# Java

Amplía las [reglas comunes](common.md).

## Estilo

- El formateador del proyecto (google-java-format o Checkstyle). Un tipo público por fichero.
- `record` para valores y DTO; campos `final` por defecto; copias defensivas en el API (`List.copyOf`).
- Clases selladas y `switch` con patrones para jerarquías cerradas, si la versión de Java lo permite.
- Inyección por constructor, nunca por campo.
- Streams cortos y sin efectos secundarios; si la cadena se complica, un bucle se lee mejor.

## Errores

- Excepciones de dominio que extienden `RuntimeException`, con contexto en el mensaje.
- `Optional<T>` como retorno de búsquedas; nunca como campo ni como parámetro, y nunca `get()` sin comprobar.
- Nada de `catch (Exception e)` salvo en el manejador de nivel superior.

## Tests

- JUnit 5 (`@Test`, `@ParameterizedTest`, `@Nested`), AssertJ para aserciones y Mockito para dependencias, si el proyecto los usa.
- Testcontainers cuando un test de integración necesita una base de datos real.
- Nombres `metodo_escenario_resultadoEsperado` o `@DisplayName` legible.

## Seguridad

- `PreparedStatement` o el API parametrizado del framework; nunca concatenar SQL.
- Contraseñas con bcrypt o Argon2; nunca MD5 ni SHA-1.
- Bean Validation (`@NotNull`, `@Size`) en los DTO de entrada, si el proyecto la usa.
- OWASP Dependency-Check o equivalente cuando cambien las dependencias.

## Comandos habituales

| Fase de `verify` | Comando típico |
|---|---|
| build | `./mvnw -q -DskipTests package` o `./gradlew assemble` |
| types | (lo cubre el compilador en build) |
| lint | `./mvnw -q checkstyle:check` o `./gradlew check -x test` |
| tests | `./mvnw -q test` o `./gradlew test` |
