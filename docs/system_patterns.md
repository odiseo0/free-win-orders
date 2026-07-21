# Free Win - Patrones del sistema

## 1) Propósito

Este documento explica los patrones arquitectónicos y de implementación presentes en el backend de Free Win. Describe cómo colaboran las capas, qué responsabilidades tiene cada pieza y qué patrones deben conservarse al extender el proyecto.

También identifica implementaciones todavía incompletas. Un comportamiento existente no se considera automáticamente un patrón recomendado.

## 2) Alcance

Este documento cubre:

- composición de la aplicación y routers;
- arquitectura por componente y recurso;
- schemas Pydantic;
- casos de uso y resultados explícitos;
- DAOs, modelos SQLAlchemy y sesiones;
- filtros, paginación y carga de relaciones;
- pipeline de scraping;
- concurrencia async y multiproceso;
- extensión de recursos siguiendo la estructura actual;
- patrones incompletos que necesitan una decisión posterior.

Este documento no cubre:

- reglas completas de Pedidos y Órdenes;
- convenciones generales de estilo, definidas en `docs/conventions.md`;
- stack, variables y operación, documentados en `docs/tech_context.md`;
- estrategia detallada de pruebas, definida en `docs/testing.md`.

## 3) Clasificación de patrones

Este documento usa tres estados:

- **Patrón actual**: está implementado, es coherente con la arquitectura y puede reutilizarse.
- **Patrón en evolución**: existe una dirección reconocible, pero el contrato todavía necesita completarse.
- **Patrón legacy**: existe en el código, pero no debe copiarse a funcionalidad nueva.

Antes de reproducir una implementación, comprueba su clasificación y las restricciones que la acompañan.

## 4) Arquitectura hexagonal pragmática

### 4.1 Unidad principal: componente

Los conceptos funcionales se agrupan bajo `src/api/<component>/`. Cada componente posee sus schemas, casos de uso, endpoints y persistencia.

```text
src/api/users/
├── domain/
├── application/
├── infrastructure/
└── repository/
```

**Patrón actual**:

- `domain` expresa datos y conceptos sin depender de FastAPI o SQLAlchemy;
- `application` coordina operaciones del recurso;
- `infrastructure` adapta HTTP hacia aplicación;
- `repository` adapta SQLAlchemy hacia las operaciones de persistencia.

La arquitectura es pragmática porque no exige una interfaz o clase adicional para cada operación. Una función de aplicación puede usar un DAO concreto cuando ese límite ya es suficiente y fácil de sustituir en pruebas.

### 4.2 Unidad secundaria: recurso

Un componente puede contener varios recursos relacionados. `users` contiene:

- Usuarios;
- Direcciones de usuario;
- Roles de usuario.

Cada recurso mantiene archivos paralelos en sus capas:

```text
domain/users.py
application/users_cases.py
infrastructure/users_api.py
repository/dao.py
repository/models.py
```

**Patrón actual**: separa por recurso cuando cada parte tenga operaciones o schemas propios, pero mantén los recursos bajo un mismo componente cuando compartan un contexto funcional estrecho.

### 4.3 Dirección de dependencias

```text
Infrastructure ──→ Application ──→ Repository
       │                 │               │
       └──────────────→ Domain ←─────────┘
                              
Shared technical capabilities live in Core
```

La representación muestra dependencias de código, no flujo de datos estricto.

- infraestructura conoce schemas y casos de uso;
- aplicación conoce schemas, modelos de retorno y DAO;
- repository conoce schemas de entrada y SQLAlchemy;
- domain solo conoce el modelo base compartido de Pydantic;
- `core` ofrece capacidades técnicas sin pertenecer a un dominio concreto.

**Restricción**: la aplicación actual importa el DAO concreto directamente. Si una operación necesita múltiples implementaciones o una sustitución compleja, podrá introducirse un puerto explícito, pero no debe hacerse de forma preventiva.

## 5) Composición de la aplicación

### 5.1 Composition root de FastAPI

`src/application.py` actúa como punto principal de composición:

