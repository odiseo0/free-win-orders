# Free Win - Documentación general

## 1) Propósito

Free Win es una aplicación comunitaria para jugadores de Yu-Gi-Oh! que facilita la compra de cartas difíciles de conseguir en el país. Este documento ofrece una visión funcional y técnica de alto nivel para entender el propósito del backend, su vocabulario, su estado actual y la ubicación de sus partes principales.

Free Win no es un producto corporativo. Las decisiones del proyecto deben priorizar la utilidad para los jugadores y la reducción del trabajo manual de sus administradores, manteniendo una solución sencilla y sostenible.

## 2) Alcance

Este documento cubre:

- el problema que resuelve Free Win;
- los conceptos principales del dominio;
- el flujo previsto de Pedidos y Órdenes;
- la arquitectura general del backend;
- el estado actual de la API y del scraper;
- una guía rápida para navegar el repositorio.

Este documento no cubre:

- reglas detalladas de implementación, definidas en `docs/conventions.md`;
- patrones técnicos en profundidad, reservados para `docs/system_patterns.md`;
- configuración y dependencias en detalle, reservadas para `docs/tech_context.md`;
- estrategia y herramientas de pruebas, reservadas para `docs/testing.md`;
- reglas de formato documental, definidas en `docs/formatting.md`.

## 3) Contexto del proyecto

Comprar cartas de Yu-Gi-Oh! que no están disponibles localmente requiere agrupar solicitudes, buscarlas en tiendas externas y coordinar su compra y entrega. Este proceso no ocurre de forma inmediata: Free Win abre períodos durante los cuales los jugadores envían las cartas que desean y los administradores revisan cada solicitud.

La aplicación busca centralizar ese trabajo. En lugar de depender exclusivamente de archivos de Excel y seguimiento manual, el backend debe permitir crear Pedidos, recibir Órdenes, consultar cartas y mantener la trazabilidad de lo ocurrido.

El proyecto tiene dos núcleos complementarios:

- **Núcleo funcional**: gestión de Pedidos y Órdenes.
- **Núcleo técnico**: pipeline de scraping para localizar cartas, transformar resultados y almacenarlos.

## 4) Conceptos del dominio

### 4.1 Pedido

Un Pedido es un período abierto por los administradores de Free Win. Mientras permanece abierto, los jugadores pueden enviar las cartas que desean comprar.

Un Pedido:

- puede permanecer abierto durante días o semanas;
- agrupa solicitudes de varias personas;
- no representa una compra individual;
- no implica que las cartas se compren inmediatamente después de ser solicitadas.

### 4.2 Orden

Una Orden es el envío individual de un usuario dentro de un Pedido. Es comparable a una solicitud que necesita revisión humana antes de considerarse procesada.

Una Orden puede:

- ser tomada por un administrador;
- ser aceptada o rechazada;
- procesarse parcialmente cuando solo algunas cartas estén disponibles;
- cambiar de estado a medida que avanza la gestión.

El nombre **Orden** todavía es provisional. Debe usarse de forma consistente mientras no se adopte otro término, pero no debe tratarse como una decisión irreversible del dominio.

### 4.3 Usuario

Un Usuario representa a una persona que interactúa con Free Win. El componente actual contempla información de identidad, contacto, rol y direcciones.

### 4.4 Dirección de usuario

Una Dirección de usuario representa un lugar asociado con un Usuario y puede utilizarse en futuros flujos de entrega. El modelo contempla nombre, ubicación geográfica, estado, ciudad, dirección y código postal.

### 4.5 Rol de usuario

Un Rol de usuario vincula al Usuario con sus permisos o responsabilidades. La definición completa de roles, permisos y transiciones administrativas todavía está pendiente.

### 4.6 Carta y publicación

Una Carta contiene los metadatos descriptivos y relativamente estáticos del artículo que el jugador desea localizar. Una Publicación de carta (`CardListing`) es el producto consultable: representa una edición y condición concretas con precio y stock.

