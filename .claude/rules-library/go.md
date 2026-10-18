---
paths:
  - "**/*.go"
  - "**/go.mod"
  - "**/go.sum"
---
<!-- Adaptado de ECC (rules/golang), https://github.com/affaan-m/ECC — MIT License, Copyright (c) 2026 Affaan Mustafa. -->
# Go

Amplía las [reglas comunes](common.md).

## Estilo

- `gofmt` y `goimports`, sin discusión.
- Acepta interfaces y devuelve structs. Interfaces pequeñas (de 1 a 3 métodos), definidas donde se consumen.
- Inyección de dependencias por constructor (`NewServicio(repo Repo)`); opciones funcionales cuando hay muchos parámetros opcionales.
- `context.Context` como primer parámetro de toda función que haga E/S o pueda tardar.
- Nombres cortos en ámbitos cortos; exportado solo lo que forma parte del contrato.

## Errores

- Siempre se comprueba el error. Se envuelve con contexto: `fmt.Errorf("guardar enlace %s: %w", id, err)`.
- Errores centinela (`var ErrNotFound = errors.New(...)`) o tipos de error, comparados con `errors.Is` y `errors.As`.
- `panic` solo para estados imposibles, nunca para errores esperables.

## Tests

- Tests de tabla con `t.Run` por caso. `t.Helper()` en las funciones auxiliares y `t.TempDir()` para ficheros.
- `go test -race` en la suite: las condiciones de carrera son defectos.
- Dobles de prueba escritos a mano contra la interfaz pequeña, mejor que librerías de mocks.

## Seguridad

- Secretos con `os.Getenv`, comprobados al arrancar.
- `database/sql` con parámetros (`?`, `$1`); nunca `fmt.Sprintf` para construir SQL.
- Timeouts en todo cliente y servidor HTTP: los valores por defecto no tienen límite.
- `gosec ./...` y `govulncheck ./...` si el proyecto los usa.

## Comandos habituales

| Fase de `verify` | Comando típico |
|---|---|
| build | `go build ./...` |
| types | `go vet ./...` |
| lint | `golangci-lint run` |
| tests | `go test -race ./...` |