1. crea `FastAPI`;
2. instala middleware;
3. incluye el router de la API;
4. define endpoints globales mínimos.

**Patrón actual**: la creación de la aplicación y las decisiones globales no se dispersan entre componentes.

### 5.2 Composición de routers

`src/api/api.py` reúne los routers exportados por los componentes y les asigna un prefijo:

```python
router = APIRouter()
router.include_router(users_router, prefix="/users")
router.include_router(user_addresses_router, prefix="/user-addresses")
router.include_router(user_roles_router, prefix="/user-roles")
```

El recorrido de exportación es:

```text
infrastructure/<resource>_api.py
        ↓
infrastructure/__init__.py
        ↓
<component>/__init__.py
        ↓
src/api/api.py
        ↓
src/application.py
```

**Patrón actual**: los módulos superiores importan la superficie pública del componente, no sus archivos internos.

### 5.3 Endpoint delgado

Un endpoint se limita a:

1. declarar el contrato HTTP;
2. recibir la sesión y los datos;
3. invocar el caso de uso;
4. devolver o traducir su resultado.

```python
@router.post("/")
async def create_user_address(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_address_in: UserAddressCreate,
) -> UserAddressResponse:
    return await create(db, obj_in=user_address_in)
```

**Patrón actual**: no construyas queries, modelos SQLAlchemy ni reglas de dominio dentro del endpoint.

## 6) Familia de schemas Pydantic

### 6.1 Separación por intención

Cada recurso utiliza una familia de schemas:

```text
Resource
├── ResourceCreate
├── ResourceUpdate
└── ResourceResponse
```

- `Resource` declara campos compartidos como opcionales;
- `ResourceCreate` hace obligatorios los campos necesarios para crear;
- `ResourceUpdate` hereda campos opcionales para `PATCH`;
- `ResourceResponse` añade campos generados, como `id`.

Ejemplo actual:

```python
class UserRole(BaseModel):
    role_id: int | None = None


class UserRoleCreate(UserRole):
    role_id: int


class UserRoleUpdate(UserRole):
    pass


class UserRoleResponse(UserRole):
    id: int
```

### 6.2 Modelo base compartido

Todos los schemas heredan de `src.core.schema.BaseModel`, que centraliza:

- eliminación de espacios laterales en strings;
- creación desde atributos ORM;
- aliases en camelCase;
- población por nombre Python o alias;
- serialización de enums.

**Patrón actual**: la configuración transversal se modifica en un solo lugar. Una excepción propia de un recurso permanece en su schema.

### 6.3 Contratos de entrada y salida

**Patrón en evolución**: separar `Create`, `Update` y `Response` expresa correctamente la intención, pero los schemas de respuesta todavía deben revisarse por seguridad y nulabilidad.

En particular, `UserResponse` hereda actualmente `password` desde `User`. Este campo no debe formar parte de un contrato público aunque su valor esté transformado. Los nuevos recursos deben diseñar su respuesta desde la información que sea seguro exponer.

## 7) Casos de uso funcionales

### 7.1 Funciones por operación

La capa de aplicación usa funciones async a nivel de módulo:

- `get_one`;
- `get_multi`;
- `create`;
- `update`;
- `remove`.

**Patrón actual**: no se introduce una clase de servicio cuando las funciones no necesitan estado propio. La sesión se recibe explícitamente y el DAO del recurso se importa con alias `dao`.

```python
from typing import Never

from src.api.users.repository import dao_users as dao
from src.core import Ok, Result


async def create(db: AsyncSession, obj_in: UserCreate) -> Result[User, Never]:
    user = await dao.create(db, obj_in=obj_in)
    return Ok(user)
```

### 7.2 Importaciones solo para tipos

Los casos de uso usan `TYPE_CHECKING` para evitar una importación runtime que solo se necesita en anotaciones:

```python
if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
```

**Patrón actual**: combina este patrón con `from __future__ import annotations` cuando reduzca ciclos o costo de importación.

### 7.3 Resultados explícitos y exhaustivos

`src/core/result.py` define una unión discriminada mínima mediante dataclasses inmutables:

```python
@dataclass(frozen=True, slots=True)
class Ok[T]:
    value: T


@dataclass(frozen=True, slots=True)
class Err[E]:
    error: E


type Result[T, E] = Ok[T] | Err[E]
```

La aplicación representa los resultados esperados mediante esta unión:

```text
DAO result
   ├── success ──→ Ok(value)
   └── recoverable failure ──→ Err(TypedDomainError)
```

Los errores recuperables son valores concretos definidos en el dominio, por ejemplo `UserNotFound`. No heredan necesariamente de `Exception`, porque no se lanzan: viajan dentro de `Err`.

```python
async def get_one(
    db: AsyncSession,
    user_id: int,
) -> Result[User, UserNotFound]:
    user = await dao.get(db, user_id)

    if user is Empty:
        return Err(UserNotFound(user_id))

    return Ok(user)
```

**Patrón actual**:

- usa `Result[T, E]` para errores que forman parte del flujo esperado;
- usa tipos concretos para `E`, nunca strings o `Exception` genérica;
- usa `Result[T, Never]` cuando no existe una variante recuperable;
- reserva excepciones para bugs, invariantes rotas o infraestructura inesperada;
- no proporciona `unwrap`, para que el consumidor deba reconocer el resultado.

### 7.4 Traducción exhaustiva en infraestructura

La infraestructura consume el `Result` mediante pattern matching:

```python
match result:
    case Ok(user):
        return user
    case Err(UserNotFound()):
        raise HTTPException(status_code=404, detail="El usuario no existe")
    case unexpected:
        assert_never(unexpected)
```

`assert_never` permite que un type checker detecte una nueva variante de error no manejada. La garantía depende de ejecutar análisis estático estricto; Python no impone exhaustividad durante compilación como Rust.

**Patrón actual**: los routers nunca devuelven el wrapper. Traducen `Ok` al schema exitoso y cada `Err` a su contrato HTTP.

## 8) Persistencia mediante DAO genérico

### 8.1 Adaptador genérico

`DAO[ModelType, CreateSchema, UpdateSchema]` concentra comportamiento CRUD compartido:

```text
ResourceDAO
    ↓ specializes
DAO[ORM Model, Create Schema, Update Schema]
    ↓ executes
SQLAlchemy AsyncSession
```

Un DAO específico puede permanecer vacío mientras el comportamiento genérico sea suficiente:

```python
class UserAddressDAO(DAO[UserAddress, UserAddressCreate, UserAddressUpdate]):
    pass


dao_user_addresses = UserAddressDAO(UserAddress)
```

**Patrón actual**: añade métodos al DAO específico solo para consultas o persistencia propias del recurso.

### 8.2 Conversión de schemas a datos

En creación:

- acepta un schema Pydantic o diccionario;
- usa `model_dump(mode="python")`;
- ejecuta `INSERT ... RETURNING id`;
- recupera el modelo creado.

En actualización:

- usa `model_dump(mode="json", exclude_unset=True)`;
- actualiza únicamente campos presentes;
- usa `UPDATE ... RETURNING id`;
- recupera el modelo actualizado.

**Patrón actual**: la semántica de `PATCH` se conserva mediante `exclude_unset=True`.

### 8.3 Commit configurable

Las operaciones de escritura aceptan `commit: bool = True`.

- con `commit=True`, la operación confirma inmediatamente;
- con `commit=False`, el consumidor puede coordinar varias escrituras y confirmar después.

**Patrón actual**: usa el commit predeterminado para una operación CRUD independiente. Usa `commit=False` únicamente cuando un caso de uso sea dueño explícito de una transacción mayor y se responsabilice de commit o rollback.

### 8.4 Traducción de excepciones

`catch_sqlalchemy_exception` captura `IntegrityError` y `SQLAlchemyError`.

**Patrón legacy**: actualmente vuelve a lanzar `Exception` sin conservar un tipo útil para aplicación. Este comportamiento no debe extenderse. La evolución esperada es traducir errores de persistencia a categorías explícitas, preservando la causa y permitiendo una respuesta HTTP coherente.

