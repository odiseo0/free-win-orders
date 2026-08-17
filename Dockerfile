# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.13-slim

FROM python:${PYTHON_VERSION} AS builder

ARG PDM_VERSION=2.28.0

ENV PDM_CHECK_UPDATE=false \
    PDM_VENV_IN_PROJECT=1

WORKDIR /app

RUN pip install --no-cache-dir "pdm==${PDM_VERSION}"

COPY pyproject.toml pdm.lock ./

RUN pdm lock --check \
    && pdm sync --prod --no-self --clean-unselected

FROM python:${PYTHON_VERSION} AS runtime

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 freewin \
    && useradd --uid 10001 --gid freewin --no-log-init --create-home freewin

WORKDIR /app

COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv
COPY --chown=10001:10001 src ./src
COPY --chown=10001:10001 migrations ./migrations
COPY --chown=10001:10001 alembic.ini ./alembic.ini

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2).read()"]

CMD ["uvicorn", "src.application:app", "--host", "0.0.0.0", "--port", "8000"]
