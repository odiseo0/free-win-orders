# Free Win - Contexto técnico

## 1) Propósito

Este documento describe el contexto técnico actual del backend de Free Win: runtime, dependencias, puntos de entrada, configuración, persistencia, servicios externos y restricciones operativas.

Su función es responder qué tecnologías usa el proyecto y cómo están conectadas. Los patrones detallados de implementación se documentarán en `docs/system_patterns.md`.

## 2) Alcance

Este documento cubre:

- lenguaje, runtime y gestor del proyecto;
- frameworks y librerías principales;
- arranque y ensamblaje de la API;
- configuración mediante entorno;
- acceso asíncrono a PostgreSQL;
- pipeline de scraping y APIs externas;
- estado de migraciones, pruebas, despliegue y observabilidad;
- brechas técnicas conocidas.

Este documento no cubre:

- reglas funcionales de Pedidos y Órdenes;
- convenciones detalladas de código, definidas en `docs/conventions.md`;
- estrategia de pruebas, definida en `docs/testing.md`;
- patrones entre capas, reservados para `docs/system_patterns.md`.

## 3) Estado técnico resumido

| Área | Estado actual |
| --- | --- |
| Backend HTTP | FastAPI con routers para Usuarios, Direcciones y Roles |
| Runtime | Python 3.13 |
| Persistencia | SQLAlchemy 2 async y PostgreSQL mediante asyncpg |
| Configuración | pydantic-settings dividido en API, caché y base de datos |
| Caché | `InMemoryCache` local o Valkey mediante `valkey-py` async |
| Scraper | Extracción async, transformación multiproceso y carga PostgreSQL |
| Gestor del proyecto | PDM |
| Migraciones | Alembic previsto, todavía no configurado |
| Frontend | Fuera del alcance de este repositorio |
| Despliegue | Sin Dockerfile ni configuración de plataforma documentada |
| Observabilidad | Sin stack estructurado de logs, métricas o tracing definido |

## 4) Runtime y dependencias

### 4.1 Python y empaquetado

- Python requerido: `3.13.*`.
- Gestor del proyecto: PDM.
- Manifest: `pyproject.toml`.
- Lockfile: `pdm.lock`.
- El proyecto tiene `distribution = false`; se utiliza como aplicación, no como paquete publicable.

### 4.2 Dependencias declaradas

| Dependencia | Propósito principal | Uso representativo |
| --- | --- | --- |
| `fastapi[standard]` | API ASGI, routing, dependencias y servidor de desarrollo | `src/application.py`, `src/api/` |
| `beautifulsoup4` | Análisis del HTML de cartas | `src/core/services/scraper/transformers.py` |
| `SQLAlchemy` | ORM, consultas y persistencia async | `src/core/db/`, repositories |
| `asyncpg` | Driver PostgreSQL asíncrono | `src/core/db/session.py` |
| `httptools` | Parser HTTP de alto rendimiento para el servidor ASGI | runtime de FastAPI/Uvicorn |
| `valkey` | Cliente oficial asíncrono para el caché distribuido | `src/core/services/cache/valkey.py` |

`src/core/result.py` implementa `Result[T, E]`, `Ok[T]` y `Err[E]` con dataclasses y un type alias de Python 3.13. No requiere una dependencia externa.

### 4.3 Dependencias usadas de forma indirecta o no declarada

El código importa actualmente:

- `httpx` para solicitudes externas;
- `pydantic-settings` para configuración;
- pytest para la suite existente.

Estas dependencias no aparecen como entradas directas en `pyproject.toml`. Algunas pueden estar disponibles transitivamente o en el entorno local, pero el proyecto no debe depender de esa casualidad.

**Restricción actual**: antes de considerar reproducible la instalación, las dependencias runtime y de desarrollo usadas directamente deben declararse en sus grupos correspondientes y reflejarse en `pdm.lock`.

### 4.4 Librería estándar relevante

El scraper también utiliza:

- `asyncio` para concurrencia de I/O;
- `ProcessPoolExecutor` para parsing intensivo en CPU;
- `dataclasses` para estructuras intermedias;
- `Decimal` para precios;
- `zoneinfo` mediante las utilidades de zona horaria del proyecto.

## 5) Arranque y superficie HTTP

### 5.1 Punto de entrada

`src/application.py` crea la instancia `app` de FastAPI con:

- título `Free Win`;
- descripción `Free Win API REST.`;
- versión `1.0`;
- middleware CORS;
- router principal;
- endpoint de bienvenida `GET /`.

El comando de desarrollo documentado es:

```bash
pdm run fastapi dev src/application.py
```

### 5.2 Ensamblaje de routers

