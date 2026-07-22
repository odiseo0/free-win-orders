# Free Win

Backend de la aplicación comunitaria Free Win para gestionar pedidos de cartas de Yu-Gi-Oh! difíciles de conseguir en el país.

Free Win centraliza la apertura de períodos de Pedido, el envío de Órdenes por parte de los jugadores y su posterior revisión por los administradores. El proyecto también contiene un pipeline de scraping para buscar cartas y preparar información que eventualmente pueda consultarse desde una base de datos propia.

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
│   ├── cards/
│   ├── collections/
│   ├── order_periods/
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

El scraper está implementado en `src/core/services/scraper/`.
El caché vive en `src/core/services/cache/` y permite alternar entre memoria y Valkey mediante `CACHE_BACKEND`.

## Documentación

La carpeta `docs/` contiene documentos que servirán como base de formato y organización. Parte de su contenido todavía proviene de otro contexto y debe adaptarse completamente a Free Win antes de considerarse documentación vigente del proyecto.
