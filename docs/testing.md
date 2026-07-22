# Free Win - Guía de pruebas

## 1) Propósito

Este documento define la estrategia de pruebas del backend de Free Win. Su objetivo es proporcionar confianza sobre el dominio, la API, la persistencia y el scraper sin depender de servicios externos ni de datos reales de la comunidad.

La estrategia debe crecer junto con el proyecto. Las reglas de esta guía distinguen las pruebas que existen actualmente de las expectativas para funcionalidad nueva.

## 2) Alcance

Este documento cubre:

- principios generales de pruebas;
- estado actual de la suite;
- pruebas unitarias, de API, persistencia y scraper;
- código asíncrono con pytest y AnyIO;
- fixtures, fakes y reemplazo de dependencias;
- pruebas manuales y protección de datos sensibles;
- criterios para cambios nuevos.

Este documento no cubre:

- pruebas de carga o capacidad todavía no requeridas;
- monitoreo en producción;
- QA de un frontend futuro;
- convenciones generales de implementación, definidas en `docs/conventions.md`.

## 3) Estado actual

### 3.1 Cobertura existente

La suite actual contiene:

- `tests/test_imports.py`: comprueba que la aplicación FastAPI pueda importarse;
- `tests/test_scraper_transformers.py`: comprueba la transformación de una página HTML local en una publicación;
- `tests/test_scraper_loader.py`: comprueba la normalización previa a la carga y el comportamiento de lotes vacíos.
- `tests/test_cache.py`: comprueba la invalidación por prefijo del caché en memoria;
- `tests/test_valkey_cache.py`: comprueba namespace, TTL, lectura, invalidación por lotes y cierre usando un cliente falso;
- `tests/test_card_listing_search.py`: comprueba el fallback base de datos → scraper y la reutilización del resultado cacheado;
- `tests/test_card_cases.py`: comprueba el error recuperable al consultar una Carta inexistente;
- `tests/test_result.py`: comprueba las variantes inmutables del resultado tipado.
- `tests/test_order_period_contracts.py` y `tests/test_order_period_rules.py`: comprueban contratos, zonas horarias y estados temporales de Pedidos;
- `tests/test_order_period_cases.py`: comprueba coordinación, transacciones, historial y reglas de modificación de Pedidos;
- `tests/test_order_period_authorization.py` y `tests/test_order_period_api.py`: comprueban permisos, visibilidad y contratos HTTP de Pedidos.

Estas pruebas cubren el arranque mínimo y partes de transformación/carga del scraper. Todavía no existe cobertura automatizada para:

- endpoints de Usuarios, Direcciones o Roles;
- casos de uso del componente `users`;
- DAO genérico y DAOs específicos;
- integración real con PostgreSQL;
- configuración de entorno;
- extracción HTTP del scraper;
- endpoints HTTP de `cards` y el componente `collections`;
- integración PostgreSQL de `order_periods` y sus migraciones.

### 3.2 Patrón async actual

Las pruebas actuales ejecutan coroutines mediante `asyncio.run`. Este patrón se conserva como comportamiento existente, pero las nuevas pruebas asíncronas deben usar AnyIO para compartir correctamente el event loop entre FastAPI, HTTPX y SQLAlchemy.

pytest está declarado en `pyproject.toml`. Los plugins adicionales deben declararse explícitamente antes de depender de ellos en la suite.

## 4) Principios de pruebas

### 4.1 Confianza por capas

La estrategia sigue capas con responsabilidades diferentes:

1. **Pruebas unitarias**: validan funciones y reglas aisladas.
2. **Pruebas de aplicación**: validan coordinación entre casos de uso y DAOs falsos.
3. **Pruebas de API**: validan contratos HTTP con la aplicación ASGI.
4. **Pruebas de persistencia**: validan SQLAlchemy y comportamiento específico de PostgreSQL.
5. **Pruebas manuales**: cubren temporalmente integraciones que no puedan automatizarse de forma razonable.

Una prueba de nivel superior no reemplaza necesariamente una prueba unitaria cuando la regla puede comprobarse de forma más simple y precisa.

### 4.2 Determinismo

- **Required** las pruebas no dependen del orden de ejecución.
- **Required** las pruebas unitarias no acceden a internet.
- **Required** usa HTML, respuestas y datos locales controlados.
- **Required** restaura cualquier dependencia, variable o estado global modificado.
- **Recommended** evita aserciones dependientes del reloj sin controlar el tiempo.
- **Recommended** usa datos pequeños que expresen claramente el escenario.