`src/api/api.py` registra actualmente:

| Router | Prefijo |
| --- | --- |
| Usuarios | `/users` |
| Direcciones de usuario | `/user-addresses` |
| Roles de usuario | `/user-roles` |
| Cartas | `/cards` |
| Publicaciones de cartas | `/card-listings` |

Cada router usa una `AsyncSession` proporcionada por la dependencia `get_db`.

### 5.3 CORS

El middleware actual permite:

- todos los orígenes;
- credenciales;
- todos los métodos;
- todos los headers.

**Restricción actual**: esta configuración es permisiva y sirve como estado inicial de desarrollo. Antes de un despliegue accesible públicamente, los orígenes y capacidades permitidas deben definirse mediante configuración de entorno y revisarse junto con el cliente real.

### 5.4 OpenAPI

FastAPI expone su documentación OpenAPI con el comportamiento predeterminado. Todavía no existe una política por entorno para habilitarla u ocultarla.

## 6) Organización del código

```text
src/
├── application.py
├── api/
│   ├── api.py
│   ├── cards/
│   ├── collections/
│   ├── orders/
│   └── users/
├── core/
│   ├── db/
│   ├── schema/
│   ├── services/
│   ├── types/
│   └── utils/
└── settings/
```

- `src/api/` organiza funcionalidad por componente.
- `src/core/` contiene capacidades compartidas.
- `src/settings/` separa configuración por responsabilidad.
- `src/api/users/` es el componente más desarrollado y sirve como referencia actual.
- `collections` y `orders` mantienen la estructura de capas, pero aún están incompletos.

La dirección de dependencias y responsabilidades se define en `docs/conventions.md`.

## 7) Configuración

### 7.1 Modelo de settings

La configuración usa `BaseSettings` y `SettingsConfigDict` de pydantic-settings. Ambos módulos leen `.env` y omiten claves adicionales.

- `src/settings/api_settings.py` define `APISettings` con prefijo `API_`.
- `src/settings/cache_settings.py` define `CacheSettings` con prefijo `CACHE_`.
- `src/settings/db_settings.py` define `DBSettings` para PostgreSQL.
- `src/settings/__init__.py` exporta los tres grupos de configuración.

### 7.2 Variables de base de datos declaradas

| Variable | Tipo | Propósito |
| --- | --- | --- |
| `DB_HOST` | `str` | Host de PostgreSQL |
| `DB_NAME` | `str` | Nombre de la base |
| `DB_PORT` | `int` | Puerto de PostgreSQL |
| `DB_USERNAME` | `str` | Usuario de conexión |
| `DB_PASSWORD` | `str` | Contraseña de conexión |

Todas son obligatorias en el modelo actual.

### 7.3 Brecha de configuración de sesión

`src/core/db/session.py` consume además estos atributos:

- `db_settings.url`;
- `db_settings.pool_size`;
- `db_settings.pool_timeout`;
- `db_settings.pool_recycle`;
- `db_settings.pool_overflow`.

Esos atributos no están definidos actualmente en `DBSettings`.

**Restricción actual**: la configuración de base de datos está incompleta y debe resolverse antes de considerar estable el arranque con PostgreSQL. La solución debe centralizar la construcción del DSN y los defaults del pool dentro de settings, sin hardcodearlos en consumidores.

### 7.4 Configuración de API

`APISettings` no declara todavía campos específicos. Es el punto previsto para opciones como CORS, entorno, exposición de OpenAPI o metadata configurable cuando sean necesarias.

## 8) Persistencia

### 8.1 Engine y sesiones

`src/core/db/session.py` crea:

- un engine asíncrono mediante `create_async_engine`;
- una `async_sessionmaker` con `expire_on_commit=False`;
- una sesión scoped por tarea mediante `async_scoped_session`.

`src/core/db/deps.py` ofrece:

- `get_db`: dependencia async para FastAPI;
- `session`: context manager async para procesos fuera del sistema de dependencias.

### 8.2 Base declarativa

`src/core/db/model.py` define:

- metadata con nombres deterministas para índices y restricciones;
- `Base`, que genera nombres de tabla en `snake_case` plural;
- `AwaitAttrs`, para cargar atributos de forma awaitable;
- `Date`, con `date_added` y `date_updated` timezone-aware.

### 8.3 DAO genérico

`src/core/db/dao.py` implementa operaciones reutilizables:

- obtener por id o campos;
- listar con paginación, filtros y ordenamiento;
- crear uno o varios registros;
- actualizar;
- eliminar uno o varios registros;
- contar;
- aplicar estrategias de carga de relaciones.