## 9) Modelos SQLAlchemy como dataclasses

### 9.1 Base declarativa

Los modelos usan:

```python
class User(MappedAsDataclass, Base, Date, kw_only=True):
    ...
```

- `MappedAsDataclass` proporciona semántica de dataclass;
- `Base` aporta metadata, tabla automática y atributos awaitable;
- `Date` aporta timestamps;
- `kw_only=True` evita construcción posicional ambigua.

### 9.2 Nombres y restricciones

`Base.__tablename__` transforma el nombre de la clase a `snake_case` plural. La metadata asigna nombres deterministas a:

- índices;
- claves únicas;
- checks;
- claves foráneas;
- claves primarias.

**Patrón actual**: las migraciones futuras pueden detectar y referenciar restricciones con nombres estables.

### 9.3 Mixins de fecha

`Date` añade:

- `date_added`, generado localmente y por servidor;
- `date_updated`, nullable y actualizado al modificar.

**Patrón actual**: úsalo en entidades persistentes que necesiten trazabilidad temporal básica. La trazabilidad completa de estados de Pedidos y Órdenes requerirá entidades o eventos adicionales; los dos timestamps no la sustituyen.

### 9.4 Relaciones y carga async

`AwaitAttrs` ofrece:

- `await_attr.<relationship>` para acceso awaitable;
- `await_load(attr)` para cargar un atributo tipado.

El DAO también acepta estrategias SQLAlchemy mediante `options`, como `joinedload` o `selectinload`.

**Patrón en evolución**: las relaciones del componente `users` todavía contienen referencias pendientes y lados de `back_populates` incompletos. No deben usarse como plantilla hasta definir correctamente `Role`, `UserRole`, `UserAddress` y sus cardinalidades.

## 10) Ausencia explícita mediante sentinel

El DAO usa `Empty`/`EmptyType` para distinguir un registro inexistente de un valor válido:

```text
DAO.get(id)
   ├── row found ──→ Model
   └── no row ──→ Empty sentinel
```

Esto evita usar `None` cuando `None` pueda ser un valor significativo en otros contratos.

**Patrón en evolución**: `EmptyType` es actualmente un alias de la clase `Empty`, y los consumidores comparan identidad contra esa clase. Antes de ampliar el patrón debe definirse si se usará una instancia singleton, un tipo de resultado o `None` con tipos explícitos.

No mezcles varias representaciones de ausencia dentro de una misma operación.

## 11) Consultas, filtros y ordenamiento

### 11.1 Filtros simples

`DAO.get_multi` acepta `where: dict[str, Any]`:

- un valor escalar produce igualdad;
- una lista o tuple produce `IN`.

**Patrón actual**: los nombres de campo deben provenir de contratos controlados; no expongas acceso arbitrario a atributos del modelo desde input sin validación.

### 11.2 Filtros tipados

`src/core/utils/filters.py` define dataclasses para:

- fecha exacta;
- antes y después;
- rango de fechas;
- búsqueda de texto;
- igualdad de campo;
- filtro mensual;
- ordenamiento.

`DAO.apply_filters` traduce estas estructuras a expresiones SQLAlchemy.

**Patrón actual**: aplicación expresa intención mediante tipos y repository traduce esa intención a SQL.

**Patrón en evolución**: `AnyFieldFilter` y `DAO.any_filter` no están completos y no deben utilizarse como capacidad disponible.

### 11.3 Ordenamiento

El DAO admite:

- un objeto `OrderBy` con `ascending` o `descending`;
- una lista de pares `(campo, es_descendente)`;
- orden predeterminado por `date_added` descendente.

Si el campo es una relación no cargada mediante join, el DAO puede añadir el join antes de ordenar.

### 11.4 Paginación

El DAO interpreta `page` como offset y aplica:

```python
statement.offset(page).limit(shows)
```

La aplicación intenta convertir un número de página a offset mediante:

```python
(page - 1) * shows
```

**Patrón en evolución**: los endpoints comienzan actualmente en `page=0`, mientras aplicación presupone una numeración desde 1. Esto puede producir offsets negativos y debe resolverse con un contrato único.