Una misma carta puede tener múltiples publicaciones porque el set, la condición, el precio o la disponibilidad pueden variar.

## 5) Flujo funcional previsto

El flujo mínimo previsto de Free Win es:

```text
Administrador abre un Pedido
        ↓
Usuarios preparan y envían sus Órdenes
        ↓
Se consultan cartas, publicaciones y disponibilidad
        ↓
Administrador toma y revisa cada Orden
        ↓
Administrador registra aceptación, rechazo o resultado parcial
        ↓
La Orden conserva trazabilidad hasta su cierre y entrega
```

Este flujo describe la dirección funcional del producto. No implica que todas sus etapas estén implementadas actualmente.

## 6) Estado actual

### 6.1 Comportamiento implementado

El repositorio contiene actualmente:

- una aplicación FastAPI creada en `src/application.py`;
- ensamblaje central de routers en `src/api/api.py`;
- endpoints CRUD para Usuarios, Direcciones de usuario y Roles de usuario;
- endpoints CRUD para Cartas;
- endpoints de lectura y búsqueda para Publicaciones de cartas;
- una sesión asíncrona de SQLAlchemy para PostgreSQL;
- un DAO genérico con operaciones de consulta y persistencia;
- un pipeline de scraping con etapas de extracción, transformación y carga;
- un contrato de caché sustituible con implementaciones en memoria y Valkey;
- configuración separada para API, caché y base de datos.

La superficie HTTP registrada actualmente incluye:

| Recurso | Prefijo | Operaciones actuales |
| --- | --- | --- |
| Usuarios | `/users` | listar, obtener, crear, actualizar y eliminar |
| Direcciones | `/user-addresses` | listar, obtener, crear, actualizar y eliminar |
| Roles de usuario | `/user-roles` | listar, obtener, crear, actualizar y eliminar |
| Cartas | `/cards` | listar, obtener, crear, actualizar y eliminar |
| Publicaciones | `/card-listings` | listar, obtener y buscar |

La raíz `/` devuelve un mensaje de bienvenida.

### 6.2 Estructura preparada pero incompleta

Los componentes `collections` y `orders` ya existen dentro de `src/api/`, pero sus capas todavía no contienen una implementación funcional completa. Su presencia define una dirección de organización, no una API disponible.

También están pendientes de definición o finalización:

- estados y transiciones de Pedidos y Órdenes;
- permisos administrativos y catálogo de roles;
- representación de resultados parciales por carta;
- persistencia coordinada de resultados obtenidos por búsqueda;
- entorno Valkey disponible para validar la integración distribuida;
- migraciones Alembic del esquema actual;
- contrato uniforme de errores HTTP.

## 7) Arquitectura general

### 7.1 Organización del backend

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

- `src/application.py` crea la aplicación FastAPI, configura middleware y monta el router principal.
- `src/api/` agrupa los componentes funcionales.
- `src/core/` contiene capacidades compartidas, como base de datos, schemas base, servicios y utilidades.
- `src/settings/` concentra la configuración del proceso.

### 7.2 Arquitectura por componente

Cada componente de la API sigue una arquitectura hexagonal pragmática:

```text
<component>/
├── domain/          # Schemas y conceptos del componente
├── application/     # Casos de uso
├── infrastructure/  # Adaptadores HTTP
└── repository/      # Modelos SQLAlchemy y DAOs
```

La intención de esta separación es mantener las reglas y operaciones del componente independientes de FastAPI y de los detalles de persistencia, sin introducir abstracciones que el proyecto todavía no necesita.

## 8) Ciclo de una solicitud HTTP

Una solicitud CRUD del componente `users` sigue este recorrido general:

```text
Cliente HTTP
    ↓
Router de FastAPI
    ↓
Dependencia get_db
    ↓
Caso de uso de aplicación
    ↓
DAO del recurso
    ↓
SQLAlchemy AsyncSession / PostgreSQL
    ↓
Validación y serialización de respuesta
```