### 4.3 Comportamiento observable

- **Required** prueba resultados y efectos observables, no detalles internos irrelevantes.
- **Required** una prueba de endpoint comprueba al menos código de estado y cuerpo de respuesta.
- **Required** una prueba de persistencia comprueba los datos guardados o recuperados.
- **Required** una prueba de error comprueba el contrato expuesto, no solo que “algo falló”.
- **Recommended** prueba funciones privadas directamente solamente cuando contengan lógica aislada importante y la alternativa resulte innecesariamente compleja.

### 4.4 Regresiones

- **Required** una corrección de error debe incluir una prueba que reproduzca el fallo cuando sea razonable.
- **Recommended** escribe primero el escenario que falla y luego implementa la corrección.
- **Required** no reduzcas una aserción únicamente para hacer pasar una prueba si eso oculta el comportamiento esperado.

## 5) Convenciones de pytest y AnyIO

### 5.1 Nombres y estructura

- **Required** los archivos usan el patrón `test_<area>.py`.
- **Required** las funciones usan el patrón `test_<comportamiento_esperado>`.
- **Recommended** expresa escenario y resultado en el nombre, por ejemplo `test_load_scraped_data_skips_empty_batches`.
- **Recommended** agrupa pruebas por recurso o unidad, no por una numeración artificial.
- **Recommended** sigue Arrange, Act, Assert mediante separación visual cuando la prueba tenga varias etapas.

### 5.2 Backend asíncrono

Las pruebas async nuevas deben usar `pytest.mark.anyio` y restringirse a `asyncio`, porque FastAPI, SQLAlchemy async y el código del proyecto utilizan ese backend.

```python
import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_async_behavior() -> None:
    result = await async_operation()

    assert result is not None
```

- **Required** no mezcles distintos event loops dentro de una misma prueba.
- **Recommended** evita `asyncio.run` en pruebas nuevas que compartan clientes, sesiones o fixtures async.
- **Required** no ejecutes la suite también con Trio salvo que el proyecto adopte y soporte explícitamente ese backend.

## 6) Pruebas por área

### 6.1 Dominio y schemas

Objetivos:

- comprobar campos obligatorios y opcionales;
- comprobar aliases y serialización común;
- comprobar enums y validadores;
- comprobar que schemas de respuesta no expongan datos sensibles.

Casos mínimos para un schema nuevo:

- entrada válida;
- ausencia de un campo requerido;
- valor inválido para cada restricción relevante;
- serialización esperada cuando existan aliases o tipos especiales.

### 6.2 Casos de uso

Los casos de uso deben probarse sin una base real cuando la regla pueda aislarse mediante un fake o stub del DAO.

Objetivos:

- comprobar parámetros enviados a persistencia;
- comprobar el valor `Ok` en operaciones exitosas;
- comprobar el valor `Err` en fallos esperados;
- comprobar cada tipo de error recuperable declarado por el caso de uso;
- comprobar que la infraestructura traduzca cada `Err` al código y payload HTTP esperados;
- comprobar paginación, filtros y ordenamiento coordinados por aplicación;
- comprobar que no se confunda un resultado vacío con un error inesperado.

Evita mockear cada llamada interna. El fake debe representar el límite que el caso de uso consume.

Un error nuevo debe hacer fallar el manejo exhaustivo mediante `assert_never` durante el análisis estático y debe añadir una prueba de su traducción. No uses `unwrap` en pruebas de aplicación si esto oculta la variante que se está comprobando.

### 6.3 Endpoints FastAPI

Las pruebas HTTP deben usar `httpx.AsyncClient` con `ASGITransport` sobre la aplicación real.

```python
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from src.application import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
```

Por endpoint, comprueba según corresponda:

- operación exitosa;
- input inválido;
- recurso inexistente;
- conflicto de persistencia;
- código de estado;
- schema y campos del cuerpo;
- ausencia de campos sensibles.

No uses un servidor real para estas pruebas. El transporte ASGI invoca la aplicación dentro del proceso.

### 6.4 Dependencias FastAPI

Usa `app.dependency_overrides` para sustituir dependencias de frontera como `get_db`, autenticación o clientes externos.

```python
import pytest

from src.application import app
from src.core.db import get_db


async def fake_db():
    yield FakeSession()


@pytest.fixture
def override_db():
    app.dependency_overrides[get_db] = fake_db
    yield
    app.dependency_overrides.clear()
```

