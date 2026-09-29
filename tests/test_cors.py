import asyncio

from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient, Response

from src.application import app
from src.settings.api_settings import api_settings


def test_cors_uses_configured_origins_without_wildcard() -> None:
    middleware = next(
        item for item in app.user_middleware if item.cls is CORSMiddleware
    )

    assert middleware.kwargs["allow_origins"] == api_settings.cors_allowed_origins
    assert "*" not in middleware.kwargs["allow_origins"]


def test_cors_rejects_an_unconfigured_origin() -> None:
    async def request() -> Response:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            return await client.options(
                "/health/live",
                headers={
                    "Origin": "https://otro.example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )

    response = asyncio.run(request())
    assert "access-control-allow-origin" not in response.headers
