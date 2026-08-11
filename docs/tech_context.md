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
| Backend HTTP | FastAPI con routers para Usuarios, Roles, Pedidos y Órdenes |
| Runtime | Python 3.13 |
| Persistencia | SQLAlchemy 2 async y PostgreSQL mediante asyncpg |
| Configuración | pydantic-settings dividido en API, caché y base de datos |
| Caché | `InMemoryCache` local o Valkey mediante `valkey-py` async |
| Búsqueda de cartas | Servicio separado `free-win-search` sobre PostgreSQL compartido |
| Gestor del proyecto | PDM |
| Migraciones | Alembic con historial local y propiedad de tablas separada por servicio |
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
| `SQLAlchemy` | ORM, consultas y persistencia async | `src/core/db/`, repositories |
| `asyncpg` | Driver PostgreSQL asíncrono | `src/core/db/session.py` |
| `httptools` | Parser HTTP de alto rendimiento para el servidor ASGI | runtime de FastAPI/Uvicorn |
| `valkey` | Cliente oficial asíncrono para el caché distribuido | `src/core/services/cache/valkey.py` |

`src/core/result.py` implementa `Result[T, E]`, `Ok[T]` y `Err[E]` con dataclasses y un type alias de Python 3.13. No requiere una dependencia externa.

### 4.3 Dependencias usadas de forma indirecta o no declarada

El código importa actualmente `httpx` para pruebas ASGI, `pydantic-settings` para
configuración y pytest para la suite existente.

Estas dependencias no aparecen como entradas directas en `pyproject.toml`. Algunas pueden estar disponibles transitivamente o en el entorno local, pero el proyecto no debe depender de esa casualidad.

**Restricción actual**: antes de considerar reproducible la instalación, las dependencias runtime y de desarrollo usadas directamente deben declararse en sus grupos correspondientes y reflejarse en `pdm.lock`.

### 4.4 Librería estándar relevante

La librería estándar aporta `asyncio` para el runtime asíncrono, `dataclasses`
para entidades y resultados, y `Decimal` para importes y snapshots de Órdenes.

## 5) Arranque y superficie HTTP

### 5.1 Punto de entrada

`src/application.py` crea la instancia `app` de FastAPI con:

- título `Free Win`;
- descripción funcional en español;
- versión `0.1.0`, alineada con `pyproject.toml`;
- licencia MIT;
- tags descritos y ordenados;
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
| Roles | `/roles` |
| Permisos | `/permissions` |
| Pedidos | `/order-periods` |
| Órdenes | `/order-requests` |

Cada router usa una `AsyncSession` proporcionada por la dependencia `get_db`.

### 5.3 CORS

El middleware actual permite:

- todos los orígenes;
- credenciales;
- todos los métodos;
- todos los headers.

**Restricción actual**: esta configuración es permisiva y sirve como estado inicial de desarrollo. Antes de un despliegue accesible públicamente, los orígenes y capacidades permitidas deben definirse mediante configuración de entorno y revisarse junto con el cliente real.

### 5.4 OpenAPI

OpenAPI es el contrato oficial entre el backend y sus clientes. La aplicación
publica metadata funcional, modelos HTTP transversales para errores, validación y
paginación, y `operation_id` estables en los componentes consolidados. La
descripción explica la identidad local temporal sin declarar un `securityScheme`
que el backend todavía no consume.

Todavía no existe una política por entorno para habilitar u ocultar OpenAPI.

## 6) Organización del código