- **Required** limpia los overrides después de cada prueba.
- **Recommended** sustituye la dependencia pública en lugar de hacer monkeypatch a detalles internos.
- **Required** un fake no debe conectarse accidentalmente a servicios reales.

### 6.5 DAO y PostgreSQL

Las pruebas del DAO validan comportamiento de consultas y persistencia que no puede garantizarse mediante un fake.

Casos importantes:

- creación y recuperación;
- actualización parcial;
- eliminación;
- filtros y filtros complejos;
- ordenamiento y paginación;
- relaciones y estrategias de carga;
- conflictos de claves únicas o foráneas;
- rollback después de un fallo.

El código utiliza características específicas de PostgreSQL, como `asyncpg`, tipos del dialecto y `ON CONFLICT`. Por ello:

- **Required** las pruebas de integración fieles usan una base PostgreSQL exclusiva para pruebas.
- **Required** nunca ejecutes pruebas destructivas contra una base de desarrollo compartida o producción.
- **Required** cada prueba debe aislar sus datos mediante transacción, rollback, esquema temporal o limpieza explícita.
- **Recommended** no uses SQLite como sustituto silencioso cuando el comportamiento probado dependa de PostgreSQL.

### 6.6 Scraper

El scraper necesita pruebas por etapa.

**Extracción**:

- URL codificada correctamente;
- respuesta exitosa;
- respuesta 404;
- otros errores HTTP;
- timeout o error de red;
- límite de concurrencia cuando se modifique esa lógica.

**Transformación**:

- estructura HTML principal;
- selectores alternativos;
- HTML vacío o inesperado;
- publicación sin precio o código;
- rareza, condición y stock ausentes;
- deduplicación;
- varias cartas y páginas inexistentes.

**Carga**:

- conversión de precio a `Decimal`;
- precio `N/A`;
- lote vacío;
- cantidad reportada como cargada;
- upsert por código y condición;
- actualización de una publicación existente.

- **Required** las pruebas unitarias del scraper usan HTML local y clientes falsos; nunca dependen de CoolStuffInc.
- **Recommended** prueba directamente el parser síncrono cuando el objetivo sea la interpretación del HTML, evitando crear procesos sin necesidad.
- **Recommended** reserva pruebas del `ProcessPoolExecutor` para comprobar la integración del transformador async.

### 6.7 Configuración

Las pruebas de settings deben comprobar:

- variables requeridas;
- valores válidos e inválidos;
- carga desde entorno controlado;
- defaults cuando existan;
- que secretos no aparezcan en representaciones o errores.

Las pruebas que modifiquen variables de entorno deben usar mecanismos temporales de pytest y restaurar el estado al finalizar.

### 6.8 Caché y búsqueda de publicaciones

Comprueba por separado:

- hit de caché sin acceso posterior a base de datos o red;
- miss de caché con resultados de PostgreSQL;
- miss de caché y PostgreSQL con fallback al scraper;
- almacenamiento de resultados externos y de listas vacías;
- normalización de la consulta usada en la clave;
- expiración e invalidación de claves;
- que los tests nunca contacten Redis, Valkey ni el sitio externo sin una integración explícita.

Usa `InMemoryCache` o un fake del protocolo `Cache` en pruebas de aplicación. Las pruebas unitarias de `ValkeyCache` usan un cliente falso y nunca abren sockets. Una futura prueba de integración deberá usar una instancia Valkey desechable y no reemplaza las pruebas del orden de resolución del caso de uso.

## 7) Fixtures, fakes y datos

### 7.1 Ubicación

- **Recommended** mantiene fixtures locales dentro del archivo mientras solo las use ese conjunto de pruebas.
- **Recommended** mueve fixtures compartidas a `tests/conftest.py` cuando las consuman varias áreas.
- **Recommended** coloca HTML o payloads extensos en `tests/fixtures/` cuando mejore su lectura y reutilización.
- **Required** evita crear una carpeta de helpers genéricos sin consumidores claros.

### 7.2 Fakes frente a mocks

- **Recommended** usa fakes pequeños para DAOs, stores y clientes con comportamiento estable.
- **Recommended** usa mocks cuando sea importante verificar llamadas, parámetros o cantidad de invocaciones.
- **Required** configura únicamente el comportamiento necesario para el escenario.
- **Required** no reproduzcas toda la implementación real dentro de un fake.

### 7.3 Datos de prueba

