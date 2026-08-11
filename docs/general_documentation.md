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
- el estado actual de la API y su límite con el servicio de búsqueda;
- una guía rápida para navegar el repositorio.

Este documento no cubre:

- reglas detalladas de implementación, definidas en `docs/conventions.md`;
- patrones técnicos en profundidad, reservados para `docs/system_patterns.md`;
- configuración y dependencias en detalle, reservadas para `docs/tech_context.md`;
- estrategia y herramientas de pruebas, reservadas para `docs/testing.md`;
- reglas de formato documental, definidas en `docs/formatting.md`.

## 3) Contexto del proyecto

Comprar cartas de Yu-Gi-Oh! que no están disponibles localmente requiere agrupar solicitudes, buscarlas en tiendas externas y coordinar su compra y entrega. Este proceso no ocurre de forma inmediata: Free Win abre períodos durante los cuales los jugadores envían las cartas que desean y los administradores revisan cada solicitud.

La aplicación busca centralizar ese trabajo. En lugar de depender exclusivamente de archivos de Excel y seguimiento manual, este backend permite crear Pedidos, recibir Órdenes y mantener la trazabilidad de lo ocurrido. La consulta de cartas se realiza mediante `free-win-search`.

El núcleo de este repositorio es la gestión de Pedidos y Órdenes. La búsqueda,
transformación y carga de cartas pertenece a `free-win-search`, desplegado de
forma independiente pero conectado a la misma base PostgreSQL.

## 4) Conceptos del dominio

### 4.1 Pedido

Un Pedido es un período abierto por los administradores de Free Win. Mientras permanece abierto, los jugadores pueden enviar las cartas que desean comprar.

Un Pedido:

- puede permanecer abierto durante días o semanas;
- agrupa solicitudes de varias personas;
- no representa una compra individual;
- no implica que las cartas se compren inmediatamente después de ser solicitadas.

En código y API se representa como `OrderPeriod`; cada envío individual se
representa como `OrderRequest`. Su estado se deriva de la ventana temporal:

- `draft` antes de la apertura;
- `open` desde la apertura y hasta antes del cierre;
- `closed` al alcanzar el cierre.

Los administradores pueden modificar libremente nombre y fechas mientras está
en Borrador. Una vez abierto solo pueden adelantar o extender un cierre que siga
en el futuro. Un Pedido cerrado no puede reabrirse ni eliminarse. El cierre
impide nuevas Órdenes, pero no detiene la revisión de las ya recibidas.

### 4.2 Orden

Una Orden es el envío individual de un usuario dentro de un Pedido. Es comparable a una solicitud que necesita revisión humana antes de considerarse procesada.

Una Orden puede:

- ser tomada por un administrador;
- ser aceptada o rechazada;
- procesarse parcialmente cuando solo algunas cartas estén disponibles;
- cambiar de estado a medida que avanza la gestión.

El nombre **Orden** todavía es provisional. Debe usarse de forma consistente mientras no se adopte otro término, pero no debe tratarse como una decisión irreversible del dominio.

La primera versión implementada permite crear, consultar y editar la Orden,
administrar sus ítems y precios, consultar su historial y recorrer los estados
`submitted`, `in_review`, `accepted`, `rejected` y `cancelled`. El documento
`docs/orderRequestIdea.md` conserva el diseño de origen y separa las propuestas
futuras del comportamiento disponible.

### 4.3 Usuario

Un Usuario representa a una persona que interactúa con Free Win. El componente actual contempla información de identidad, contacto, rol y direcciones.

### 4.4 Dirección de usuario

Una Dirección de usuario representa un lugar asociado con un Usuario y puede utilizarse en futuros flujos de entrega. El modelo contempla nombre, ubicación geográfica, estado, ciudad, dirección y código postal.

### 4.5 Rol de usuario