Paso a paso:

1. `src/api/api.py` dirige la solicitud al router del recurso.
2. El endpoint recibe parámetros o un schema Pydantic.
3. FastAPI proporciona una `AsyncSession` mediante `get_db`.
4. El endpoint delega la operación al caso de uso.
5. El caso de uso invoca el DAO específico.
6. El DAO construye y ejecuta la operación SQLAlchemy.
7. El resultado vuelve a la frontera HTTP para formar la respuesta.

Los detalles y reglas de esta interacción se documentan en `docs/conventions.md` y, progresivamente, en `docs/system_patterns.md`.

## 9) Pipeline de scraping

El scraper se encuentra en `src/core/services/scraper/` y está diseñado como un pipeline separable del resto de la API.

### 9.1 Extracción

`scraper.py` recibe nombres de cartas, construye las rutas de consulta y obtiene las páginas de forma asíncrona. La concurrencia está limitada mediante un semáforo y las solicitudes externas tienen timeout.

### 9.2 Transformación

`transformers.py` analiza el HTML y produce publicaciones normalizadas. Debido a que el procesamiento de HTML puede consumir CPU, distribuye el trabajo mediante un `ProcessPoolExecutor` reutilizable.

La transformación intenta extraer:

- nombre y set;
- código de la carta;
- precio;
- rareza;
- condición;
- stock.

También elimina publicaciones duplicadas antes de devolver los resultados.

### 9.3 Carga

`loader.py` convierte los resultados a tipos apropiados para persistencia y realiza un upsert en PostgreSQL. Una publicación se identifica de forma única por la combinación de código y condición.

El pipeline conceptual es:

```text
Nombres de cartas
    ↓
Descarga asíncrona de páginas
    ↓
Transformación de HTML en procesos separados
    ↓
Normalización y deduplicación
    ↓
Upsert de publicaciones en PostgreSQL
```

### 9.4 Búsqueda interactiva

`GET /card-listings/search?query=<nombre>` consulta primero el caché y después PostgreSQL. Solamente cuando ambas fuentes carecen de resultados utiliza las etapas de extracción y transformación del scraper. La respuesta obtenida se guarda en caché durante cinco minutos, incluidos los resultados vacíos.

```text
Caché → PostgreSQL → Scraper → Caché → Usuario
```

La búsqueda no ejecuta automáticamente la carga a PostgreSQL. Esto mantiene separada la respuesta interactiva de la persistencia del pipeline.

Aunque hoy forma parte del backend, sus límites deben permitir separarlo en un servicio independiente si el crecimiento real del proyecto lo justifica.

## 10) Datos y configuración

### 10.1 Persistencia

La persistencia usa SQLAlchemy 2 con `AsyncSession` y PostgreSQL mediante `asyncpg`.

La infraestructura compartida incluye:

- `src/core/db/model.py`: base declarativa, mixin de fechas y convención de restricciones;
- `src/core/db/dao.py`: operaciones CRUD, filtros, ordenamiento y carga de relaciones;
- `src/core/db/session.py`: engine y fábrica de sesiones asíncronas;
- `src/core/db/deps.py`: dependencia `get_db` y context manager para usos fuera de FastAPI.

### 10.2 Configuración

La configuración usa `pydantic-settings` y se divide por responsabilidad:

- `src/settings/api_settings.py`: configuración de la API;
- `src/settings/db_settings.py`: conexión y opciones de PostgreSQL.

Los secretos y valores dependientes del entorno deben permanecer fuera del repositorio.

## 11) Funcionalidades futuras

Las siguientes ideas forman parte de la dirección del producto, pero todavía necesitan diseño y priorización:

- trazabilidad completa de Pedidos y Órdenes;
- Pre-Pedidos;
- mapa de entrega;
- históricos de precios;
- históricos de Pedidos;
- base de datos propia de publicaciones consultable sin scraping continuo.

