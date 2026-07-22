from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import router
from src.core.services.cache import close_cache, get_cache


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    cache = get_cache()

    try:
        await cache.start()
        yield
    finally:
        await close_cache()


app = FastAPI(
    title="Free Win",
    description="Free Win API REST.",
    version="1.0",
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