- **Required** usa Usuarios, direcciones, cartas y precios sintéticos.
- **Required** no copies información personal real de la comunidad.
- **Recommended** usa cartas reconocibles en ejemplos cuando ayuden a leer la prueba, sin depender de su precio o disponibilidad real.
- **Required** controla moneda, zona horaria y fechas en escenarios donde afecten el resultado.

## 8) Red y servicios externos

- **Required** la suite predeterminada no realiza solicitudes externas.
- **Required** reemplaza HTTPX en el límite del cliente o usa un transporte falso.
- **Required** no pruebes el parser descargando HTML vivo; conserva una muestra local sanitizada.
- **Recommended** una comprobación manual contra un sitio externo debe ser explícita y separada de pytest.
- **Required** respeta límites del sitio y no usa pruebas como herramienta de carga.

Las respuestas externas cambian sin aviso. Una prueba basada en la red sería lenta, frágil y no permitiría distinguir una regresión del proyecto de un cambio del proveedor de datos.

## 9) Pruebas manuales

La validación manual es aceptable temporalmente cuando una integración no pueda automatizarse todavía, pero no reemplaza pruebas razonables para reglas deterministas.

Usa esta plantilla:

```md
### Caso manual: <nombre>

- **Área**: <API, persistencia, scraper>.
- **Entorno**: <local o prueba>.
- **Precondiciones**:
  - <configuración necesaria>.
- **Pasos**:
  1. <paso>.
  2. <paso>.
- **Resultado esperado**: <comportamiento>.
- **Resultado observado**: <comportamiento>.
- **Evidencia**: <respuesta o captura sanitizada>.
- **Riesgo restante**: <qué no se comprobó>.
- **Automatización futura**: <prueba candidata>.
```

La evidencia debe ser reproducible y no puede contener credenciales ni datos personales.

## 10) Seguridad y aislamiento

- **Required** no incluyas contraseñas, tokens, DSN reales ni archivos `.env` en pruebas.
- **Required** no uses credenciales ni bases de producción.
- **Required** sanitiza logs, respuestas y capturas antes de conservarlos.
- **Required** las pruebas no envían mensajes, correos ni notificaciones reales.
- **Required** los procesos y conexiones abiertos por una prueba deben cerrarse.
- **Recommended** usa nombres de base que hagan evidente su propósito de prueba.

## 11) Comandos y flujo de trabajo

Cuando las dependencias de desarrollo estén declaradas e instaladas mediante PDM:

```bash
pdm run pytest
```

Para un archivo específico:

```bash
pdm run pytest tests/test_scraper_loader.py
```

Para un escenario específico:

```bash
pdm run pytest tests/test_scraper_loader.py::test_load_scraped_data_skips_empty_batches
```

Flujo recomendado:

1. Ejecuta la prueba o archivo relacionado mientras implementas.
2. Ejecuta todas las pruebas unitarias.
3. Ejecuta integraciones PostgreSQL cuando el cambio afecte modelos, DAOs o migraciones.
4. Registra validación manual solamente para riesgos que no puedan automatizarse todavía.
5. Comunica claramente cualquier prueba no ejecutada y el motivo.

## 12) Expectativas por tipo de cambio

### 12.1 Endpoint nuevo o modificado

- respuesta exitosa;
- validación de entrada;
- recurso inexistente;
- errores esperados;
- código de estado y schema;
- override de dependencias externas.

### 12.2 Regla de Pedido u Orden

- estados iniciales;
- transiciones válidas;
- transiciones rechazadas;
- procesamiento parcial;
- permisos cuando estén definidos;
- trazabilidad del cambio.

### 12.3 Modelo, DAO o migración

- escritura y lectura en PostgreSQL;
- restricciones y relaciones;
- comportamiento nulo/no nulo;
- rollback y conflictos;
- migración hacia adelante y reversión cuando sea posible.

### 12.4 Autorización, Roles o Permisos

- matriz de permisos de `Admin` y `User`;
- decisiones puras de permiso general y propiedad;
- `401` sin identidad, `403` sin permiso y ocultación `404` para recursos ajenos;
- filtrado de colecciones por propietario;
- rechazo de `roleId` durante el registro y ausencia de contraseña en respuestas;
- inmutabilidad de `Admin` y `User`;
- CRUD y reemplazo completo de permisos para roles personalizados;
- bootstrap idempotente y promoción administrativa;
- `dependency_overrides` para sustituir `get_current_user` en pruebas HTTP.
- fakes de DAO para demostrar que los casos de uso coordinan reglas y transacciones sin ejecutar consultas directamente.