Esta lista no autoriza a implementar alcance adicional durante una tarea no relacionada.

## 12) Navegación recomendada

Para conocer el proyecto, el orden de lectura recomendado es:

1. `README.md`: resumen y estructura.
2. `AGENTS.md`: contexto del dominio y reglas para agentes.
3. `docs/general_documentation.md`: visión funcional y técnica general.
4. `src/application.py`: creación de FastAPI.
5. `src/api/api.py`: routers disponibles.
6. `src/api/users/`: ejemplo más completo de un componente.
7. `src/core/db/`: persistencia compartida.
8. `src/core/services/scraper/`: pipeline de cartas.
9. `docs/conventions.md`: reglas de implementación.
10. `docs/system_patterns.md`: patrones técnicos detallados a medida que se documenten.

## 13) Referencias

- `README.md`: presentación del repositorio.
- `AGENTS.md`: propósito, vocabulario y criterio de producto.
- `src/application.py`: aplicación FastAPI.
- `src/api/api.py`: routers registrados.
- `src/api/users/`: implementación actual de Usuarios, Direcciones y Roles.
- `src/core/db/`: infraestructura de persistencia.
- `src/core/services/scraper/`: pipeline de scraping.
- `docs/conventions.md`: convenciones de código y diseño.
- `docs/system_patterns.md`: patrones del sistema.
- `docs/tech_context.md`: contexto técnico.

## 14) Glosario

- **Administrador**: persona responsable de abrir Pedidos y revisar Órdenes.
- **Carta**: artículo de Yu-Gi-Oh! que un jugador desea localizar o comprar.
- **Componente**: agrupación funcional dentro de `src/api/`.
- **DAO**: objeto que encapsula operaciones de acceso y persistencia de datos.
- **Orden**: solicitud individual de un Usuario dentro de un Pedido; el nombre todavía es provisional.
- **Pedido**: período durante el cual Free Win recibe Órdenes de los jugadores.
- **Pipeline**: secuencia de extracción, transformación y carga de datos.
- **Publicación**: oferta concreta de una carta con set, código, condición, precio y stock.
- **Usuario**: persona que interactúa con Free Win.

## 15) Decisiones y restricciones actuales

### DEC-20260720-backend-only

- **Fecha**: 2026-07-20.
- **Contexto**: el monorepo inicial añadía estructura para un cliente que todavía no forma parte del trabajo actual.
- **Decisión**: este repositorio contiene exclusivamente el backend de Free Win.
- **Impacto**: cualquier frontend futuro se desarrollará fuera de este repositorio salvo que se revise explícitamente la decisión.
- **Evidencia**: `README.md`, `src/`.
- **Revisión**: reconsiderar solamente si mantener ambos proyectos juntos aporta una ventaja concreta.

### DEC-20260720-scraper-in-backend

- **Fecha**: 2026-07-20.
- **Contexto**: el scraper es necesario para construir rápidamente el flujo de búsqueda y carga de datos.
- **Decisión**: el pipeline permanece en `src/core/services/scraper/`, conservando límites que permitan extraerlo en el futuro.
- **Impacto**: no se crea un microservicio antes de que exista una necesidad operativa real.
- **Evidencia**: `src/core/services/scraper/`.
- **Revisión**: reconsiderar si su despliegue, escalado o ciclo de ejecución necesita independencia del API.

## 16) Checklist de actualización

Actualiza este documento cuando cambie alguno de estos puntos:

- [ ] propósito o alcance general de Free Win;
- [ ] definición de Pedido, Orden, Usuario o Publicación;
- [ ] flujo funcional principal;
- [ ] componentes disponibles o responsabilidades de alto nivel;
- [ ] routers expuestos por la API;
- [ ] etapas o ubicación del scraper;
- [ ] estado real de una funcionalidad descrita como actual o prevista;
- [ ] decisiones o restricciones que alteren el modelo mental del proyecto.
