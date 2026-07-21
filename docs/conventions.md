# Free Win - Convenciones

## 1) Propósito

Este documento define las convenciones de código y diseño para el backend de Free Win.

Sus objetivos son:

- mantener consistencia con los patrones actuales del repositorio;
- facilitar que cada componente evolucione sin romper los límites entre capas;
- distinguir las reglas vigentes de las recomendaciones que todavía pueden evolucionar;
- favorecer código sencillo para un proyecto comunitario, sin introducir complejidad innecesaria.

## 2) Alcance

Este documento cubre:

- organización de módulos y dirección de dependencias;
- nombres y estilo de Python;
- responsabilidades de dominio, aplicación, infraestructura y persistencia;
- convenciones para FastAPI, Pydantic, SQLAlchemy y código asíncrono;
- manejo de errores, configuración, seguridad y comentarios.

Este documento no define:

- reglas funcionales completas de Pedidos y Órdenes;
- la estrategia detallada de pruebas, que corresponde a `docs/testing.md`;
- el formato de la documentación, que corresponde a `docs/formatting.md`;
- decisiones de despliegue todavía no adoptadas.

## 3) Niveles de reglas

Cada convención se identifica con uno de estos niveles:

- **Required**: debe cumplirse en código nuevo.
- **Recommended**: debe seguirse por defecto; una desviación necesita una razón concreta.
- **Legacy**: existe en el código actual, pero no debe extenderse sin revisar antes el patrón.

Si una convención contradice el comportamiento necesario del dominio, debe prevalecer el dominio y documentarse la excepción.

## 4) Organización del código

### 4.1 Responsabilidad de las carpetas

- **Required** `src/application.py` contiene la creación y configuración principal de la aplicación FastAPI.
- **Required** `src/api/` contiene los componentes funcionales y el ensamblaje de sus routers.
- **Required** `src/core/` contiene infraestructura base y capacidades compartidas por varios componentes.
- **Required** `src/settings/` contiene configuración dividida por responsabilidad.
- **Required** `tests/` contiene las pruebas automatizadas.
- **Recommended** evita crear módulos genéricos como `helpers.py`, `common.py` o `misc.py` cuando exista una ubicación de dominio o técnica más concreta.

### 4.2 Estructura de un componente

Los componentes de `src/api/` siguen esta estructura:

```text
<component>/
├── domain/
├── application/
├── infrastructure/
└── repository/
```

- **Required** `domain/` define schemas, conceptos y reglas del componente sin depender de FastAPI ni SQLAlchemy.
- **Required** `application/` coordina casos de uso y depende de interfaces o funciones de dominio/persistencia.
- **Required** `infrastructure/` expone adaptadores de entrada, actualmente routers FastAPI.
- **Required** `repository/` contiene modelos SQLAlchemy, DAOs y detalles de persistencia.
- **Recommended** divide archivos por recurso cuando un componente contiene varias partes relacionadas. El componente `users`, por ejemplo, separa `users`, `user_addresses` y `user_roles`.

### 4.3 Dirección de dependencias

- **Required** el dominio no importa FastAPI, SQLAlchemy ni adaptadores externos.
- **Required** infraestructura delega la operación a la capa de aplicación; no contiene consultas ni reglas de negocio.
- **Required** aplicación no conoce detalles HTTP como `Request`, códigos de estado o `HTTPException`.
- **Required** repository no decide respuestas HTTP ni políticas de presentación.
- **Recommended** mueve algo a `src/core/` solamente cuando lo utiliza más de un componente o forma parte de la infraestructura base.
- **Recommended** evita ciclos de importación; usa `TYPE_CHECKING` y referencias adelantadas cuando la relación entre tipos lo requiera.

## 5) Convenciones de Python

### 5.1 Nombres

