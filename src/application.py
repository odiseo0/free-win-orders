from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api import router

app = FastAPI(
    title="Free Win",
    description="Free Win API REST.",
    version="1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/")


@app.get("/")
async def welcome():
    return {"message": "Bienvenido a Free Win"}
