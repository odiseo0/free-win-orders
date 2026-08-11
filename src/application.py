from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import router
from src.core.services.cache import close_cache, get_cache

API_DESCRIPTION = """
Free Win centraliza los **Pedidos** de cartas de Yu-Gi-Oh! difíciles de conseguir
en el país y las **Órdenes** que los usuarios envían dentro de cada Pedido.

La API permite gestionar usuarios y permisos, abrir y administrar Pedidos, y
revisar las Órdenes que referencian publicaciones del servicio de búsqueda.

## Autenticación temporal

Durante el desarrollo local, la identidad se selecciona mediante la configuración
del backend. Los clientes no envían todavía credenciales, tokens Bearer ni OAuth2.
Este mecanismo es temporal y por ello OpenAPI no declara un esquema de seguridad.
"""

OPENAPI_TAGS = [
    {
        "name": "order-periods",
        "description": "Apertura, consulta y administración de Pedidos.",
    },
    {
        "name": "order-requests",
        "description": "Envío y revisión de Órdenes dentro de un Pedido.",
    },
    {
        "name": "users",
        "description": "Usuarios que participan en Pedidos y administran Free Win.",
    },
    {
        "name": "user-addresses",
        "description": "Direcciones de entrega asociadas a los usuarios.",
    },
    {
        "name": "roles",
        "description": "Roles y asignación de permisos administrativos.",
    },
    {
        "name": "permissions",
        "description": "Tabla compartida de permisos usados por Free Win y sus servicios.",
    },
    {
        "name": "user-roles",
        "description": "API heredada de asignaciones entre usuarios y roles.",
    },
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    cache = get_cache()

    try:
        await cache.start()
        yield
    finally:
        await close_cache()


app = FastAPI(
    title="Free Win",
    description=API_DESCRIPTION,
    version="0.1.0",
    license_info={"name": "MIT"},
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
async def welcome():
    return {"message": "Bienvenido a Free Win"}