- **Required** módulos, funciones, métodos y variables usan `snake_case`.
- **Required** clases y tipos usan `PascalCase`.
- **Required** constantes usan `UPPER_SNAKE_CASE`.
- **Required** nombres internos no públicos comienzan con `_` cuando ocultarlos a consumidores del módulo sea relevante.
- **Required** los identificadores usan inglés en el código; los términos propios del dominio deben conservar un significado consistente.
- **Recommended** usa nombres descriptivos y concretos, como `user_address_id`, `read_user_addresses` y `dao_user_addresses`.
- **Recommended** evita abreviaturas salvo las ampliamente conocidas en el proyecto, como `db`, `dao` o `api`.

### 5.2 Tipos

- **Required** las funciones nuevas declaran tipos para parámetros y retorno.
- **Required** usa sintaxis moderna de Python 3.13: `list[T]`, `dict[K, V]` y `T | None`.
- **Recommended** importa tipos usados únicamente para análisis estático dentro de `if TYPE_CHECKING:`.
- **Recommended** añade `from __future__ import annotations` en módulos con relaciones adelantadas o anotaciones que puedan producir ciclos.
- **Recommended** evita `Any` cuando el tipo real pueda expresarse de forma razonable.

### 5.3 Responsabilidad y legibilidad

- **Required** cada archivo agrupa una preocupación cohesionada.
- **Required** cada función realiza una tarea principal y delega preocupaciones secundarias.
- **Recommended** separa preparación, ejecución y tratamiento del resultado con espacios en blanco cuando mejore la lectura.
- **Recommended** extrae helpers cuando una función mezcle consulta, transformación, validación y efectos externos.
- **Recommended** favorece retornos tempranos frente a bloques condicionales profundamente anidados.

## 6) Dominio y schemas Pydantic

### 6.1 Modelo base

- **Required** los schemas del proyecto heredan de `src.core.schema.BaseModel`.
- **Required** la configuración transversal de Pydantic se centraliza en ese modelo base; no la dupliques en cada schema.
- **Recommended** añade comportamiento global al modelo base únicamente si es válido para todos sus descendientes.

### 6.2 Familia de schemas por recurso

El patrón actual separa el modelo común, la entrada de creación, la entrada de actualización y la respuesta:

```python
class UserAddress(BaseModel):
    name: str | None = None


class UserAddressCreate(UserAddress):
    name: str


class UserAddressUpdate(UserAddress):
    pass


class UserAddressResponse(UserAddress):
    id: int
```

- **Required** `<Resource>Create` declara como obligatorios los campos necesarios para crear el recurso.
- **Required** `<Resource>Update` permite actualizaciones parciales cuando el endpoint use `PATCH`.
- **Required** `<Resource>Response` contiene los campos generados o expuestos solamente en respuestas, como `id`.
- **Recommended** mantén en el schema base los campos compartidos por creación, actualización y respuesta.
- **Recommended** usa tipos, `Field`, enums y validadores de Pydantic para restricciones de entrada que sean reglas del dato.

### 6.3 Validadores

- **Required** un validador de request puede lanzar `ValueError` para que Pydantic lo convierta en un error de validación.
- **Required** los validadores no realizan I/O ni consultan la base de datos.
- **Recommended** usa validadores para restricciones locales del valor; usa dependencias o casos de uso para reglas que necesitan estado externo.

## 7) Capa de aplicación

### 7.1 Casos de uso

- **Required** los casos de uso reciben explícitamente sus dependencias, incluida la sesión de base de datos cuando corresponda.
- **Required** las funciones de aplicación usan nombres orientados a la operación: `get_one`, `get_multi`, `create`, `update` y `remove` para el CRUD actual.
- **Required** la aplicación delega la persistencia al DAO correspondiente.
- **Recommended** usa un alias local `dao` cuando el archivo trabaja con un único DAO y esto mantiene el código claro.
- **Recommended** conserva un archivo de casos de uso por recurso cuando un componente contenga varios recursos.

### 7.2 Resultados y errores

