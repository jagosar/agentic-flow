---
paths:
  - "**/*.swift"
  - "**/Package.swift"
---
<!-- Adaptado de ECC (rules/swift), https://github.com/affaan-m/ECC — MIT License, Copyright (c) 2026 Affaan Mustafa. -->
# Swift

Amplía las [reglas comunes](common.md).

## Estilo

- SwiftFormat y SwiftLint, o `swift-format`, según lo que use el proyecto.
- `let` por defecto; `struct` con semántica de valor salvo que haga falta identidad.
- Claridad en el punto de uso: los métodos se nombran por su papel, sin palabras de sobra.
- Enums con valores asociados para modelar estados distintos; protocolos para las dependencias.
- Concurrencia estructurada (`async let`, `TaskGroup`) mejor que `Task {}` sueltos; actores para el estado mutable compartido y tipos `Sendable` entre dominios de aislamiento.

## Errores

- `throws` con tipos de error propios (`enum` que conforma `Error`).
- Nada de `try!` ni de desempaquetado forzado (`!`) con datos externos: `guard let` o `if let`.

## Tests

- Swift Testing (`@Test`, `#expect`) o XCTest, el que use el proyecto.
- Tests parametrizados para tablas de casos; dependencias inyectadas por protocolo para aislarlos.

## Seguridad

- Secretos en el Llavero (Keychain), nunca en `UserDefaults` ni en el código.
- App Transport Security activado; solo HTTPS.
- Se valida todo lo que llega de fuera (deep links, portapapeles, API) antes de usarlo.

## Comandos habituales

| Fase de `verify` | Comando típico |
|---|---|
| build | `swift build` |
| types | (lo cubre el compilador en build) |
| lint | `swiftlint --strict` |
| tests | `swift test` |