Los DAOs específicos de cada recurso heredan del genérico y proporcionan el modelo y schemas correspondientes.

### 8.4 PostgreSQL y zona horaria

El engine utiliza `asyncpg` y configura el servidor con zona horaria `America/Caracas`. Un listener registra un codec para `timestamptz` que normaliza fechas hacia la zona definida por el proyecto.

### 8.5 Migraciones

Alembic forma parte del stack previsto, pero el repositorio no contiene todavía configuración ni revisiones de migración.

**Restricción actual**: el esquema no debe considerarse gestionado para producción hasta que exista una historia de migraciones reproducible. La creación implícita de tablas no sustituye migraciones versionadas.

## 9) Modelos y datos actuales

### 9.1 Usuarios

`src/api/users/repository/models.py` contiene modelos para:

- `User`;
- `UserAddress`;
- `UserRole`.

El componente usa schemas Pydantic separados para base, creación, actualización y respuesta, y DAOs específicos basados en el DAO genérico.

**Restricción actual**: algunas relaciones y el catálogo externo de roles todavía están incompletos o apuntan a referencias pendientes. La definición de permisos no debe inferirse solamente desde estos modelos.

### 9.2 Cartas y publicaciones

Los modelos principales del componente se encuentran en `src/api/cards/repository/model.py`:

- `Card` conserva metadatos descriptivos y relativamente estáticos;
- `CardListing` representa la publicación consultada por los jugadores, con precio, condición y stock.

Una publicación almacena:

- nombre;
- set;
- código;
- precio como `Decimal`;
- rareza;
- condición;
- stock.

La restricción única combina `code` y `condition`. La carga usa `INSERT ... ON CONFLICT DO UPDATE` de PostgreSQL para actualizar publicaciones existentes.

El componente expone CRUD completo de Carta para apoyar el desarrollo y las pruebas actuales. Las Publicaciones son de lectura y ofrecen consulta individual, listado y búsqueda.

## 10) Servicios externos

### 10.1 CoolStuffInc

El scraper consulta CoolStuffInc para localizar publicaciones de cartas.

Configuración relevante en `src/core/constants.py`:

| Constante | Valor o función |
| --- | --- |
| `BASE_URL` | Página base de productos Yu-Gi-Oh! |
| `BASE_URL_SEARCH` | Endpoint de búsqueda |
| `REQUEST_TIMEOUT_SECONDS` | Timeout de 15 segundos |
| `SEARCH_RESULTS_PER_PAGE` | 50 resultados |
| `DELAY_BETWEEN_REQUESTS_SECONDS` | 1.5 segundos |
| `USER_AGENT` | Identificación del cliente HTTP |

El scraper debe tratar la estructura HTML como una dependencia externa inestable.

### 10.2 YGOPRODeck

`src/core/services/ygopro_api.py` contiene integración HTTP con la API de YGOPRODeck. Su URL base se define mediante `YGO_API_URL`.

El papel definitivo de esta fuente frente al scraper y la base propia todavía debe documentarse cuando el flujo de cartas esté completo.

## 11) Pipeline de scraping

### 11.1 Extracción

`src/core/services/scraper/scraper.py`:

- recibe una lista de nombres;
- codifica cada nombre para la URL;
- comparte un `httpx.AsyncClient`;
- limita la concurrencia a 50 solicitudes mediante `asyncio.Semaphore`;
- devuelve `None` para páginas no encontradas o errores de request.

### 11.2 Transformación

`src/core/services/scraper/transformers.py`:

- analiza HTML mediante Beautiful Soup;
- busca distintas estructuras de filas;
- usa expresiones regulares como fallback;
- normaliza publicaciones a dataclasses;
- elimina duplicados;
- ejecuta parsing en un `ProcessPoolExecutor` reutilizable;
- usa como máximo el número de CPU disponibles, con mínimo de un worker.

### 11.3 Carga

`src/core/services/scraper/loader.py`:

- separa persistencia mediante el protocolo `ScraperDataStore`;
- convierte precios a `Decimal`;
- permite probar la carga con stores falsos;
- implementa `SQLAlchemyScraperStore` para PostgreSQL;
- realiza upsert y commit del lote.

Esta separación mantiene abierta la posibilidad de ejecutar el pipeline fuera del proceso de API en el futuro.

### 11.4 Integración con la búsqueda

`src/core/services/scraper/search.py` adapta extracción y transformación al protocolo `CardListingSearch`. El caso de uso de búsqueda lo invoca únicamente cuando el caché y PostgreSQL no contienen resultados.

La búsqueda interactiva responde y almacena el resultado en caché, pero no ejecuta la etapa de carga. Persistir publicaciones sigue siendo una operación separada para no convertir una petición de usuario en una escritura implícita del pipeline.

