# Free Win - Guía para agentes

## Propósito y criterio de producto

Free Win es el backend comunitario para facilitar la compra de cartas de Yu-Gi-Oh! difíciles de conseguir localmente. Prioriza soluciones sencillas, mantenibles y útiles para jugadores y administradores; evita procesos corporativos, sobrearquitectura y dependencias o servicios sin una necesidad actual.

El núcleo funcional y técnico de este backend son los **Pedidos** y las **Órdenes**. La búsqueda y carga de cartas pertenecen al servicio separado `free-win-search`, aunque ambos servicios comparten PostgreSQL y las Órdenes conservan su FK hacia `card_listings`. Las funcionalidades futuras orientan el producto, pero no amplían por sí mismas el alcance de una tarea.

## Vocabulario obligatorio

- **Pedido**: período que abren los administradores para recibir solicitudes; no es una compra individual ni inmediata.
- **Orden**: envío individual de un usuario dentro de un Pedido. Puede revisarse y procesarse parcialmente. El nombre es provisional: no hagas renombrados amplios sin acordarlo.

Flujo base: un administrador abre un Pedido, los usuarios envían Órdenes y el administrador las revisa y actualiza, con resultados parciales cuando corresponda.

Consulta el dominio, el estado implementado y las reglas detalladas de las Órdenes en [docs/general_documentation.md](docs/general_documentation.md).

## Arquitectura y límites

Este repositorio contiene únicamente el backend Python. Los componentes de `src/api/` se organizan en `domain/`, `application/`, `infrastructure/` y `repository/`.

- El dominio no depende de FastAPI, SQLAlchemy ni detalles de red.
- Infraestructura y persistencia pueden depender de aplicación y dominio; los routers se mantienen delgados.
- `src/core/` solo contiene infraestructura base o capacidades compartidas por más de un componente.
- Mantén I/O asíncrono en red, archivos y base de datos; no ocultes operaciones bloqueantes en funciones `async`.
- Los errores recuperables usan `Result`, `Ok` y `Err` con errores concretos del dominio. Los casos de uso devuelven `Result`; infraestructura lo resuelve exhaustivamente y los routers nunca lo exponen directamente.

Las convenciones obligatorias de código, HTTP, persistencia, seguridad y asincronía están en [docs/conventions.md](docs/conventions.md). Los patrones y ejemplos de implementación están en [docs/system_patterns.md](docs/system_patterns.md).

## Cartas y datos compartidos

No añadas búsqueda, scraping ni CRUD de cartas a este backend. `free-win-search` administra esas capacidades y las tablas `cards` y `card_listings`. Free Win puede leer una proyección mínima de `card_listings` para validar y copiar snapshots de los ítems de una Orden; no debe alterar el esquema externo ni eliminar sus tablas, FK o permisos persistidos.

Consulta [docs/tech_context.md](docs/tech_context.md) y [docs/system_patterns.md](docs/system_patterns.md) antes de modificar este límite.

## Forma de trabajo

Antes de editar, lee la documentación relevante, revisa los archivos cercanos y conserva los cambios ajenos del árbol de trabajo. Implementa el cambio mínimo completo, con tipos en interfaces y funciones nuevas, sin secretos ni valores locales.

No inventes reglas de negocio irreversibles. Cuando falte una definición, declara la ambigüedad y elige solo la alternativa más simple y reversible si es segura.

Para cambios de esquema, usa migraciones Alembic cuando la infraestructura esté disponible; no dependas de la creación implícita de tablas en producción.

## Validación y documentación

Para errores corregidos o reglas nuevas, añade una prueba que fallaba antes del cambio. Mantén las pruebas unitarias independientes de servicios externos y declara con claridad cualquier validación no ejecutada. Al terminar un cambio, solicita al usuario una prueba manual.

La documentación detallada vive en `docs/`; actualiza el documento propietario cuando un cambio vuelva incorrecta una afirmación vigente:

- [docs/general_documentation.md](docs/general_documentation.md): dominio, alcance, estado y navegación.
- [docs/conventions.md](docs/conventions.md): reglas de implementación.
- [docs/system_patterns.md](docs/system_patterns.md): patrones y decisiones técnicas.
- [docs/tech_context.md](docs/tech_context.md): stack, configuración y operación.
- [docs/testing.md](docs/testing.md): estrategia y comandos de prueba.
- [docs/formatting.md](docs/formatting.md): formato y mantenimiento de documentación.

Parte de la documentación histórica puede seguir describiendo otro proyecto. No tomes referencias a Payments Webservice, Go o proveedores de pago como reglas de Free Win; contrástalas con el código, el README y los documentos ya adaptados.
