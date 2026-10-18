---
paths:
  - "**/*.rs"
  - "**/Cargo.toml"
---
<!-- Adaptado de ECC (rules/rust), https://github.com/affaan-m/ECC — MIT License, Copyright (c) 2026 Affaan Mustafa. -->
# Rust

Amplía las [reglas comunes](common.md).

## Estilo

- `cargo fmt` y `cargo clippy -- -D warnings`.
- `let` por defecto; `let mut` solo cuando hace falta mutar.
- Presta (`&T`, `&str`, `&[T]`) por defecto; toma la propiedad solo para guardar o consumir. Nada de `clone()` para callar al borrow checker sin entender por qué.
- Privado por defecto; `pub(crate)` para compartir dentro del crate y `pub` solo para el API público.
- Newtypes y enums para que el sistema de tipos impida estados inválidos ("parse, don't validate").

## Errores

- `Result<T, E>` y `?`. Nunca `unwrap()` ni `expect()` en código de producción, salvo en estados de verdad imposibles, con el motivo en el mensaje.
- Librerías: errores tipados con `thiserror`. Aplicaciones: `anyhow` con `.context(...)`.

## Tests

- Módulo `#[cfg(test)] mod tests` para unitarios y `tests/` para integración.
- `#[tokio::test]` para async, si el proyecto usa tokio; `rstest` y `proptest` si ya están en las dependencias.
- Nombres que describen el comportamiento: `rechaza_pedido_sin_stock`.

## Seguridad

- Cada bloque `unsafe` lleva un comentario `// SAFETY:` con la invariante que lo hace correcto. Sin `unsafe` por comodidad.
- Consultas con parámetros enlazados (sqlx, diesel); nunca `format!` para SQL.
- `cargo audit` cuando cambie `Cargo.lock`.

## Comandos habituales

| Fase de `verify` | Comando típico |
|---|---|
| build | `cargo build --locked` |
| types | `cargo check --all-targets` |
| lint | `cargo clippy --all-targets -- -D warnings` |
| tests | `cargo test` |
