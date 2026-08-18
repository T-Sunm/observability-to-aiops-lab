# Observability to AIOps Lab

Hands-on lab for the Metrics, Logs, and Traces practices in [main.pdf](main.pdf), with a later AIOps extension based on the same Prometheus data.

## Quick start

```powershell
uv sync --group dev
docker compose up -d --build
docker compose ps
```

Open Grafana at http://localhost:3000 (`admin` / `grafana`), Prometheus at http://localhost:9090, Loki at http://localhost:3100/ready, Jaeger at http://localhost:16686, and Alloy at http://localhost:12345.

Stop the lab with:

```powershell
docker compose down
```

## Generate the checkout incident

Create baseline checkout traffic, then deterministic failures. Wait for two Prometheus scrapes before querying metrics.

```powershell
1..20 | ForEach-Object { curl.exe -s http://localhost:8001/checkout | Out-Null }
1..5 | ForEach-Object { curl.exe -s "http://localhost:8001/checkout?force_error=true" | Out-Null }
Start-Sleep -Seconds 15
```

`force_error=true` asks inventory for an impossible quantity. Inventory returns 409, `demo-app` returns 502, and both services emit correlated telemetry.

## Runtime query mapping

```promql
up{job="demo-app"}

sum(rate(app_requests_total{endpoint="/checkout"}[5m]))

sum(rate(app_requests_total{endpoint="/checkout",status=~"5.."}[5m]))
/
sum(rate(app_requests_total{endpoint="/checkout"}[5m]))

histogram_quantile(
  0.95,
  sum by (le) (
    rate(app_request_latency_seconds_bucket{endpoint="/checkout"}[5m])
  )
)
```

```logql
{source="docker", service="demo-app"} |= "ERROR"

{source="docker", service="demo-app"} | json | level="ERROR"

{source="docker", service="demo-app"}
| json
| event="inventory_returned_error"
```

Copy the resulting `trace_id` into Jaeger and inspect the `demo-app` and `inventory-service` spans.

## Checks

```powershell
uv run python -m unittest discover -s tests -v
uv run ruff check .
uv run ruff format --check .
docker compose config --quiet
```

## AIOps extensions

Install the optional AIOps group after the observability stack is collecting history:

```powershell
uv sync --group aiops
uv run --group aiops python aiops/anomaly/train.py
uv run --group aiops python aiops/anomaly/detect.py
uv run --group aiops python aiops/forecasting/train.py
uv run --group aiops python aiops/forecasting/forecast.py
```
