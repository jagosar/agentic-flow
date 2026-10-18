<!-- Adaptado de ECC (rules/common), https://github.com/affaan-m/ECC — MIT License, Copyright (c) 2026 Affaan Mustafa. -->
# Reglas comunes

Estas reglas valen para cualquier lenguaje. Las del lenguaje concreto (`.claude/rules/agentic/<lenguaje>.md`) las amplían.

## Precedencia

Cuando dos fuentes se contradicen, gana la primera de esta lista:
1. `architecture.md`: contratos (sección 6), convenciones (sección 7) y patrones a imitar del WP.
2. El estilo del código que ya existe en el repo (sección 4b).
3. Las reglas propias del proyecto en `.claude/rules/`, fuera de `agentic/`.
4. Estas reglas genéricas.

En un repo con código, imitar lo existente vale más que aplicar aquí una preferencia. Si una regla de aquí contradice el plan, se sigue el plan y la contradicción se anota en el informe.

## Diseño

- **Lo más simple que funcione.** Nada de abstracciones especulativas (YAGNI). Se extrae una función o un tipo cuando la repetición es real, no por si acaso.
- **Ficheros con un propósito.** Alta cohesión, poco acoplamiento. Organiza por funcionalidad o dominio, no por tipo de fichero.
- **Funciones cortas y planas.** Retorno temprano en vez de anidar condicionales; más de 4 niveles de anidación es una señal de que hay que partir.
- **Sin números mágicos.** Umbrales, tiempos y límites van en constantes con nombre o en configuración.
- **Datos inmutables por defecto** cuando el lenguaje lo facilita: se devuelve una copia en vez de modificar lo que entra, salvo que el contrato diga lo contrario.

## Errores y entradas

- Valida en las fronteras del sistema (entrada de usuario, ficheros, red, variables de entorno) y falla pronto, con un mensaje claro.
- Nunca te tragues un error en silencio. Captura la excepción concreta, no la genérica, salvo en el punto de entrada.
- Los mensajes de cara al usuario no filtran rutas internas, trazas, SQL ni secretos. El detalle va al log.
- Los errores que cruzan un contrato son los de la sección 6, con su nombre exacto.

## Nombres

- El nombre dice qué contiene o qué hace, sin necesitar un comentario.
- Los booleanos se leen como una afirmación (`is_expired`, `hasAccess`).
- Mayúsculas y prefijos siguen la convención del lenguaje (ver su fichero de reglas).

## Tests

- Estructura preparar, actuar, comprobar. Un comportamiento por test, con un nombre que lo describa (`devuelve_404_si_el_enlace_no_existe`).
- En un fix, el test que reproduce el bug va antes que la corrección y falla sin ella.
- Prueba los casos límite y los de error, no solo el camino feliz: vacío, nulo, máximo, duplicado, sin permisos.
- Los tests son deterministas: sin red real, sin depender de la hora ni del orden de ejecución. Los dobles de prueba se definen en los ficheros del propio WP.
- Un test que falla se arregla o se reporta. Nunca se desactiva para ponerlo en verde (el hook lo bloquea).

## Seguridad

- Ningún secreto en el código, en los tests ni en los informes: variables de entorno o un gestor de secretos.
- Consultas parametrizadas siempre; nunca se concatena entrada del usuario en SQL, en comandos de shell ni en rutas.
- Las rutas que llegan de fuera se normalizan y se comprueba que no salen del directorio permitido.
- Escapa la salida en plantillas HTML y trata como sospechoso todo lo que llega de una API externa, un webhook o un fichero subido.
- Autenticación y criptografía con librerías establecidas; nunca implementaciones propias.

## Antes de decir DONE

- Pasan los comandos de validación del WP y los tests de aceptación de sus AC.
- No quedan restos de depuración (`print`, `console.log`, `dbg!`, código comentado).
- El formateador y el linter del proyecto no dan avisos nuevos en tus ficheros.