- **Required** los errores recuperables se representan mediante `Result[T, E]`, `Ok[T]` y `Err[E]` desde `src/core/result.py`.
- **Required** `E` es un tipo de error concreto definido por el dominio propietario. No uses `str`, `Any`, `Exception` ni listas vacías como errores.
- **Required** usa `Never` como parámetro de error cuando una operación no tenga una variante recuperable.
- **Required** la infraestructura resuelve cada `Result` mediante pattern matching y traduce errores del dominio al contrato HTTP.
- **Required** usa `assert_never` para que el type checker detecte variantes que no hayan sido manejadas.
- **Required** un endpoint nunca devuelve `Result`, `Ok` o `Err` directamente.
- **Required** no implementes ni uses `unwrap` en código de aplicación; manejar el resultado debe ser visible.
- **Required** no uses excepciones genéricas para control de flujo esperado ni conviertas una excepción desconocida en un `Err` genérico.
- **Recommended** reserva excepciones para fallos inesperados, invariantes rotas o infraestructura que la operación no pueda recuperar.
- **Recommended** captura una excepción técnica solamente en el adaptador que pueda traducirla a un error recuperable específico, preservando su causa para diagnóstico.

## 8) FastAPI y rutas HTTP

### 8.1 Routers

- **Required** cada recurso expone un `APIRouter` desde su módulo de infraestructura.
- **Required** los routers del componente se reexportan desde `infrastructure/__init__.py` y el `__init__.py` del componente.
- **Required** `src/api/api.py` ensambla los routers y define sus prefijos.
- **Required** las funciones de endpoint son delgadas: reciben datos, invocan el caso de uso, resuelven su `Result` y forman la respuesta HTTP.
- **Required** las sesiones se obtienen mediante `Annotated[AsyncSession, Depends(get_db)]`.

### 8.2 Diseño REST

- **Required** las rutas representan recursos y usan sustantivos en plural.
- **Required** usa métodos HTTP según la intención: `GET` para consultar, `POST` para crear, `PATCH` para actualizar parcialmente y `DELETE` para eliminar.
- **Required** los parámetros de ruta usan `snake_case` y el nombre completo del recurso: `{user_id}`, `{user_address_id}` y `{user_role_id}`.
- **Recommended** conserva el mismo nombre de parámetro cuando varias dependencias encadenadas resuelvan el mismo recurso. Esto permite reutilizar validaciones de FastAPI sin adaptadores innecesarios.
- **Recommended** usa rutas anidadas cuando la pertenencia sea parte de la operación, no solo para reflejar relaciones de base de datos.

### 8.3 Contrato y documentación OpenAPI

- **Required** declara el tipo o `response_model` esperado para cada endpoint.
- **Required** usa códigos de estado coherentes con el resultado de la operación.
- **Recommended** añade `summary`, `description` y `responses` cuando el comportamiento no sea evidente o existan respuestas alternativas relevantes.
- **Recommended** devuelve datos que FastAPI pueda validar contra el schema de respuesta; evita construir manualmente un schema Pydantic solo para que FastAPI vuelva a validarlo y serializarlo.
- **Recommended** la disponibilidad de OpenAPI por entorno debe configurarse centralmente si el despliegue futuro requiere ocultarlo; no disperses esta decisión entre routers.

## 9) Persistencia con SQLAlchemy

### 9.1 Modelos

- **Required** los modelos heredan de `MappedAsDataclass`, `Base` y, cuando corresponda, `Date`.
- **Required** las columnas usan anotaciones `Mapped[T]` y `mapped_column` cuando sea necesario declarar opciones explícitas.
- **Required** las claves primarias usan `id`; las claves foráneas usan `<resource>_id`.
- **Required** las relaciones declaran ambos lados con `back_populates` cuando la navegación sea bidireccional.
- **Required** la nulabilidad de la anotación y la columna debe representar la misma regla.
- **Recommended** usa `String(length)` cuando exista un límite conocido y útil para la base de datos.
- **Recommended** reserva `association_proxy` para atributos derivados que eviten exponer detalles innecesarios de una relación.

