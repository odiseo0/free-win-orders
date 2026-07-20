# Dependency Injection



Use dependencies when:

* They can't be declared in Pydantic validation and require additional logic
* The logic depends on external resources or could block in any other way
* Other dependencies need their results (it's a sub-dependency)
* The logic can be shared by multiple endpoints to do things like error early, handle authentication, etc.
* They need to handle cleanup (e.g., DB sessions, file handles), using dependencies with `yield`
* Their logic needs input data from the request, like headers, query parameters, etc.

## Dependencies with `yield` and `scope`

When using dependencies with `yield`, they can have a `scope` that defines when the exit code is run.

Use the default scope `"request"` to run the exit code after the response is sent back.

```python
from typing import Annotated

from fastapi import Depends, FastAPI

app = FastAPI()


def get_db():
    db = DBSession()
    try:
        yield db
    finally:
        db.close()


DBDep = Annotated[DBSession, Depends(get_db)]


@app.get("/items/")
async def read_items(db: DBDep):
    return db.query(Item).all()
```

Use the scope `"function"` when they should run the exit code after the response data is generated but before the response is sent back to the client.

```python
from typing import Annotated

from fastapi import Depends, FastAPI

app = FastAPI()


def get_username():
    try:
        yield "Rick"
    finally:
        print("Clean up before response is sent")

UserNameDep = Annotated[str, Depends(get_username, scope="function")]

@app.get("/users/me")
def get_user_me(username: UserNameDep):
    return username
```

## Class Dependencies

Avoid creating class dependencies when possible.

If a class is needed, instead create a regular function dependency that returns a class instance.

Do this:

```python
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, FastAPI

app = FastAPI()


@dataclass
class DatabasePaginator:
    offset: int = 0
    limit: int = 100
    q: str | None = None

    def get_page(self) -> dict:
        # Simulate a page of data
        return {
            "offset": self.offset,
            "limit": self.limit,
            "q": self.q,
            "items": [],
        }


def get_db_paginator(
    offset: int = 0, limit: int = 100, q: str | None = None
) -> DatabasePaginator:
    return DatabasePaginator(offset=offset, limit=limit, q=q)


PaginatorDep = Annotated[DatabasePaginator, Depends(get_db_paginator)]


@app.get("/items/")
async def read_items(paginator: PaginatorDep):
    return paginator.get_page()
```

instead of this:

```python
# DO NOT DO THIS
from typing import Annotated

from fastapi import Depends, FastAPI

app = FastAPI()


class DatabasePaginator:
    def __init__(self, offset: int = 0, limit: int = 100, q: str | None = None):
        self.offset = offset
        self.limit = limit
        self.q = q

    def get_page(self) -> dict:
        # Simulate a page of data
        return {
            "offset": self.offset,
            "limit": self.limit,
            "q": self.q,
            "items": [],
        }


@app.get("/items/")
async def read_items(paginator: Annotated[DatabasePaginator, Depends()]):
    return paginator.get_page()
```

### Beyond Dependency Injection
Pydantic is a great schema validator, but for complex validations that require database or external service calls, it's not enough.

FastAPI docs mostly present dependencies as DI for endpoints, but they're also great for request validation.

Dependencies can validate data against database constraints (e.g., checking if an email already exists, ensuring a user exists, etc.).
```python
# dependencies.py
async def valid_post_id(post_id: UUID4) -> dict[str, Any]:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()

    return post


# router.py
@router.get("/posts/{post_id}", response_model=PostResponse)
async def get_post_by_id(post: dict[str, Any] = Depends(valid_post_id)):
    return post


@router.put("/posts/{post_id}", response_model=PostResponse)
async def update_post(
    update_data: PostUpdate,  
    post: dict[str, Any] = Depends(valid_post_id), 
):
    updated_post = await service.update(id=post["id"], data=update_data)
    return updated_post


@router.get("/posts/{post_id}/reviews", response_model=list[ReviewsResponse])
async def get_post_reviews(post: dict[str, Any] = Depends(valid_post_id)):
    post_reviews = await reviews_service.get_by_post_id(post["id"])
    return post_reviews
```
If we didn't put data validation in a dependency, we would have to validate that `post_id` exists
in every endpoint and write the same tests for each of them. 

### Chain Dependencies
Dependencies can use other dependencies and avoid code repetition for similar logic.
```python
# dependencies.py
from fastapi.security import OAuth2PasswordBearer
import jwt  # PyJWT
from jwt.exceptions import InvalidTokenError

async def valid_post_id(post_id: UUID4) -> dict[str, Any]:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()

    return post


async def parse_jwt_data(
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="/auth/token"))
) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, "JWT_SECRET", algorithms=["HS256"])
    except InvalidTokenError:
        raise InvalidCredentials()

    return {"user_id": payload["id"]}


async def valid_owned_post(
    post: dict[str, Any] = Depends(valid_post_id), 
    token_data: dict[str, Any] = Depends(parse_jwt_data),
) -> dict[str, Any]:
    if post["creator_id"] != token_data["user_id"]:
        raise UserNotOwner()

    return post

# router.py
@router.get("/users/{user_id}/posts/{post_id}", response_model=PostResponse)
async def get_user_post(post: dict[str, Any] = Depends(valid_owned_post)):
    return post

```
### Decouple & Reuse dependencies. Dependency calls are cached
Dependencies can be reused multiple times, and they won't be recalculated - FastAPI caches dependency's result within a request's scope by default,
i.e. if `valid_post_id` gets called multiple times in one route, it will be called only once.

Knowing this, we can decouple dependencies onto multiple smaller functions that operate on a smaller domain and are easier to reuse in other routes.
For example, in the code below we are using `parse_jwt_data` three times:
1. `valid_owned_post`
2. `valid_active_creator`
3. `get_user_post`,

but `parse_jwt_data` is called only once, in the very first call.

```python
# dependencies.py
from fastapi import BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
import jwt  # PyJWT
from jwt.exceptions import InvalidTokenError

async def valid_post_id(post_id: UUID4) -> Mapping:
    post = await service.get_by_id(post_id)
    if not post:
        raise PostNotFound()

    return post


async def parse_jwt_data(
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="/auth/token"))
) -> dict:
    try:
        payload = jwt.decode(token, "JWT_SECRET", algorithms=["HS256"])
    except InvalidTokenError:
        raise InvalidCredentials()

    return {"user_id": payload["id"]}


async def valid_owned_post(
    post: Mapping = Depends(valid_post_id), 
    token_data: dict = Depends(parse_jwt_data),
) -> Mapping:
    if post["creator_id"] != token_data["user_id"]:
        raise UserNotOwner()

    return post


async def valid_active_creator(
    token_data: dict = Depends(parse_jwt_data),
):
    user = await users_service.get_by_id(token_data["user_id"])
    if not user["is_active"]:
        raise UserIsBanned()
    
    if not user["is_creator"]:
       raise UserNotCreator()
    
    return user
        

# router.py
@router.get("/users/{user_id}/posts/{post_id}", response_model=PostResponse)
async def get_user_post(
    worker: BackgroundTasks,
    post: Mapping = Depends(valid_owned_post),
    user: Mapping = Depends(valid_active_creator),
):
    """Get post that belong the active user."""
    worker.add_task(notifications_service.send_email, user["id"])
    return post

```

### Prefer `async` dependencies
FastAPI supports both `sync` and `async` dependencies. It's tempting to use `sync` when you don't need to await anything, but that's not the best choice.

Just like routes, `sync` dependencies run in a threadpool. Threads have overhead that's unnecessary for small non-I/O operations.

## Your dependencies may be running on threads

If the function is non-async and you use it as a dependency, it will run in a thread.

In the following example, the `http_client` function will run in a thread:

```py
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from httpx import AsyncClient
from fastapi import FastAPI, Request, Depends


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, AsyncClient]]:
    async with AsyncClient() as client:
        yield {"client": client}


app = FastAPI(lifespan=lifespan)


def http_client(request: Request) -> AsyncClient:
    return request.state.client


@app.get("/")
async def read_root(client: AsyncClient = Depends(http_client)):
    return await client.get("/")
```

To run in the event loop, you need to make the function async:
```py
# ...

async def http_client(request: Request) -> AsyncClient:
    return request.state.client

# ...
```

As an exercise for the reader, let's learn a bit more about how to check the running threads.

You can run the following with `python main.py`:

```py
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anyio
from anyio.to_thread import current_default_thread_limiter
from httpx import AsyncClient
from fastapi import FastAPI, Request, Depends


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[dict[str, AsyncClient]]:
    async with AsyncClient() as client:
        yield {"client": client}


app = FastAPI(lifespan=lifespan)


# Change this function to be async, and rerun this application.
def http_client(request: Request) -> AsyncClient:
    return request.state.client


@app.get("/")
async def read_root(client: AsyncClient = Depends(http_client)): ...


async def monitor_thread_limiter():
    limiter = current_default_thread_limiter()
    threads_in_use = limiter.borrowed_tokens
    while True:
        if threads_in_use != limiter.borrowed_tokens:
            print(f"Threads in use: {limiter.borrowed_tokens}")
            threads_in_use = limiter.borrowed_tokens
        await anyio.sleep(0)


if __name__ == "__main__":
    import uvicorn

    config = uvicorn.Config(app="main:app")
    server = uvicorn.Server(config)

    async def main():
        async with anyio.create_task_group() as tg:
            tg.start_soon(monitor_thread_limiter)
            await server.serve()

    anyio.run(main)
```

If you call the endpoint, you will see the following message:

```bash
❯ python main.py
INFO:     Started server process [23966]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
Threads in use: 1
INFO:     127.0.0.1:57848 - "GET / HTTP/1.1" 200 OK
Threads in use: 0
```

Replace the `def http_client` with `async def http_client` and rerun the application.
You will not see the message `Threads in use: 1`, because the function is running in the event loop.