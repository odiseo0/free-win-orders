from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import get_db
from src.core.schema import BaseModel
from src.core.services.cache import Cache, get_cache


class HealthResponse(BaseModel):
    status: Literal["ok", "ready", "unavailable"]


router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "/live",
    response_model=HealthResponse,
    summary="Comprobar que el proceso HTTP responde",
    description="No consulta PostgreSQL ni el caché configurado.",
    operation_id="getHealthLiveness",
)
async def get_liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={
        503: {
            "model": HealthResponse,
            "description": "PostgreSQL o el caché configurado no están disponibles.",
        }
    },
    summary="Comprobar las dependencias necesarias para atender solicitudes",
    description="Comprueba PostgreSQL y el caché sin exponer datos de conexión.",
    operation_id="getHealthReadiness",
)
async def get_readiness(
    db: AsyncSession = Depends(get_db),
    cache: Cache = Depends(get_cache),
) -> HealthResponse | JSONResponse:
    try:
        await db.execute(text("SELECT 1"))
        await cache.check_health()
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable"},
        )

    return HealthResponse(status="ready")