Un `Role` agrupa permisos. `PermissionCode` controla los códigos que esta API
puede asignar, mientras la tabla compartida puede conservar códigos pertenecientes
a `free-win-search`. `Admin` y `User` son roles de sistema inmutables; los
administradores pueden crear roles personalizados y reemplazar atómicamente su
conjunto de permisos locales.

`UserRole` es un puente temporal entre `User` y `Role`. Cada `Role` posee un único puente y las nuevas asignaciones se realizan con el ID real del rol mediante `PUT /users/{user_id}/role`. La API `/user-roles` se conserva solamente por compatibilidad y está marcada como obsoleta.

### 4.6 Carta y publicación

Una Carta contiene los metadatos descriptivos y relativamente estáticos del artículo que el jugador desea localizar. Una Publicación de carta (`CardListing`) representa una edición y condición concretas con precio y disponibilidad. Ambos conceptos pertenecen a `free-win-search`.

Una misma carta puede tener múltiples publicaciones porque el set, la condición, el precio o la disponibilidad pueden variar. Free Win no expone su búsqueda ni CRUD: solamente valida el ID de una publicación existente y copia un snapshot dentro del ítem de una Orden.

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
- endpoints protegidos para Usuarios y Direcciones de usuario;
- catálogo de permisos y CRUD de Roles personalizados;
- autorización por permisos y propiedad con identidad local temporal;
- creación, consulta, modificación, cierre e historial de Pedidos;
- creación, consulta, edición, revisión, precios, estados e historial de Órdenes;
- una sesión asíncrona de SQLAlchemy para PostgreSQL;
- un DAO genérico con operaciones de consulta y persistencia;
- un contrato de caché sustituible con implementaciones en memoria y Valkey;
- configuración separada para API, caché y base de datos.

La superficie HTTP registrada actualmente incluye:

| Recurso | Prefijo | Operaciones actuales |
| --- | --- | --- |
| Usuarios | `/users` | listar, obtener, crear, actualizar y eliminar |
| Direcciones | `/user-addresses` | listar, obtener, crear, actualizar y eliminar |
| Roles de usuario | `/user-roles` | listar, obtener, crear, actualizar y eliminar |
| Roles | `/roles` | CRUD de roles personalizados y asignación de permisos |
| Permisos | `/permissions` | lectura de la tabla compartida; asignación limitada al Enum local |
| Pedidos | `/order-periods` | crear, listar, obtener, modificar, cerrar y consultar historial |
| Órdenes | `/order-requests` | crear, listar, obtener, editar nota e ítems, revisar, cotizar, aceptar, rechazar, cancelar, reabrir y consultar historial |

La raíz `/` devuelve un mensaje de bienvenida.

Los endpoints protegidos no están disponibles de forma anónima. Durante el desarrollo puede configurarse temporalmente `AUTH_MODE=local` junto con `AUTH_LOCAL_USER_ID`; si falta cualquiera de los valores, responden `401`. Esa identidad local recibe todos los permisos del catálogo para pruebas manuales, sin cambiar su rol persistido. El registro `POST /users` permanece público y siempre asigna el rol de sistema `User`.

### 6.2 Contrato HTTP normalizado

OpenAPI es el contrato oficial entre el backend y sus clientes. La normalización
se aplicó directamente sobre las rutas existentes, sin duplicarlas ni introducir
un período adicional de deprecación. Los consumidores deben coordinar estos
cambios incompatibles:

- los listados paginados de Usuarios, Direcciones y Roles de usuario comienzan
  en `page=1`;
- esos listados validan `1 <= shows <= 100` y responden `{items, total}`;
- los catálogos completos de Roles y Permisos continúan como arrays porque no
  representan listados paginados;
- las eliminaciones exitosas de Usuarios, Direcciones y Roles de usuario
  responden `204 No Content` sin cuerpo;
- los identificadores de ruta deben ser positivos; cero y valores negativos
  producen la validación estándar `422` de FastAPI;
