---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
<!-- Adaptado de ECC (rules/python), https://github.com/affaan-m/ECC — MIT License, Copyright (c) 2026 Affaan Mustafa. -->
# Python

Amplía las [reglas comunes](common.md).

## Estilo

- PEP 8. Anotaciones de tipo en todas las firmas públicas; `X | None` en vez de `Optional[X]` desde Python 3.10.
- `dataclass(frozen=True)` o `NamedTuple` para valores; `Protocol` para depender de una interfaz sin herencia.
- `pathlib.Path` para rutas, `with` para todo recurso que se abre, generadores para recorrer datos grandes.
- Nada de argumentos por defecto mutables (`def f(x=[])`). Nada de `import *`.
- Imports agrupados: librería estándar, terceros y locales.

## Errores

- Excepciones propias del dominio, que heredan de una base del módulo (`class StorageError(Exception)`).
- `raise NuevoError(...) from e` al traducir una excepción, para no perder la causa.
- Nunca `except:` ni `except Exception: pass`. Captura lo concreto.

## Tests

- `pytest` si el proyecto lo usa; si no, `unittest`, que no añade dependencias.
- Fixtures para preparar estado, `tmp_path` para ficheros, `monkeypatch` para el entorno. Sin escribir fuera del directorio temporal.
- `pytest.mark.parametrize` para tablas de casos.

## Seguridad

- Secretos con `os.environ["NOMBRE"]`, que falla si falta.
- Nunca `eval`, `exec`, `pickle` de datos externos ni `yaml.load` sin `SafeLoader`.
- `subprocess.run([...])` con lista de argumentos, sin `shell=True` cuando hay entrada externa.
- Si el proyecto lo usa, `bandit -r src/` como análisis estático.

## Comandos habituales

| Fase de `verify` | Comando típico |
|---|---|
| build | `python3 -m compileall -q src` |
| types | `mypy src` o `pyright` |
| lint | `ruff check .` (y `ruff format --check .`) |
| tests | `python3 -m pytest -q` o `python3 -m unittest discover -s tests` |