### 12.4 Scraper

- etapa específica modificada;
- entrada vacía o incompleta;
- cambio de estructura HTML;
- error de red cuando afecte extracción;
- deduplicación o upsert cuando afecte identidad de datos.

### 12.5 Corrección de error

- prueba de regresión que falle con el comportamiento anterior;
- prueba de casos cercanos cuando compartan la misma causa;
- ausencia de cambios innecesarios en contratos no relacionados.

## 13) Cobertura y calidad

El proyecto no define por ahora un porcentaje mínimo de cobertura. La calidad no se evalúa únicamente por cantidad de líneas ejecutadas.

Se espera que:

- toda regla de dominio nueva tenga pruebas;
- las ramas de error relevantes estén cubiertas;
- los contratos HTTP importantes se prueben desde la frontera;
- el scraper tenga fixtures para estructuras conocidas y degradadas;
- los cambios PostgreSQL se validen contra PostgreSQL;
- una exclusión de pruebas se explique de forma concreta.

La cobertura numérica podrá adoptarse cuando la suite tenga una base más amplia y el porcentaje ayude a detectar regresiones reales.

## 14) Decisiones de pruebas

### DEC-20260720-anyio-asyncio

- **Fecha**: 2026-07-20.
- **Contexto**: FastAPI y SQLAlchemy necesitan compartir un event loop coherente en pruebas async.
- **Decisión**: las pruebas async nuevas usan `pytest.mark.anyio` con backend `asyncio`.
- **Impacto**: no se duplica la suite bajo Trio y se evitan loops creados manualmente alrededor de fixtures async.
- **Evidencia**: `ideas.md`, `src/application.py`, `src/core/db/`.
- **Revisión**: reconsiderar si el proyecto adopta otro backend asíncrono.

### DEC-20260720-postgresql-integration-tests

- **Fecha**: 2026-07-20.
- **Contexto**: la persistencia usa asyncpg y operaciones específicas del dialecto PostgreSQL.
- **Decisión**: las integraciones de persistencia se validan con PostgreSQL y no con SQLite como sustituto implícito.
- **Impacto**: las pruebas de integración requieren una base desechable, pero reflejan el comportamiento real.
- **Evidencia**: `src/core/db/`, `src/core/services/scraper/loader.py`.
- **Revisión**: reconsiderar si se abstraen o eliminan todas las dependencias específicas del dialecto.

## 15) Referencias

- `tests/test_imports.py`: importación mínima de la aplicación.
- `tests/test_scraper_transformers.py`: integración async de transformación.
- `tests/test_scraper_loader.py`: normalización y carga con store falso.
- `src/application.py`: aplicación usada por el transporte ASGI.
- `src/core/db/deps.py`: dependencia de sesión reemplazable.
- `src/core/db/dao.py`: comportamiento genérico de persistencia.
- `src/core/result.py`: unión tipada para errores recuperables.
- `src/core/services/cache/`: contrato y proveedor temporal de caché.
- `src/core/services/scraper/`: etapas del pipeline.
- `docs/conventions.md`: convenciones de implementación.
- `docs/formatting.md`: formato de documentación y decisiones.

## 16) Glosario

- **ASGITransport**: transporte de HTTPX que invoca una aplicación ASGI sin levantar un servidor real.
- **Fake**: implementación simplificada y funcional de una dependencia usada en pruebas.
- **Fixture**: preparación reutilizable de datos o dependencias para una prueba.
- **Integración**: prueba que valida la colaboración con infraestructura real, como PostgreSQL.
- **Mock**: sustituto configurable que permite controlar y verificar interacciones.
- **Prueba de regresión**: prueba que reproduce un error para impedir que reaparezca.

## 17) Checklist de actualización

- [ ] ¿La guía distingue cobertura actual de expectativas futuras?
- [ ] ¿Las dependencias y comandos de pruebas coinciden con `pyproject.toml`?
- [ ] ¿Las pruebas async comparten el backend `asyncio`?
- [ ] ¿Las pruebas de API usan ASGITransport y limpian overrides?
- [ ] ¿Las integraciones usan una base PostgreSQL exclusiva para pruebas?
- [ ] ¿Las pruebas del scraper evitan internet?
- [ ] ¿Los datos y evidencias están sanitizados?
- [ ] ¿Los cambios nuevos incluyen escenarios exitosos y de error relevantes?
- [ ] ¿Las pruebas no ejecutadas se comunican claramente?