### 9.2 Nombres de base de datos

- **Required** tablas, columnas, índices y restricciones usan `snake_case`.
- **Required** los nombres de restricciones siguen la convención central definida en `src/core/db/model.py`.
- **Required** las tablas siguen el plural generado por `Base.__tablename__`, salvo una excepción explícita.
- **Required** usa sufijo `_id` para claves foráneas.
- **Required** usa nombres temporales consistentes con los mixins actuales: `date_added` y `date_updated`.
- **Recommended** agrupa tablas relacionadas mediante nombres de dominio claros, sin prefijos redundantes.

### 9.3 DAOs y consultas

- **Required** los DAOs específicos heredan de `DAO[Model, CreateSchema, UpdateSchema]`.
- **Required** cada recurso exporta una instancia con nombre `dao_<resources>`.
- **Recommended** reutiliza las operaciones genéricas antes de añadir un método especializado.
- **Recommended** añade métodos especializados cuando expresen una consulta del dominio o eviten filtrar grandes conjuntos en Python.
- **Recommended** realiza joins, filtros, ordenamiento, paginación y agregaciones simples en SQL.
- **Recommended** deja la validación y serialización del contrato HTTP a Pydantic/FastAPI; no conviertas consultas SQL en una capa de presentación.

### 9.4 Migraciones

- **Required** los cambios persistentes de esquema deben representarse con Alembic cuando su infraestructura esté habilitada.
- **Required** las migraciones deben ser estáticas, descriptivas y reversibles siempre que PostgreSQL lo permita.
- **Required** una migración no debe depender de que la estructura se genere dinámicamente en tiempo de ejecución.
- **Recommended** usa nombres que expliquen el cambio, no nombres genéricos como `changes` o `update`.
- **Recommended** revisa las migraciones autogeneradas antes de incorporarlas.

## 10) Código asíncrono y trabajo diferido

### 10.1 I/O asíncrono

- **Required** las operaciones de base de datos, red y archivos dentro de rutas `async` deben usar APIs asíncronas.
- **Required** no llames directamente SDKs síncronos o funciones bloqueantes desde el event loop.
- **Recommended** si una dependencia síncrona es inevitable y realiza I/O, ejecútala con `starlette.concurrency.run_in_threadpool` en la frontera correspondiente.
- **Recommended** limita explícitamente la concurrencia en operaciones masivas, como hace el scraper.
- **Required** configura timeouts para llamadas externas.

### 10.2 Trabajo intensivo en CPU

- **Required** no trates una operación intensiva en CPU como asíncrona solamente por declararla con `async def`.
- **Required** no uses threads como estrategia principal para trabajo intensivo en CPU.
- **Recommended** delega procesamiento intensivo a otro proceso o a una cola de tareas cuando esa necesidad exista realmente.

### 10.3 Tareas en segundo plano

- **Required** usa `BackgroundTasks` solamente para trabajo corto cuya pérdida no comprometa datos ni procesos importantes.
- **Required** no uses `BackgroundTasks` para operaciones que necesiten reintentos, seguimiento, planificación o garantía de ejecución.
- **Recommended** adopta una cola externa únicamente cuando el proyecto necesite esas garantías; no añadas una por anticipación.

## 11) Configuración y seguridad

### 11.1 Configuración

- **Required** la configuración proviene de `src/settings/` y no se dispersa en constantes locales de infraestructura.
- **Required** separa settings por responsabilidad, como API y base de datos.
- **Required** los secretos se reciben mediante variables de entorno o mecanismos externos; nunca se incluyen en el repositorio.
- **Required** la aplicación debe fallar al iniciar si falta una configuración indispensable.
- **Recommended** los valores por defecto deben ser seguros para desarrollo y no reducir la seguridad de producción.