Antes de ampliar listados, decide y documenta una de estas alternativas:

- `page` basado en 1 y conversión central a offset;
- `offset` explícito y sin conversión;
- objeto de paginación que encapsule ambas partes.

La respuesta de lista también debe definir de forma uniforme items, total, página y tamaño cuando el contrato público se estabilice.

## 12) Sesión por solicitud

### 12.1 Dependencia FastAPI

`get_db` abre una `AsyncSession`, la entrega al endpoint y la cierra al terminar:

```text
HTTP request
    ↓
get_db opens AsyncSession
    ↓
endpoint → use case → DAO
    ↓
get_db closes AsyncSession
```

**Patrón actual**: una misma solicitud propaga la sesión explícitamente entre capas.

### 12.2 Uso fuera de FastAPI

`session()` ofrece un context manager async para procesos que no pasan por inyección de dependencias, como futuros jobs o comandos.

**Patrón actual**: no importes una sesión global y la compartas entre tareas. Abre el alcance mediante la dependencia o el context manager apropiado.

## 13) Pipeline ETL del scraper

### 13.1 Separación por etapas

El scraper sigue un patrón Extract, Transform, Load:

```text
scraper.py          transformers.py          loader.py
Extract        →       Transform       →       Load
HTTP pages             CardListing             PostgreSQL
```

Cada etapa tiene un contrato diferente:

- extracción produce pares de nombre y HTML opcional;
- transformación produce publicaciones normalizadas;
- carga convierte tipos y persiste publicaciones.

**Patrón actual**: conserva las etapas separadas aunque hoy compartan el mismo módulo técnico dentro del backend.

### 13.2 Extracción asíncrona y limitada

La extracción:

- comparte un `AsyncClient`;
- crea una tarea por carta;
- limita concurrencia con `Semaphore`;
- configura headers, redirects y timeout;
- representa una página no disponible como `None`.

```text
cards
  ├── task ─┐
  ├── task ─┼─→ Semaphore ─→ shared AsyncClient
  └── task ─┘
```

**Patrón actual**: toda concurrencia externa debe tener un límite explícito y un cliente reutilizable dentro del batch.

### 13.3 Transformación tolerante a HTML variable

El transformador aplica selectores en orden y usa parsing de texto como fallback. Una fila inválida no cancela todo el lote.

**Patrón actual**:

- intenta estructuras específicas antes del fallback;
- produce defaults explícitos para campos desconocidos;
- descarta resultados sin identidad o precio útil;
- deduplica al final de la transformación.

**Restricción**: capturar `Exception` por fila mantiene el batch, pero oculta la causa. La evolución debe conservar tolerancia parcial y añadir una forma segura de observar fallos de parsing.

### 13.4 Puerto estructural para carga

`ScraperDataStore` es un `Protocol`:

```python
class ScraperDataStore(Protocol):
    async def upsert_card_listings(
        self,
        rows: Sequence[dict[str, object]],
    ) -> int: ...
```

`load_scraped_data` depende del protocolo y `SQLAlchemyScraperStore` implementa el adaptador real.

```text
load_scraped_data
      ↓ depends on
ScraperDataStore protocol
      ↑ implemented by
SQLAlchemyScraperStore / FakeScraperStore
```

**Patrón actual**: introduce un protocolo en un límite donde ya existen dos motivos reales: desacoplar persistencia y probar sin base de datos.

### 13.5 Upsert idempotente

La identidad persistente de una publicación es `(code, condition)`. Ante conflicto, se actualizan datos variables como precio, rareza y stock.

**Patrón actual**: una nueva ejecución puede actualizar el estado observado sin crear filas duplicadas para la misma identidad.

**Restricción**: la identidad y los campos actualizados deben revisarse si distintas ediciones o vendedores pueden compartir código y condición.

### 13.6 Búsqueda de publicaciones con fallback

La búsqueda pública de publicaciones aplica una cadena de resolución explícita:

```text
Consulta normalizada
       ↓
Caché ── hit ──────────────────────────────→ respuesta
       ↓ miss
PostgreSQL ── resultados ──────────────────→ caché → respuesta
       ↓ vacío
Scraper (Extract + Transform) ─────────────→ caché → respuesta
```

`CardListingSearch` encapsula la búsqueda externa y `ScraperCardListingSearch` adapta las etapas existentes de extracción y transformación. El caso de uso no conoce HTTPX, Beautiful Soup ni la forma de construir la URL externa.

Los resultados obtenidos del scraper usan `CardListingResponse`, igual que los persistidos. Sus identificadores pueden ser nulos porque responder una búsqueda no implica que la publicación ya haya sido cargada en PostgreSQL.

**Patrón actual**: consulta siempre el caché antes de realizar I/O de base de datos o red y conserva el orden caché → base de datos → proveedor externo.

**Restricción**: la búsqueda interactiva no persiste automáticamente resultados del scraper. La carga continúa siendo una responsabilidad separada del pipeline.

## 14) Caché como puerto sustituible

`src/core/services/cache/` define el protocolo asíncrono `Cache` con operaciones para leer, escribir, eliminar una clave e invalidar un prefijo. Los casos de uso dependen de este protocolo y FastAPI obtiene el proveedor mediante `get_cache`.

```text
cards application
       ↓ depends on
Cache protocol
       ↑ implemented by
InMemoryCache / futuro Redis o Valkey
```

`InMemoryCache` es el proveedor actual para desarrollo. Admite TTL e invalidación por prefijo, pero su contenido pertenece a un único proceso y se pierde al reiniciar.

Las lecturas de Cartas y Publicaciones almacenan respuestas serializadas durante cinco minutos. Las mutaciones de Carta actualizan la clave individual e invalidan las listas afectadas para no servir representaciones obsoletas.

**Patrón actual**:

- las claves incluyen recurso, operación y parámetros normalizados;
- un valor vacío también se almacena para evitar repetir búsquedas externas sin resultados;
- los casos de uso trabajan con schemas de respuesta, no con objetos ORM guardados en memoria;
- cambiar a Redis o Valkey requiere sustituir el proveedor, no modificar los casos de uso.

**Restricción**: `delete_prefix` deberá implementarse de forma acotada en el adaptador distribuido; no debe ejecutar una operación bloqueante sobre todo el keyspace.

## 15) Separación de I/O y CPU

El pipeline distingue:

- descarga de red, resuelta con `asyncio` y HTTPX;
- parsing de HTML, delegado a procesos.

```text
Event loop
  ├── network I/O with AsyncClient
  └── run_in_executor
          ↓
      ProcessPoolExecutor
          ↓
      BeautifulSoup parsing
```

El executor:

- se crea de forma lazy;
- se conserva a nivel de módulo;
- usa como máximo el número de CPU disponible;
- se comparte entre transformaciones.

**Patrón actual**: no ejecutes trabajo de parsing pesado directamente en el event loop.

**Patrón en evolución**: falta integrar el cierre del executor con el lifecycle de la aplicación o del proceso que ejecute el pipeline.

## 16) Configuración por responsabilidad

`src/settings/` divide settings de API y base de datos:

```text
settings/
├── api_settings.py
├── db_settings.py
└── __init__.py
```

Cada módulo:

- define una clase `BaseSettings`;
- configura lectura de entorno y `.env`;
- exporta una instancia del settings correspondiente.

**Patrón actual**: una nueva familia de configuración obtiene su propio módulo cuando tiene una responsabilidad distinta.

**Restricción**: `DBSettings` aún no contiene todas las propiedades consumidas por la sesión. El patrón de configuración está definido, pero esa implementación debe completarse antes de copiarla.

## 17) Cómo extender un recurso

Para añadir un recurso dentro de un componente existente:

1. Define `Resource`, `ResourceCreate`, `ResourceUpdate` y `ResourceResponse` en `domain/`.
2. Reexporta los schemas desde `domain/__init__.py`.
3. Define el modelo SQLAlchemy en `repository/models.py`.
4. Crea `ResourceDAO` y su instancia `dao_<resources>`.
5. Reexporta modelo y DAO desde `repository/__init__.py`.
6. Implementa casos de uso en `application/<resource>_cases.py`.
7. Implementa un router delgado en `infrastructure/<resource>_api.py`.
8. Reexporta el router desde `infrastructure/__init__.py` y el componente.
9. Móntalo en `src/api/api.py` con un prefijo de recurso.
10. Añade migración cuando Alembic esté disponible.
11. Añade pruebas según `docs/testing.md`.
12. Actualiza documentación si cambia el modelo mental o la superficie pública.

Para crear un componente completo, aplica el mismo flujo dentro de `src/api/<component>/` y evita importar internals de otro componente. Si dos componentes necesitan una capacidad técnica común, evalúa `src/core/`; si comparten una regla de dominio, define primero cuál componente es su propietario.

## 18) Patrones incompletos y legacy

### 18.1 Eliminación

**Estado**: incompleto.

Los endpoints existentes de Usuarios devuelven el string `"Eliminado"`, mientras el CRUD nuevo de Cartas usa `204 No Content`. Debe definirse un contrato uniforme para el resto de los recursos.

### 18.2 Relaciones de Usuarios y Roles

**Estado**: incompleto.

Las relaciones contienen rutas antiguas o inexistentes, falta el lado de Direcciones y el modelo `Role` no está definido en el componente actual. No copies estas cadenas ni cardinalidades a otros modelos.

### 18.3 Contratos de listas

**Estado**: incompleto.

Aplicación produce `(items, count)` dentro de `Ok`, mientras los endpoints devuelven únicamente `items`. Debe definirse un schema paginado uniforme para exponer el total sin romper el contrato.

### 18.4 Errores genéricos

**Estado**: legacy.

Strings como `"Error"`, excepciones genéricas y capturas silenciosas dificultan diagnóstico y contratos. Los cambios nuevos deben usar errores con intención concreta y conservar información interna sin exponerla al cliente.

## 19) Decisiones de patrones

### DEC-20260720-pragmatic-hexagonal-components

- **Fecha**: 2026-07-20.
- **Contexto**: el proyecto necesita límites claros sin adoptar complejidad corporativa.
- **Decisión**: organizar la API por componentes con capas domain, application, infrastructure y repository, introduciendo abstracciones solo cuando tengan un uso concreto.
- **Impacto**: el código conserva dirección de dependencias y permite funciones/DAOs directos para casos sencillos.
- **Evidencia**: `src/api/users/`, `docs/conventions.md`.
- **Revisión**: reevaluar si la colaboración entre componentes vuelve insuficientes los límites actuales.

### DEC-20260720-generic-dao

- **Fecha**: 2026-07-20.
- **Contexto**: los recursos comparten operaciones CRUD, filtros y estrategias de carga.
- **Decisión**: centralizar esas operaciones en `DAO` y especializar solamente consultas propias del recurso.
- **Impacto**: reduce duplicación, pero el DAO genérico no debe absorber reglas de dominio.
- **Evidencia**: `src/core/db/dao.py`, `src/api/users/repository/dao.py`.
- **Revisión**: reevaluar si el genérico empieza a necesitar condiciones específicas de múltiples componentes.

### DEC-20260720-scraper-etl-boundaries

- **Fecha**: 2026-07-20.
- **Contexto**: scraping, parsing y persistencia tienen ritmos, errores y recursos diferentes.
- **Decisión**: mantener extracción, transformación y carga como etapas separadas, con un protocolo en el límite de persistencia.
- **Impacto**: las etapas pueden probarse y evolucionar de forma independiente, y el pipeline conserva una ruta de extracción futura.
- **Evidencia**: `src/core/services/scraper/`.
- **Revisión**: reevaluar los contratos si el scraper se convierte en un proceso o servicio independiente.

### DEC-20260721-typed-result

