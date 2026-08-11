# Free Win

Backend de la aplicación comunitaria Free Win para gestionar pedidos de cartas de Yu-Gi-Oh! difíciles de conseguir en el país.

Free Win centraliza la apertura de períodos de Pedido, el envío de Órdenes por parte de los jugadores y su posterior revisión por los administradores. También gestiona los usuarios, roles y permisos propios de este backend. La búsqueda y carga de cartas vive en el servicio separado [`free-win-search`](https://github.com/odiseo0/free-win-search); ambos backends comparten PostgreSQL y las Órdenes referencian sus publicaciones mediante `card_listings`.

## Stack actual

- Python 3.13
- FastAPI
- SQLAlchemy 2
- PostgreSQL mediante `asyncpg`
- Valkey mediante `valkey-py` como proveedor distribuido de caché
- PDM

## Estructura

```text
src/
├── application.py        # Punto de entrada de FastAPI
├── api/                 # Componentes y endpoints de la API
│   ├── order_periods/
│   ├── order_requests/
│   ├── roles/
│   └── users/
├── core/                # Base de datos, servicios y utilidades compartidas
└── settings/            # Configuración de la aplicación
docs/                    # Documentación y referencias para su futura adaptación
tests/                   # Pruebas automatizadas
```

Los componentes de `src/api/` siguen una arquitectura hexagonal pragmática:

```text
<component>/
├── domain/              # Entidades y reglas de negocio
├── application/         # Casos de uso
├── infrastructure/      # Adaptadores, incluidos endpoints HTTP
└── repository/          # Persistencia y acceso a datos
```

El caché vive en `src/core/services/cache/` y permite alternar entre memoria y Valkey mediante `CACHE_BACKEND`. La proyección de solo lectura usada para validar publicaciones externas está en `src/api/order_requests/repository/card_listings.py`.

## Documentación

La carpeta `docs/` contiene documentos que servirán como base de formato y organización. Parte de su contenido todavía proviene de otro contexto y debe adaptarse completamente a Free Win antes de considerarse documentación vigente del proyecto.