```text
src/
├── application.py
├── api/
│   ├── api.py
│   ├── order_periods/
│   ├── order_requests/
│   ├── roles/
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
- `src/api/users/` ofrece el flujo CRUD de Usuarios y Direcciones.
- `order_periods` implementa Pedidos con estado temporal derivado, historial y autorización.
- `order_requests` implementa Órdenes, snapshots, revisión, precios y transiciones.
- `roles` implementa autorización, catálogo local y administración de Roles.

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

- `db_settings.SQLALCHEMY_DATABASE_URI`;
- `db_settings.pool_size`;
- `db_settings.pool_timeout`;
- `db_settings.pool_recycle`;
- `db_settings.pool_overflow`.

Esos atributos no están definidos actualmente en `DBSettings`.

**Restricción actual**: la configuración de base de datos está incompleta y debe resolverse antes de considerar estable el arranque con PostgreSQL. La solución debe centralizar la construcción del DSN y los defaults del pool dentro de settings, sin hardcodearlos en consumidores.

### 7.4 Configuración de API

`APISettings` no declara todavía campos específicos. Es el punto previsto para opciones como CORS, entorno, exposición de OpenAPI o metadata configurable cuando sean necesarias.

### 7.5 Identidad local temporal

`src/settings/auth_settings.py` define dos variables:

- `AUTH_MODE`, cuyo valor por defecto es `disabled` y cuyo único modo activo actual es `local`;
- `AUTH_LOCAL_USER_ID`, que identifica un usuario persistido cuando el modo es `local`.

Los endpoints protegidos responden `401` si falta cualquiera de ambos valores o el usuario no existe. La identidad local recibe todos los permisos del catálogo para facilitar pruebas manuales, sin modificar el rol persistido del usuario. Esta configuración no sustituye autenticación, hashing, sesiones ni tokens.

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

Alembic está configurado en `migrations/`. Sus revisiones históricas se conservan
sin modificaciones, incluida la revisión inicial `20260722_01` que permitía crear
el esquema completo sobre una base vacía.

La propiedad vigente del esquema está dividida entre servicios. `free-win-search`
administra `cards`, `card_listings`, sus tablas operativas de scraping e indexado,
y registra su historia en `free_win_search_alembic_version`. Este backend conserva
la FK de `order_request_items.card_listing_id` y una proyección de solo lectura de
`card_listings`, pero sus filtros de autogeneración excluyen todas las tablas del
servicio de búsqueda. Por ello una revisión nueva de Free Win no debe crear,
alterar ni eliminar esas tablas.

La tabla `permissions` continúa compartida. Los códigos utilizados exclusivamente
por el servicio de búsqueda pueden permanecer persistidos aunque no formen parte
del Enum de permisos reconocido por esta aplicación.

## 9) Modelos y datos actuales

### 9.1 Usuarios

`src/api/users/repository/models.py` contiene modelos para:

- `User`;
- `UserAddress`;
- `UserRole`.

El componente usa schemas Pydantic separados para base, creación, actualización y respuesta, y DAOs específicos basados en el DAO genérico.

`UserRole` conserva temporalmente la compatibilidad entre `User` y el nuevo `Role`. La restricción única sobre `UserRole.role_id` garantiza un solo puente por rol. `RolePermission` implementa la relación muchos-a-muchos entre roles y el catálogo persistente de permisos.

La persistencia del componente se concentra en `src/api/roles/repository/dao.py`. Los casos de uso no construyen consultas: utilizan `RoleDAO`, `PermissionDAO`, `RolePermissionDAO` y los DAOs del puente de Usuarios. La dependencia de identidad utiliza `AuthorizationDAO` para cargar `User → UserRole → Role → Permission`.

### 9.2 Referencia externa de Publicaciones

`free-win-search` es propietario de `cards` y `card_listings`. Este backend declara
en `src/api/order_requests/repository/card_listings.py` una `Table` parcial dentro
de `Base.metadata` para resolver la FK y consultar únicamente las columnas que
forman el snapshot de una Orden.

`CardListingReferenceDAO` ejecuta una lectura por ID y devuelve
`CardListingSnapshot`. No hay relaciones ORM, escrituras ni endpoints de cartas
en Free Win.

## 10) Servicio externo de búsqueda

La búsqueda, scraping y carga de cartas se ejecutan en `free-win-search`. Ambos
servicios usan PostgreSQL compartido, pero tienen composición de aplicación y
tablas Alembic independientes.

Free Win reconoce como externas `cards`, `card_listings`, `scrape_targets`,
`scrape_jobs`, `search_index_events` y `free_win_search_alembic_version`. Los
filtros de `migrations/ownership.py` impiden que `autogenerate` proponga crear,
alterar o eliminar esas tablas.

## 11) Contrato de datos compartido

La integración actual es síncrona a través de PostgreSQL: una Orden recibe un
`card_listing_id`, valida que exista y copia sus datos descriptivos. La FK
`order_request_items.card_listing_id → card_listings.id` permanece activa.

Si en el futuro los servicios dejan de compartir base de datos, esta frontera
deberá reemplazarse por un contrato remoto y una estrategia explícita para la
integridad referencial; ese cambio no se presupone en el diseño actual.

## 12) Caché

`src/core/services/cache/` contiene:

- `Cache`: contrato asíncrono independiente del proveedor;
- `InMemoryCache`: implementación local con TTL;
- `ValkeyCache`: adaptador asíncrono de `valkey-py`;
- `get_cache`: dependencia de FastAPI que selecciona la implementación activa.

`CACHE_BACKEND` selecciona `memory` o `valkey`. El proveedor Valkey se configura con `CACHE_URL`, namespace de claves y timeouts de conexión. La URL se representa mediante `SecretStr` para evitar que credenciales futuras aparezcan accidentalmente en representaciones de settings.

El lifecycle de FastAPI ejecuta `PING` al iniciar cuando Valkey está seleccionado y cierra explícitamente el pool con `aclose()` al detener la aplicación. Un fallo de conexión impide el arranque, en vez de servir una aplicación configurada con un caché inaccesible.

La invalidación por prefijo usa `SCAN` y elimina claves en lotes de 100; no ejecuta `KEYS` sobre el keyspace. Todas las claves reciben el namespace configurado, `free-win:` por defecto.

El caché permanece como capacidad compartida disponible para los componentes de
Free Win. La extracción del buscador no elimina su configuración, lifecycle ni
pruebas de proveedores.

## 13) Concurrencia y recursos

El backend mantiene I/O asíncrono en FastAPI, SQLAlchemy y asyncpg. El lifecycle
inicia y cierra el proveedor de caché; las sesiones de base de datos conservan un
alcance por solicitud. Free Win no mantiene executors, workers ni tareas de
scraping.

## 14) Pruebas y herramientas de desarrollo

La suite utiliza pytest, declarado en `pyproject.toml`, y vive en `tests/`.

Cobertura actual:

- importación de FastAPI;
- caché en memoria;
- adaptador Valkey mediante un cliente falso, sin red;
- reglas, autorización y contratos HTTP de Pedidos y Órdenes;
- lectura de la proyección externa de `card_listings`;
- aislamiento de tablas externas durante `autogenerate`.

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

Después de aplicar el esquema, el catálogo se inicializa explícitamente y fuera del arranque HTTP:

```bash
pdm run alembic upgrade head
pdm run python -m src.api.roles.bootstrap
```

Sobre una base vacía, el primer bootstrap crea `Admin`, `User`, sus permisos y los puentes necesarios. Después se registra el primer usuario mediante `POST /users`. Cuando el usuario ya existe, puede promoverse ejecutando nuevamente el bootstrap:

```bash
pdm run python -m src.api.roles.bootstrap --admin-user-id 123
```

El bootstrap es idempotente. La variante con `--admin-user-id` revierte sus cambios si el ID no existe.

### 15.2 Artefactos de despliegue

El repositorio no contiene actualmente:

- Dockerfile;
- compose file;
- manifiestos de plataforma;
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
- autenticación real, hashing de contraseñas y tokens todavía no definidos;
- la identidad `AUTH_MODE=local` es exclusivamente temporal y está deshabilitada por defecto;
- el almacenamiento de contraseñas sigue pendiente de endurecimiento, aunque ya no se expone en respuestas;
- protección de datos de contacto y entrega;
- sanitización consistente de errores y logs.

Los secretos deben permanecer en variables de entorno y nunca registrarse ni incluirse en documentación o fixtures.

## 17) Brechas técnicas conocidas

| Brecha | Impacto | Documento propietario futuro |
| --- | --- | --- |
| Dependencias directas y de desarrollo incompletas | Instalación no completamente reproducible | `docs/tech_context.md` |
| `DBSettings` no expone atributos usados por la sesión | Arranque de persistencia incompleto | `docs/tech_context.md` |
| Contrato de errores inconsistente | API difícil de consumir de forma uniforme | `docs/system_patterns.md` |
| Solo identidad local temporal | API no preparada todavía para exposición pública | documento de seguridad futuro |
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
- **Evidencia**: `pyproject.toml`, `src/core/db/`, `migrations/`.
- **Revisión**: reevaluar si cambian de forma material los requisitos de persistencia.

### DEC-20260811-search-schema-ownership

- **Fecha**: 2026-08-11.
- **Contexto**: la búsqueda de cartas fue extraída a un servicio independiente que conserva la misma base PostgreSQL.
- **Decisión**: `free-win-search` posee sus tablas y usa `free_win_search_alembic_version`; Free Win conserva la FK, la proyección de lectura y excluye las tablas externas de `autogenerate`.
- **Impacto**: el desacoplamiento de aplicación no rompe las relaciones existentes ni duplica la gestión del esquema.
- **Evidencia**: `migrations/ownership.py`, `src/api/order_requests/repository/card_listings.py`.
- **Revisión**: reevaluar si los servicios dejan de compartir PostgreSQL.

### DEC-20260722-local-authorization

- **Fecha**: 2026-07-22.
- **Contexto**: los límites de acceso deben existir antes de implementar login o JWT.
- **Decisión**: resolver una identidad local configurable, cargar permisos desde PostgreSQL en cada solicitud y autorizar mediante permisos explícitos y propiedad.
- **Impacto**: no se sirven privilegios obsoletos desde caché; la dependencia `get_current_user` puede reemplazarse en pruebas y posteriormente por autenticación real.
- **Evidencia**: `src/settings/auth_settings.py`, `src/api/roles/domain/policies.py`, `src/api/roles/infrastructure/auth.py`.
- **Revisión**: reemplazar la identidad local al incorporar el componente de autenticación.

## 19) Referencias

- `pyproject.toml`: runtime y dependencias declaradas.
- `pdm.lock`: resolución de dependencias.
- `src/application.py`: creación de la API.
- `src/api/api.py`: routers montados.
- `src/settings/`: configuración.
- `src/core/db/`: persistencia asíncrona.
- `src/api/users/`: modelos y flujo CRUD actual.
- `src/api/order_requests/repository/card_listings.py`: proyección externa de Publicaciones.
- `migrations/ownership.py`: tablas excluidas de las migraciones locales.
- `src/core/services/cache/`: contrato de caché y proveedores en memoria/Valkey.
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
- [ ] ¿El límite con `free-win-search` y sus tablas externas sigue vigente?
- [ ] ¿Una brecha conocida fue resuelta, reemplazada o ampliada?
- [ ] ¿Cambió el modelo de despliegue, observabilidad o seguridad?
- [ ] ¿Una decisión técnica necesita añadirse o revisarse?
