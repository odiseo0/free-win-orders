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

## Docker Compose

Este repositorio inicia la API y el worker de entregas. No crea PostgreSQL,
usuarios, permisos ni tablas. Ambos procesos leen la conexión existente desde
`.env`.

Compose no resuelve la autenticación pendiente. Mantén `AUTH_MODE=disabled` y no
expongas el sistema a usuarios anónimos hasta implementar autenticación real.

Copia el ejemplo y configura tu PostgreSQL externo:

```bash
cp .env.example .env
```

Como mínimo, revisa `DB_HOST`, `DB_NAME`, `DB_PORT`, `DB_USERNAME` y
`DB_PASSWORD`. También puedes usar `SQLALCHEMY_DATABASE_URI`. El contenedor debe
poder resolver y alcanzar el host configurado. Si PostgreSQL está en la misma
máquina, `localhost` no sirve dentro del contenedor; usa
`host.docker.internal` y añade el acceso del servidor PostgreSQL a esa conexión.

Construye e inicia:

```bash
docker compose up -d --build
```

La API queda disponible solo en `http://127.0.0.1:8000`. Cambia
`FREE_WIN_API_PORT` si ese puerto está ocupado. Consulta el estado con:

```bash
docker compose ps
docker compose logs --tail=100 free-win-api
```

Compose no ejecuta Alembic, el bootstrap ni ninguna tarea de administración de
PostgreSQL. Mantén esos procesos fuera de este arranque.

La API expone dos comprobaciones:

- `GET /health/live`: confirma que el proceso HTTP responde;
- `GET /health/ready`: comprueba PostgreSQL y el caché configurado.

Compose usa la primera como comprobación del proceso y no modifica la base.

## Documentación

La carpeta `docs/` contiene documentos que servirán como base de formato y organización. Parte de su contenido todavía proviene de otro contexto y debe adaptarse completamente a Free Win antes de considerarse documentación vigente del proyecto.
