---
paths:
  - "**/*.rb"
  - "**/Gemfile"
  - "**/*.rake"
---
<!-- Adaptado de ECC (rules/ruby), https://github.com/affaan-m/ECC — MIT License, Copyright (c) 2026 Affaan Mustafa. -->
# Ruby

Amplía las [reglas comunes](common.md).

## Estilo

- La configuración de RuboCop del repo; sin desactivar reglas en línea salvo excepción justificada.
- `# frozen_string_literal: true` si el proyecto sigue esa convención.
- Ruby claro antes que metaprogramación ingeniosa; los DSL, aislados y probados.
- En Rails: primero las convenciones del framework. Los controladores, solo de transporte (autenticación, parámetros, respuesta). Los objetos de servicio o de consulta, cuando la complejidad lo pide, no por defecto.
- `bin/rails` y los binstubs del repo, no comandos instalados de forma global.

## Errores

- `rescue` de excepciones concretas; nada de `rescue StandardError` que no relance o conserve el contexto.
- Sin `puts`, `pp` ni `debugger` en el código que se entrega.

## Tests

- El framework que ya use el proyecto (Minitest o RSpec), sin mezclarlos en la misma área.
- Lógica de dominio en tests de modelo o de servicio; contratos HTTP en tests de request. Los tests de sistema, solo para los flujos críticos.
- Fixtures o `factory_bot`, según lo que ya use el repo.

## Seguridad

- Strong parameters antes de cualquier asignación masiva. La protección CSRF, activada.
- Consultas de Active Record o SQL parametrizado; nunca interpolar parámetros en SQL.
- `html_safe` y `raw` se tratan como código sensible.
- `bundle audit` o `bundler-audit` cuando cambie el `Gemfile.lock`.

## Comandos habituales

| Fase de `verify` | Comando típico |
|---|---|
| build | `bundle exec rails zeitwerk:check` (Rails) |
| types | (no aplica, o `bundle exec srb tc` con Sorbet) |
| lint | `bundle exec rubocop` |
| tests | `bin/rails test` o `bundle exec rspec` |