- la creación de Direcciones y Roles de usuario responde `201 Created`;
- las actualizaciones y acciones conservan `200 OK`, salvo eliminaciones con
  `204 No Content`.

Estos cambios sustituyen las respuestas de texto `"Eliminado"`, las páginas
basadas en cero y los arrays paginados anteriores. `user-roles` continúa marcado
como obsoleto: su normalización no revierte ni amplía esa estrategia.

### 6.3 Estructura preparada pero incompleta

`order_periods` implementa los Pedidos y `order_requests` implementa la primera versión de las Órdenes hasta la revisión inicial.

También están pendientes de definición o finalización:

- autenticación real, hashing de contraseñas y emisión de tokens;
- pago y estado `paid` de las Órdenes;
- cantidades efectivamente compradas y resultados posteriores a la revisión inicial;
- dirección de entrega, comprobantes y trazabilidad de entrega;
- plataforma y URL de origen dentro del snapshot de un ítem;
- vista consolidada y exportación administrativa por Pedido;
- entorno Valkey disponible para validar la integración distribuida;
- contrato uniforme de errores HTTP.

### 6.4 Órdenes v1

Un Usuario puede crear una Orden propia únicamente mientras el Pedido asociado
está abierto. Cada ítem referencia una `CardListing` existente y conserva un
snapshot de sus datos; la cantidad acordada comienza igual a la solicitada. Los
recursos de otro Usuario se ocultan mediante `404`, mientras un Administrador
con permisos globales puede consultar y administrar todas las Órdenes.

El flujo administrativo disponible es:

```text
submitted → in_review → accepted
     └───────────────→ rejected
     └───────────────→ cancelled
accepted | rejected | cancelled → in_review
```

Los precios definitivos se expresan en USD mediante los componentes unitarios de
carta, envío e impuesto. El precio final, subtotales y total acordado se derivan
de los ítems activos y no se persisten como totales independientes. Aceptar exige
al menos un ítem activo y precios completos; cero es un importe válido. Cambiar
cantidades o precios después de aceptar recalcula los totales sin cambiar el
estado automáticamente.

Cada mutación dependiente del estado bloquea la Orden y guarda su historial en la
misma transacción. Retirar un ítem no lo elimina; si era el último activo, la
Orden pasa a `cancelled`. Una operación sin cambios efectivos no genera un evento.

Quedan expresamente fuera de esta versión: `paid`, cantidades compradas,
dirección de entrega, comprobantes, plataforma/URL, vista consolidada,
exportaciones y seguimiento de entrega.

## 7) Arquitectura general

### 7.1 Organización del backend

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

## 9) Límite con el servicio de búsqueda

`free-win-search` expone la búsqueda de cartas y administra las tablas `cards` y
`card_listings`. Free Win comparte la misma base de datos, pero el desacoplamiento
es explícito a nivel de aplicación y migraciones.

`src/api/order_requests/repository/card_listings.py` declara una proyección mínima
de solo lectura. Al crear o modificar una Orden, el caso de uso consulta por ID y
copia nombre, set, código, precio, rareza y condición al snapshot del ítem. No
invoca casos de uso, routers ni modelos ORM del servicio de búsqueda.

La relación se conserva en PostgreSQL:

```text
order_request_items.card_listing_id
                 ↓ FK
        card_listings.id
        (free-win-search)
```

Las migraciones históricas de Free Win permanecen intactas. Las migraciones nuevas
excluyen las tablas externas durante `autogenerate`; `free-win-search` registra su
historia mediante `free_win_search_alembic_version`.

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

- trazabilidad completa de Órdenes;
- Pre-Pedidos;
- mapa de entrega;
- históricos de precios;
- integración de cliente con el API independiente de búsqueda.

Esta lista no autoriza a implementar alcance adicional durante una tarea no relacionada.

## 12) Navegación recomendada

Para conocer el proyecto, el orden de lectura recomendado es:

1. `README.md`: resumen y estructura.
2. `AGENTS.md`: contexto del dominio y reglas para agentes.
3. `docs/general_documentation.md`: visión funcional y técnica general.
4. `docs/orderRequestIdea.md`: diseño funcional previsto de las Órdenes.
5. `src/application.py`: creación de FastAPI.
6. `src/api/api.py`: routers disponibles.
7. `src/api/users/`: ejemplo más completo de un componente.
8. `src/core/db/`: persistencia compartida.
9. `src/api/order_requests/repository/card_listings.py`: límite de lectura con el servicio de búsqueda.
10. `docs/conventions.md`: reglas de implementación.
11. `docs/system_patterns.md`: patrones técnicos detallados a medida que se documenten.

## 13) Referencias

- `README.md`: presentación del repositorio.
- `AGENTS.md`: propósito, vocabulario y criterio de producto.
- `src/application.py`: aplicación FastAPI.
- `src/api/api.py`: routers registrados.
- `src/api/users/`: implementación actual de Usuarios, Direcciones y Roles.
- `src/core/db/`: infraestructura de persistencia.
- `src/api/order_requests/repository/card_listings.py`: proyección externa de Publicaciones.
- `docs/conventions.md`: convenciones de código y diseño.
- `docs/orderRequestIdea.md`: decisiones y propuestas funcionales de las Órdenes.
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
- **Estado**: vigente.
- **Contexto**: el monorepo inicial añadía estructura para un cliente que todavía no forma parte del trabajo actual.
- **Decisión**: este repositorio contiene exclusivamente el backend de Free Win.
- **Impacto**: cualquier frontend futuro se desarrollará fuera de este repositorio salvo que se revise explícitamente la decisión.
- **Evidencia**: `README.md`, `src/`.
- **Revisión**: reconsiderar solamente si mantener ambos proyectos juntos aporta una ventaja concreta.

### DEC-20260720-scraper-in-backend

- **Fecha**: 2026-07-20.
- **Estado**: sustituida por `DEC-20260811-search-service-separated`.
- **Contexto**: el primer flujo de búsqueda y carga de cartas se implementó dentro de este backend.
- **Decisión**: mantener temporalmente el scraper en `src/core/services/scraper/`, con límites que permitieran extraerlo después.
- **Impacto**: esta decisión explica la presencia de migraciones históricas de cartas en Free Win, pero ya no describe su aplicación actual.
- **Evidencia**: las revisiones históricas de `migrations/versions/` y el commit anterior a la extracción.
- **Revisión**: cerrada el 2026-08-11 al trasladar búsqueda, scraping y propiedad futura del esquema a `free-win-search`.

### DEC-20260811-search-service-separated

- **Fecha**: 2026-08-11.
- **Estado**: vigente.
- **Contexto**: la búsqueda y carga de cartas necesitan un ciclo de aplicación y migraciones independiente.
- **Decisión**: `free-win-search` administra búsqueda, scraping, `cards` y `card_listings`; Free Win conserva solamente la FK y una proyección de lectura para snapshots de Órdenes.
- **Impacto**: ambos servicios comparten PostgreSQL, pero no importan componentes de aplicación entre sí y utilizan tablas de versión Alembic distintas.
- **Evidencia**: `src/api/order_requests/repository/card_listings.py`, `migrations/ownership.py`.
- **Revisión**: reevaluar si las bases de datos se separan físicamente o la referencia deja de resolverse mediante FK.

## 16) Checklist de actualización

Actualiza este documento cuando cambie alguno de estos puntos:

- [ ] propósito o alcance general de Free Win;
- [ ] definición de Pedido, Orden, Usuario o Publicación;
- [ ] flujo funcional principal;
- [ ] componentes disponibles o responsabilidades de alto nivel;
- [ ] routers expuestos por la API;
- [ ] límite de datos y migraciones con `free-win-search`;
- [ ] estado real de una funcionalidad descrita como actual o prevista;
- [ ] decisiones o restricciones que alteren el modelo mental del proyecto.