### 11.2 Datos sensibles

- **Required** contraseñas, tokens, credenciales y datos personales sensibles no se escriben en logs.
- **Required** los schemas de respuesta no exponen contraseñas ni campos internos sensibles.
- **Required** los errores enviados al cliente no revelan consultas, credenciales ni detalles internos de infraestructura.
- **Recommended** limita la recopilación y retención de datos de usuarios a lo necesario para Pedidos y entregas.

## 12) Comentarios y documentación del código

- **Required** los comentarios explican la razón, restricción o efecto no evidente; no repiten la sintaxis.
- **Required** documenta integraciones frágiles, efectos secundarios y decisiones difíciles de inferir.
- **Recommended** usa docstrings en APIs públicas o comportamiento no evidente, no por obligación en cada función trivial.
- **Recommended** un workaround debe indicar el contexto que lo hace necesario y la condición que permitiría retirarlo.

Evita comentarios como:

```python
# Incrementa el contador
count += 1
```

Prefiere explicar una decisión:

```python
# El límite evita saturar el servicio externo durante una carga masiva.
MAX_EXTERNAL_CONCURRENCY = 10
```

## 13) Patrones legacy que no deben ampliarse

- **Legacy** rutas sin un contrato explícito de error o código de estado.
- **Legacy** mensajes genéricos como `"Error"` que no identifican la operación fallida.
- **Legacy** anotaciones de retorno que no coinciden con el valor real de la función.
- **Legacy** cadenas de relaciones SQLAlchemy que apuntan a módulos inexistentes o antiguos.
- **Legacy** mezclar nombres antiguos como `members` con el término actual `users`.

Corrige estos patrones cuando formen parte directa del cambio solicitado y sea posible hacerlo sin alterar reglas de negocio todavía indefinidas. Evita refactorizaciones masivas no relacionadas.

## 14) Referencias

- `src/application.py`: creación de la aplicación FastAPI.
- `src/api/api.py`: ensamblaje de routers.
- `src/api/users/`: ejemplo actual de organización por componente y recurso.
- `src/core/db/model.py`: base declarativa y convención de nombres de SQLAlchemy.
- `src/core/db/dao.py`: operaciones genéricas de persistencia.
- `src/core/schema/base.py`: configuración compartida de Pydantic.
- `src/core/services/scraper/`: concurrencia e I/O externo asíncrono.
- `docs/system_patterns.md`: patrones e interacciones del sistema.
- `docs/testing.md`: estrategia de pruebas.
- `docs/formatting.md`: formato de la documentación.

## 15) Glosario

- **Componente**: agrupación funcional dentro de `src/api/`, como `users` u `orders`.
- **DAO**: objeto que encapsula operaciones de acceso y persistencia de datos.
- **Schema**: modelo Pydantic que define datos de entrada, actualización o respuesta.
- **Router**: grupo de endpoints FastAPI asociados con uno o varios recursos relacionados.
- **Trabajo bloqueante**: operación que ocupa el hilo mientras espera y detiene el progreso del event loop.

## 16) Checklist de actualización

Antes de integrar un cambio:

- [ ] ¿El código está en la capa y el recurso correctos?
- [ ] ¿La dirección de dependencias respeta los límites del componente?
- [ ] ¿Los nombres siguen las convenciones de Python y el vocabulario de Free Win?
- [ ] ¿Los endpoints delegan la lógica a los casos de uso?
- [ ] ¿Los schemas separan correctamente creación, actualización y respuesta?
- [ ] ¿Las operaciones de I/O son asíncronas y tienen límites razonables?
- [ ] ¿Los modelos y DAOs siguen las convenciones de persistencia?
- [ ] ¿Los errores aportan contexto sin filtrar información sensible?
- [ ] ¿Los comentarios explican decisiones en lugar de repetir el código?
- [ ] ¿Una convención nueva o modificada necesita reflejarse en este documento?