- **Fecha**: 2026-07-21.
- **Contexto**: los errores recuperables deben ser visibles en las firmas y manejados antes de cruzar una frontera.
- **Decisión**: implementar `Result[T, E]` dentro de `src/core/`, representar errores recuperables como tipos de dominio y resolverlos exhaustivamente mediante pattern matching y `assert_never`.
- **Impacto**: los casos de uso no lanzan excepciones para flujo esperado y los routers deben traducir todas las variantes antes de responder.
- **Evidencia**: `src/core/result.py`, `src/api/users/domain/errors.py`, `src/api/users/application/`, `src/api/users/infrastructure/`.
- **Revisión**: reevaluar solamente si el type checker elegido no puede verificar exhaustividad o el patrón genera complejidad desproporcionada.

### DEC-20260721-card-listing-cache-aside

- **Fecha**: 2026-07-21.
- **Contexto**: buscar una publicación no debe repetir scraping cuando el dato ya está disponible localmente.
- **Decisión**: resolver búsquedas mediante cache-aside en el orden caché → PostgreSQL → scraper y depender de un protocolo de caché neutral al proveedor.
- **Impacto**: el proveedor actual puede reemplazarse por Redis o Valkey sin cambiar los casos de uso; los resultados externos, incluidos los vacíos, se reutilizan durante el TTL.
- **Evidencia**: `src/api/cards/application/card_listing_cases.py`, `src/core/services/cache/`, `src/core/services/scraper/search.py`.
- **Revisión**: reevaluar TTL, claves e invalidación cuando exista un proveedor distribuido y se conozca el patrón real de uso.

## 20) Referencias

- `src/application.py`: composition root de FastAPI.
- `src/api/api.py`: composición de routers.
- `src/api/users/`: componente de referencia actual.
- `src/api/cards/`: CRUD de Cartas y búsqueda de Publicaciones.
- `src/core/schema/base.py`: modelo Pydantic compartido.
- `src/core/result.py`: resultado tipado para errores recuperables.
- `src/core/db/model.py`: base declarativa y mixins.
- `src/core/db/dao.py`: DAO genérico, filtros y carga.
- `src/core/db/deps.py`: alcance de sesiones.
- `src/core/utils/filters.py`: objetos de filtros.
- `src/core/utils/utils.py`: sentinels y utilidades compartidas.
- `src/core/services/scraper/`: pipeline ETL.
- `src/core/services/cache/`: puerto y proveedor temporal de caché.
- `docs/conventions.md`: reglas normativas.
- `docs/tech_context.md`: stack y restricciones técnicas.
- `docs/testing.md`: estrategia de pruebas.

## 21) Glosario

- **Adaptador**: implementación que conecta una capacidad del sistema con una tecnología o interfaz concreta.
- **Composition root**: lugar donde se crean y conectan las partes principales de la aplicación.
- **ETL**: secuencia de extracción, transformación y carga de datos.
- **Puerto**: contrato que expresa una capacidad necesaria sin fijar su implementación.
- **Result**: unión `Ok[T] | Err[E]` que hace explícito un éxito o error recuperable.
- **Recurso**: entidad o concepto expuesto mediante operaciones propias dentro de un componente.
- **Sentinel**: valor especial que representa un estado como ausencia sin confundirse con datos ordinarios.
- **Upsert**: inserción que actualiza el registro existente cuando ocurre un conflicto de identidad.

## 22) Checklist de actualización

- [ ] ¿La estructura descrita coincide con los componentes actuales?
- [ ] ¿Los flujos entre router, aplicación y DAO siguen siendo correctos?
- [ ] ¿Los schemas conservan la separación entre creación, actualización y respuesta?
- [ ] ¿Cada `Result` usa errores de dominio concretos y se resuelve exhaustivamente?
- [ ] ¿Cambió la representación de ausencia del DAO?
- [ ] ¿La paginación tiene ya un contrato estable?
- [ ] ¿Las relaciones SQLAlchemy pendientes fueron corregidas?
- [ ] ¿Cambió alguna etapa o límite del scraper?
- [ ] ¿Las claves, TTL e invalidación del caché siguen siendo coherentes?
- [ ] ¿Se añadió un patrón que necesita ejemplo, decisión o clasificación?
- [ ] ¿Un patrón en evolución puede reclasificarse como actual o legacy?
