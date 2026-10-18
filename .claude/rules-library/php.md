---
paths:
  - "**/*.php"
  - "**/composer.json"
---
<!-- Adaptado de ECC (rules/php), https://github.com/affaan-m/ECC — MIT License, Copyright (c) 2026 Affaan Mustafa. -->
# PHP

Amplía las [reglas comunes](common.md).

## Estilo

- PSR-12, con PHP-CS-Fixer o Laravel Pint.
- `declare(strict_types=1);`, tipos escalares, tipos de retorno y propiedades tipadas en todo el código nuevo.
- DTO y objetos de valor con propiedades `readonly` para los datos que cruzan una frontera; los arrays, solo para mapas simples.
- Controladores finos y servicios explícitos, con las dependencias por constructor.
- `use` para cada clase referenciada.

## Errores

- Excepciones para los estados excepcionales; nunca `false` o `null` como canal oculto de error en código nuevo.
- La entrada se convierte en un DTO validado antes de llegar al dominio.

## Tests

- PHPUnit o Pest, el que use el proyecto.
- Tests unitarios rápidos, separados de los de integración con el framework o la base de datos.
- Factories o builders para preparar datos, no arrays enormes escritos a mano.

## Seguridad

- Sentencias preparadas (PDO, Doctrine, query builder de Eloquent) para toda consulta dinámica.
- `password_hash()` y `password_verify()`; se regenera la sesión al autenticar.
- Escapado por defecto en las plantillas. CSRF en toda petición que cambie el estado.
- `composer audit` cuando cambie el `composer.lock`.

## Comandos habituales

| Fase de `verify` | Comando típico |
|---|---|
| build | `composer validate --strict` |
| types | `vendor/bin/phpstan analyse` |
| lint | `vendor/bin/php-cs-fixer fix --dry-run` o `vendor/bin/pint --test` |
| tests | `vendor/bin/phpunit` o `vendor/bin/pest` |
