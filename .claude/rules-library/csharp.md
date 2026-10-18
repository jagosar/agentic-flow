---
paths:
  - "**/*.cs"
  - "**/*.csproj"
---
<!-- Adaptado de ECC (rules/csharp), https://github.com/affaan-m/ECC — MIT License, Copyright (c) 2026 Affaan Mustafa. -->
# C#

Amplía las [reglas comunes](common.md).

## Estilo

- Convenciones actuales de .NET, con los tipos de referencia anulables activados (`<Nullable>enable</Nullable>`).
- `record` para valores; `class` para entidades con identidad; `interface` en las fronteras entre servicios.
- Setters `init` y colecciones inmutables para el estado compartido. Sin `dynamic`.
- Modificadores de acceso explícitos; un tipo principal por fichero.

## Errores

- `async`/`await` de punta a punta; nunca `.Result` ni `.Wait()`. `CancellationToken` en todo API asíncrono público.
- Excepciones concretas, con log estructurado en el punto donde se gestionan.

## Tests

- xUnit, con NSubstitute o Moq para dependencias, si el proyecto los usa.
- `WebApplicationFactory<T>` para probar un API por HTTP, sin saltarse el middleware.
- La estructura de `tests/` refleja la de `src/`.

## Seguridad

- Secretos en variables de entorno o user-secrets en local, nunca en `appsettings.*.json`.
- Consultas parametrizadas con EF Core, Dapper o ADO.NET.
- Autenticación con los manejadores del framework, sin parsear tokens a mano. No se registran tokens ni contraseñas.

## Comandos habituales

| Fase de `verify` | Comando típico |
|---|---|
| build | `dotnet build --nologo` |
| types | (lo cubre el compilador en build) |
| lint | `dotnet format --verify-no-changes` |
| tests | `dotnet test --nologo` |
