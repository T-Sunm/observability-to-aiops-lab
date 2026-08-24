FROM ghcr.io/astral-sh/uv:0.9.18 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY services/demo_app/main.py ./main.py

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "opentelemetry-instrument", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
