# AGENTS.md

## Project Overview

Progressive Python 3.12 lab covering Metrics, Logs, Traces, then AIOps.
Use `main.pdf` for exercise order and learning goals; use verified runtime code for actual syntax.
Stack: FastAPI, Prometheus, Grafana, Loki, Alloy, OpenTelemetry, Jaeger, Alertmanager, Isolation Forest, Prophet, Docker Compose.
Use `uv` exclusively for Python environments and dependencies.

## Project Structure

```text
observability-to-aiops-lab/
├── README.md
├── pyproject.toml
├── uv.lock
├── docker-compose.yml
├── app/
├── inventory/
├── infra/
│   ├── prometheus/
│   ├── alertmanager/
│   ├── alloy/
│   ├── loki/
│   ├── otel-collector/
│   └── grafana/
├── aiops/
│   ├── anomaly/
│   └── forecasting/
├── notebooks/
├── tests/
└── main.pdf
```

`app/` and `inventory/` own service behavior; `infra/` owns configuration; `aiops/` consumes telemetry.

## Setup and Commands

```bash
uv sync --group dev
uv run python main.py
uv run ruff check .
uv run ruff format --check .
docker compose up -d --build
docker compose ps
docker compose down
```

Run AIOps scripts with `uv run --group aiops python aiops/<area>/<script>.py`.
Declare dependencies in `pyproject.toml`; commit generated `uv.lock` and never edit it manually.
Keep heavy AIOps packages in a separate uv dependency group when groups are introduced.

## Coding and Architecture Rules

- Make the smallest coherent change; do not refactor, rename, or reformat unrelated code.
- Reuse existing implementations before creating helpers, layers, packages, or dependencies.
- Follow PEP 8; use focused functions, meaningful names, type hints, `pathlib`, and f-strings.
- Keep imports ordered; avoid wildcard imports, mutable defaults, silent failures, and broad exception handling.
- Preserve public APIs and metric, logging, tracing, anomaly, and forecasting semantics unless required.
- Keep one root Compose project and use Alloy as the only Docker log collector.
- Keep application logic out of infrastructure configuration and AIOps logic out of API handlers.
- Prometheus is the initial AIOps data source; model files belong in a git-ignored artifact directory.
- Do not add Kafka, databases, feature stores, vector stores, LLM workflows, schedulers, or remediation without an explicit requirement.
- Do not commit secrets, `.env` files, telemetry data, or model binaries.

## Telemetry and Tutorial Contract

- Services: `demo-app` and `inventory-service`; checkout endpoint: `/checkout`.
- Metrics: `app_requests_total` and `app_request_latency_seconds_bucket`.
- Loki labels: `source="docker"` and `service`; severity values: `INFO`, `WARNING`, `ERROR`.
- Keep `trace_id`, `span_id`, request IDs, timestamps, messages, and events out of Loki stream labels.
- Preserve the practical sequence in `main.pdf`; adjust PromQL/LogQL to verified runtime identifiers.
- Every exercise states prerequisites, commands, expected results, and empty-result recovery.
- Prefer deterministic practice inputs; do not manually edit generated `main.pdf`.
- Finish Metrics, Logs, and Traces end to end before expanding AIOps acceptance criteria.

## Agent Instructions

- Preserve user changes and inspect the real call/data path before editing.
- Prefer configuration or tutorial fixes when working application behavior is already correct.
- Validate Compose after configuration edits and run focused checks through `uv run` after Python edits.
- Verify PromQL and LogQL against exported labels when the stack is available.
- Do not add tools solely to complete an unrelated task.