## 12) Caché

`src/core/services/cache/` contiene:

- `Cache`: contrato asíncrono independiente del proveedor;
- `InMemoryCache`: implementación local con TTL;
- `ValkeyCache`: adaptador asíncrono de `valkey-py`;
- `get_cache`: dependencia de FastAPI que selecciona la implementación activa.

`CACHE_BACKEND` selecciona `memory` o `valkey`. El proveedor Valkey se configura con `CACHE_URL`, namespace de claves y timeouts de conexión. La URL se representa mediante `SecretStr` para evitar que credenciales futuras aparezcan accidentalmente en representaciones de settings.

El lifecycle de FastAPI ejecuta `PING` al iniciar cuando Valkey está seleccionado y cierra explícitamente el pool con `aclose()` al detener la aplicación. Un fallo de conexión impide el arranque, en vez de servir una aplicación configurada con un caché inaccesible.

La invalidación por prefijo usa `SCAN` y elimina claves en lotes de 100; no ejecuta `KEYS` sobre el keyspace. Todas las claves reciben el namespace configurado, `free-win:` por defecto.

Las respuestas de lectura de Cartas y Publicaciones usan un TTL actual de 300 segundos. Las mutaciones de Carta invalidan las claves de listas y actualizan o eliminan su clave individual.

## 13) Concurrencia y recursos

El backend combina dos modelos:

- **I/O async**: FastAPI, HTTPX, SQLAlchemy y asyncpg.
- **CPU multiproceso**: parsing del HTML mediante `ProcessPoolExecutor`.

Consideraciones actuales:

- el límite de scraping es una constante global de 50;
- el executor de parsing se crea de forma lazy y se reutiliza;
- no existe todavía un hook documentado de shutdown para cerrar explícitamente el executor;
- no existe una cola de tareas ni scheduler;
- no se ha documentado un modelo de ejecución periódica del scraper.

No debe añadirse infraestructura de workers antes de definir una necesidad concreta de reintentos, planificación, aislamiento o escalado.

## 14) Pruebas y herramientas de desarrollo

La suite utiliza pytest, declarado en `pyproject.toml`, y vive en `tests/`.

Cobertura actual:

- importación de FastAPI;
- transformación del scraper;
- normalización y carga mediante store falso;
- caché en memoria;
- adaptador Valkey mediante un cliente falso, sin red;
- fallback de búsqueda de publicaciones;
- error tipado al consultar una Carta inexistente.

La dirección de pruebas async es AnyIO con backend `asyncio` y HTTPX `ASGITransport`. La estrategia completa está en `docs/testing.md`.

No hay configuración actual para:

- Ruff;
- formatter independiente;
- type checker;
- coverage mínima;
- hooks de pre-commit.

Estas herramientas pueden adoptarse cuando exista una decisión explícita; no deben presentarse todavía como requisitos vigentes.

## 15) Ejecución y despliegue

### 15.1 Desarrollo local

Comandos documentados:

```bash
pdm install
pdm run fastapi dev src/application.py
pdm run pytest
```

El último comando utiliza la dependencia pytest declarada en `pyproject.toml`.

### 15.2 Artefactos de despliegue

El repositorio no contiene actualmente:

- Dockerfile;
- compose file;
- manifiestos de plataforma;
- scripts de migración;
- configuración de CI;
- definición de health check dedicada.

`GET /` es un endpoint de bienvenida, no un contrato de health check.

La estrategia de despliegue debe documentarse cuando exista un entorno objetivo real.

## 16) Observabilidad y seguridad operativa

### 16.1 Observabilidad

No existe todavía una solución definida para:

- logging estructurado;
- correlación de requests;
- métricas;
- tracing;
- alertas;
- auditoría de cambios de Pedidos y Órdenes.

La futura trazabilidad del dominio no debe confundirse con observabilidad técnica: ambas necesitan diseño, pero resuelven problemas diferentes.

### 16.2 Seguridad

Riesgos que deben resolverse antes de exposición pública:

- CORS permisivo;
- autenticación y autorización todavía no definidas;
- almacenamiento y respuesta de contraseñas pendientes de endurecimiento;
- roles y permisos incompletos;
- protección de datos de contacto y entrega;
- sanitización consistente de errores y logs.

Los secretos deben permanecer en variables de entorno y nunca registrarse ni incluirse en documentación o fixtures.

## 17) Brechas técnicas conocidas

