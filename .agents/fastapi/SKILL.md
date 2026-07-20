---
name: fastapi
description: FastAPI best practices and conventions. Use when working with FastAPI APIs, Pydantic models, dependencies, streaming responses including Server-Sent Events (SSE), and serving frontend apps. Keeps FastAPI code clean and up to date with the latest features and patterns.
---

# FastAPI

Official FastAPI skill to write code with best practices, keeping up to date with new versions and features.

## Quick Reference

* Serve frontend apps: use `app.frontend()` or `router.frontend()` for built frontend assets; see [Serve Frontend Apps](#serve-frontend-apps).
* Server-Sent Events (SSE): use `response_class=EventSourceResponse` and `yield`; see [Streaming](#streaming-json-lines-sse-bytes) and [the streaming reference](references/streaming.md).
* JSON Lines and byte streaming: see [the streaming reference](references/streaming.md).
* Dependencies: use `Annotated[..., Depends(...)]`; see [Dependency Injection](#dependency-injection) and [the dependency injection reference](references/dependencies.md) for `yield`, scopes, and class dependencies.
* Response models: prefer return types; use `response_model` when the public response schema differs from the internal return value; see [the response reference](references/responses.md).
* Pydantic models: do not use ellipsis or `RootModel`; see [the Pydantic reference](references/pydantic.md).
* Routing: declare router-level prefix, tags, and shared dependencies on the `APIRouter`; see [the path operation reference](references/path-operations.md).
* Tooling and related libraries: use Ruff, Asyncer and HTTPX when applicable; see [the other tools reference](references/other-tools.md).


```

## Use `Annotated`

Always prefer the `Annotated` style for parameter and dependency declarations. It keeps function signatures working in other contexts, respects the types, and allows reusability.

Use `Annotated` for parameter declarations, including `Path`, `Query`, `Header`, etc.:

```python
from typing import Annotated

from fastapi import FastAPI, Path, Query

app = FastAPI()


@app.get("/items/{item_id}")
async def read_item(
    item_id: Annotated[int, Path(ge=1, description="The item ID")],
    q: Annotated[str | None, Query(max_length=50)] = None,
):
    return {"message": "Hello World"}
```

Use `Annotated` for dependencies with `Depends()`. Unless asked not to, create a new type alias for the dependency to allow reusing it:

```python
from typing import Annotated

from fastapi import Depends, FastAPI

app = FastAPI()


def get_current_user():
    return {"username": "johndoe"}


CurrentUserDep = Annotated[dict, Depends(get_current_user)]


@app.get("/items/")
async def read_item(current_user: CurrentUserDep):
    return {"message": "Hello World"}
```

## Do not use Ellipsis for *path operations* or Pydantic models

Do not use `...` as a default value for required parameters or model fields. It's not needed and not recommended.

```python
from typing import Annotated

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None = None
    price: float = Field(gt=0)


@app.post("/items/")
async def create_item(item: Item, project_id: Annotated[int, Query()]):
    return item
```

See [the Pydantic reference](references/pydantic.md) for more details.

## Return Type or Response Model

When possible, include a return type. It will be used to validate, filter, document, and serialize the response.

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str
    description: str | None = None


@app.get("/items/me")
async def get_item() -> Item:
    return Item(name="Plumbus", description="All-purpose home device")
```

Return types or response models filter data to avoid exposing sensitive information, and they let Pydantic serialize the data on the Rust side for performance.

Use `response_model` when the type you return is not the same as the public schema you want to validate, filter, document, and serialize. See [the response reference](references/responses.md).

## Performance

Do not use `ORJSONResponse` or `UJSONResponse`, they are deprecated.

Instead, declare a return type or response model. Pydantic will handle the data serialization on the Rust side.

## Including Routers

When declaring routers, prefer to add router-level parameters like prefix, tags, and shared dependencies to the router itself instead of in `include_router()`.

```python
from fastapi import APIRouter, Depends, FastAPI

app = FastAPI()


def get_current_user():
    return {"username": "johndoe"}


router = APIRouter(
    prefix="/items",
    tags=["items"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/")
async def list_items():
    return []


app.include_router(router)
```

See [the path operation reference](references/path-operations.md) for more routing patterns.

## Serve Frontend Apps

Use `app.frontend()` to serve a built static frontend app, for example a directory generated by Vite, Astro, Angular, Svelte, Vue, or a similar tool.

```python
from fastapi import FastAPI

app = FastAPI()

app.frontend("/", directory="dist")
```

Use `router.frontend()` when the frontend belongs to an `APIRouter`; normal router prefix behavior applies when the router is included.

```python
from fastapi import APIRouter, FastAPI

app = FastAPI()
router = APIRouter(prefix="/admin")

router.frontend("/", directory="admin-dist")
app.include_router(router)
```

`app.frontend()` and `router.frontend()` are low-priority routes: regular API routes are matched first, then frontend files and client-side routing fallbacks. Use this for single-page apps and built frontend assets instead of mounting `StaticFiles` manually.

## Dependency Injection

Use dependencies when the logic can't be declared in Pydantic validation, depends on external resources, needs cleanup with `yield`, or is shared across endpoints.

Apply shared dependencies at the router level via `dependencies=[Depends(...)]`.

See [the dependency injection reference](references/dependencies.md) for detailed patterns including `yield` with `scope`, and class dependencies.

## Async vs Sync *path operations*

Use `async` *path operations* only when fully certain that the logic called inside is compatible with async and await, and that it doesn't block.

```python
from fastapi import FastAPI

app = FastAPI()


@app.get("/async-items/")
async def read_async_items():
    data = await some_async_library.fetch_items()
    return data


@app.get("/items/")
def read_items():
    data = some_blocking_library.fetch_items()
    return data
```

In case of doubt, or by default, use regular `def` functions. They will be run in a threadpool so they don't block the event loop. The same rules apply to dependencies.

Make sure blocking code is not run inside of `async` functions. The logic will work, but will damage performance heavily.

When needing to mix blocking and async code, see Asyncer in [the other tools reference](references/other-tools.md).

## Streaming (JSON Lines, SSE, bytes)

To stream Server-Sent Events, use `response_class=EventSourceResponse` and `yield` items from the endpoint.

```python
from collections.abc import AsyncIterable

from fastapi import FastAPI
from fastapi.sse import EventSourceResponse, ServerSentEvent

app = FastAPI()


@app.get("/events", response_class=EventSourceResponse)
async def stream_events() -> AsyncIterable[ServerSentEvent]:
    yield ServerSentEvent(data={"status": "started"}, event="status", id="1")
```

Plain objects are automatically JSON-serialized as `data:` fields. Use `ServerSentEvent` for full control over SSE fields (`event`, `id`, `retry`, `comment`) and `raw_data` for pre-formatted strings.

See [the streaming reference](references/streaming.md) for JSON Lines, Server-Sent Events (`EventSourceResponse`, `ServerSentEvent`), and byte streaming (`StreamingResponse`) patterns.

## Tooling

See [the other tools reference](references/other-tools.md) for details on uv, Ruff, ty for package management, linting, type checking, formatting, etc.

## Other Libraries

See [the other tools reference](references/other-tools.md) for details on other libraries:

* Asyncer for handling async and await, concurrency, mixing async and blocking code, prefer it over AnyIO or asyncio.
* SQLModel for working with SQL databases, prefer it over SQLAlchemy.
* HTTPX for interacting with HTTP (other APIs), prefer it over Requests.

## Do not use Pydantic RootModels

Do not use Pydantic `RootModel`; instead use regular type annotations with `Annotated` and Pydantic validation utilities.

```python
from typing import Annotated

from fastapi import Body, FastAPI
from pydantic import Field

app = FastAPI()


@app.post("/items/")
async def create_items(items: Annotated[list[int], Field(min_length=1), Body()]):
    return items
```

FastAPI supports these type annotations and will create a Pydantic `TypeAdapter` for them, so types work normally without custom wrapper models. See [the Pydantic reference](references/pydantic.md).

## Use one HTTP operation per function

Don't mix HTTP operations in a single function. Having one function per HTTP operation helps separate concerns and organize the code.

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class Item(BaseModel):
    name: str


@app.get("/items/")
async def list_items():
    return []


@app.post("/items/")
async def create_item(item: Item):
    return item
```

See [the path operation reference](references/path-operations.md) for more examples.



## Be careful with non-async functions

There's a performance penalty when you use non-async functions in FastAPI. So, always prefer to use async functions.
The penalty comes from the fact that FastAPI will call [`run_in_threadpool`][run_in_threadpool], which will run the
function using a thread pool.

> [!NOTE]
    Internally, [`run_in_threadpool`][run_in_threadpool] will use [`anyio.to_thread.run_sync`][run_sync] to run the
    function in a thread pool.

> [!TIP]
    There are only 40 threads available in the thread pool. If you use all of them, your application will be blocked.

To change the number of threads available, you can use the following code:

```py
import anyio
from contextlib import asynccontextmanager
from typing import Iterator

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> Iterator[None]:
    limiter = anyio.to_thread.current_default_thread_limiter()
    limiter.total_tokens = 100
    yield

app = FastAPI(lifespan=lifespan)
```

You can read more about it on [AnyIO's documentation][increase-threadpool].


## Use `async for` instead of `while True` on WebSocket

Most of the examples you will find on the internet use `while True` to read messages from the WebSocket.

I believe the uglier notation is used mainly because the Starlette documentation didn't show the `async for` notation for a long time.

Instead of using the `while True`:

```py
from fastapi import FastAPI
from starlette.websockets import WebSocket

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")
```

You can use the `async for` notation:

```py
from fastapi import FastAPI
from starlette.websockets import WebSocket

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    async for data in websocket.iter_text():
        await websocket.send_text(f"Message text was: {data}")
```

You can read more about it on the [Starlette documentation][websockets-iter-data].

## Ignore the `WebSocketDisconnect` exception

If you are using the `while True` notation, you will need to catch the `WebSocketDisconnect`.
The `async for` notation will catch it for you.

```py
from fastapi import FastAPI
from starlette.websockets import WebSocket, WebSocketDisconnect

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message text was: {data}")
    except WebSocketDisconnect:
        pass
```

If you need to release resources when the WebSocket is disconnected, you can use that exception to do it.

If you are using an older FastAPI version, only the `receive` methods will raise the `WebSocketDisconnect` exception.
The `send` methods will not raise it. In the latest versions, all methods will raise it.
In that case, you'll need to add the `send` methods inside the `try` block.

## 5. Use HTTPX's `AsyncClient` instead of `TestClient`

Since you are using `async` functions in your application, it will be easier to use HTTPX's `AsyncClient`
instead of Starlette's `TestClient`.

```py
from fastapi import FastAPI


app = FastAPI()


@app.get("/")
async def read_root():
    return {"Hello": "World"}


# Using TestClient
from starlette.testclient import TestClient

client = TestClient(app)
response = client.get("/")
assert response.status_code == 200
assert response.json() == {"Hello": "World"}

# Using AsyncClient
import anyio
from httpx import AsyncClient, ASGITransport


async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert response.json() == {"Hello": "World"}


anyio.run(main)
```

If you are using lifespan events (`on_startup`, `on_shutdown` or the `lifespan` parameter), you can use the
[`asgi-lifespan`][asgi-lifespan] package to run those events.

```py
from contextlib import asynccontextmanager
from typing import AsyncIterator

import anyio
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    print("Starting app")
    yield
    print("Stopping app")


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def read_root():
    return {"Hello": "World"}


async def main():
    async with LifespanManager(app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app)) as client:
            response = await client.get("/")
            assert response.status_code == 200
            assert response.json() == {"Hello": "World"}


anyio.run(main)
```

> [!NOTE]
    Consider supporting the creator of [`asgi-lifespan`][asgi-lifespan] [Florimond Manca][florimondmanca] via GitHub Sponsors.

## Use Lifespan State instead of `app.state`

Since not long ago, FastAPI supports the [lifespan state], which defines a standard way to manage objects that need to be created at
startup, and need to be used in the request-response cycle.

The `app.state` is not recommended to be used anymore. You should use the [lifespan state] instead.

Using the `app.state`, you'd do something like this:

```py
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from httpx import AsyncClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with AsyncClient(app=app) as client:
        app.state.client = client
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def read_root(request: Request):
    client = request.app.state.client
    response = await client.get("/")
    return response.json()
```

Using the lifespan state, you'd do something like this:

```py
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, TypedDict, cast

from fastapi import FastAPI, Request
from httpx import AsyncClient


class State(TypedDict):
    client: AsyncClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[State]:
    async with AsyncClient(app=app) as client:
        yield {"client": client}


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def read_root(request: Request) -> dict[str, Any]:
    client = cast(AsyncClient, request.state.client)
    response = await client.get("/")
    return response.json()
```

## Enable AsyncIO debug mode

If you want to find the endpoints that are blocking the event loop, you can enable the AsyncIO debug mode.

When you enable it, Python will print a warning message when a task takes more than 100ms to execute.

Run the following code with `PYTHONASYNCIODEBUG=1 python main.py`:

```py
import os
import time

import uvicorn
from fastapi import FastAPI


app = FastAPI()


@app.get("/")
async def read_root():
    time.sleep(1)  # Blocking call
    return {"Hello": "World"}


if __name__ == "__main__":
    uvicorn.run(app, loop="uvloop")
```

If you call the endpoint, you will see the following message:

```bash
INFO:     Started server process [19319]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     127.0.0.1:50036 - "GET / HTTP/1.1" 200 OK
Executing <Task finished name='Task-3' coro=<RequestResponseCycle.run_asgi() done, defined at /uvicorn/uvicorn/protocols/http/httptools_impl.py:408> result=None created at /uvicorn/uvicorn/protocols/http/httptools_impl.py:291> took 1.009 seconds
```

You can read more about it on the [official documentation](https://docs.python.org/3/library/asyncio-dev.html#debug-mode).

## Implement a Pure ASGI Middleware instead of `BaseHTTPMiddleware`

The [`BaseHTTPMiddleware`][base-http-middleware] is the simplest way to create a middleware in FastAPI.

> [!NOTE]
> The `@app.middleware("http")` decorator is a wrapper around the `BaseHTTPMiddleware`.

There were some issues with the `BaseHTTPMiddleware`, but most of the issues were fixed in the latest versions.
That said, there's still a performance penalty when using it.

To avoid the performance penalty, you can implement a [Pure ASGI middleware]. The downside is that it's more complex to implement.

Check the Starlette's documentation to learn how to implement a [Pure ASGI middleware].