| Brecha | Impacto | Documento propietario futuro |
| --- | --- | --- |
| Dependencias directas y de desarrollo incompletas | Instalación no completamente reproducible | `docs/tech_context.md` |
| `DBSettings` no expone atributos usados por la sesión | Arranque de persistencia incompleto | `docs/tech_context.md` |
| Sin migraciones Alembic | Esquema no versionado | `docs/tech_context.md` |
| Relaciones de roles incompletas | Modelo de permisos indefinido | `docs/general_documentation.md` |
| Contrato de errores inconsistente | API difícil de consumir de forma uniforme | `docs/system_patterns.md` |
| Sin auth ni autorización | API no preparada para exposición pública | documento de seguridad futuro |
| Sin lifecycle del executor | Recursos multiproceso sin cierre explícito | `docs/system_patterns.md` |
| Sin despliegue ni CI definidos | Operación no reproducible | documento de despliegue futuro |

Esta tabla describe el estado actual; no asigna prioridad automáticamente ni amplía el alcance de tareas futuras.

## 18) Decisiones técnicas

### DEC-20260720-python-fastapi-backend

- **Fecha**: 2026-07-20.
- **Contexto**: Free Win necesita una API asíncrona y sencilla para centralizar su flujo.
- **Decisión**: usar Python 3.13, FastAPI, Pydantic y SQLAlchemy async como base del backend.
- **Impacto**: las operaciones de red y base de datos deben conservar un flujo async coherente.
- **Evidencia**: `pyproject.toml`, `src/application.py`, `src/core/db/`.
- **Revisión**: reevaluar solamente si una limitación comprobada del stack impide una necesidad del proyecto.

### DEC-20260720-postgresql

- **Fecha**: 2026-07-20.
- **Contexto**: el proyecto necesita relaciones, consultas y upserts para datos de cartas y Pedidos.
- **Decisión**: PostgreSQL es la base de datos principal, mediante SQLAlchemy y asyncpg.
- **Impacto**: modelos, migraciones e integraciones pueden utilizar capacidades propias de PostgreSQL de manera consciente.
- **Evidencia**: `pyproject.toml`, `src/core/db/`, `src/core/services/scraper/loader.py`.
- **Revisión**: reevaluar si cambian de forma material los requisitos de persistencia.

### DEC-20260720-scraper-colocated

- **Fecha**: 2026-07-20.
- **Contexto**: separar el pipeline prematuramente aumentaría la complejidad del flujo inicial.
- **Decisión**: mantener el scraper dentro del backend con etapas y protocolos separables.
- **Impacto**: comparte código y despliegue con la API, pero puede extraerse cuando exista una necesidad real.
- **Evidencia**: `src/core/services/scraper/`.
- **Revisión**: reevaluar si requiere despliegue, escalado o planificación independiente.

## 19) Referencias

- `pyproject.toml`: runtime y dependencias declaradas.
- `pdm.lock`: resolución de dependencias.
- `src/application.py`: creación de la API.
- `src/api/api.py`: routers montados.
- `src/settings/`: configuración.
- `src/core/db/`: persistencia asíncrona.
- `src/api/users/`: modelos y flujo CRUD actual.
- `src/core/services/scraper/`: pipeline de cartas.
- `src/core/services/cache/`: contrato de caché y proveedores en memoria/Valkey.
- `src/core/services/ygopro_api.py`: integración con YGOPRODeck.
- `tests/`: cobertura automatizada actual.
- `docs/general_documentation.md`: dominio y estado funcional.
- `docs/testing.md`: estrategia de pruebas.

## 20) Glosario

- **ASGI**: interfaz asíncrona usada por FastAPI para servir la aplicación web.
- **DSN**: cadena con la información necesaria para conectarse a una base de datos.
- **Engine**: objeto SQLAlchemy que administra conexiones y ejecución contra la base.
- **Event loop**: ciclo que coordina operaciones async sin bloquear el proceso durante I/O.
- **Pool**: conjunto reutilizable de conexiones a PostgreSQL.
- **Upsert**: operación que inserta un registro o actualiza el existente ante un conflicto.

## 21) Checklist de actualización

- [ ] ¿La versión de Python y las dependencias coinciden con `pyproject.toml`?
- [ ] ¿Los routers y puntos de entrada siguen siendo correctos?
- [ ] ¿Las variables y defaults coinciden con `src/settings/`?
- [ ] ¿La descripción de persistencia coincide con `src/core/db/`?
- [ ] ¿Las etapas y límites del scraper siguen vigentes?
- [ ] ¿Una brecha conocida fue resuelta, reemplazada o ampliada?
- [ ] ¿Cambió el modelo de despliegue, observabilidad o seguridad?
- [ ] ¿Una decisión técnica necesita añadirse o revisarse?
