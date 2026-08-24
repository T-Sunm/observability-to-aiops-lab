# Observability to AIOps Lab

Hands-on lab for the Metrics, Logs, and Traces practices in [main.pdf](main.pdf), with a later AIOps extension based on the same Prometheus data.

## Quick start

```powershell
uv sync --group dev
docker compose up -d --build
docker compose ps -a
```

`seed-traffic` waits for the lab services, then sends 10 successful checkout requests plus one deterministic Inventory failure and one Payment failure. It exits with status `0` when the starter telemetry is ready. Wait about 20 seconds before opening the query UIs so Prometheus can scrape the changing counters.

Open Grafana at http://localhost:3000 (`admin` / `grafana`), Prometheus at http://localhost:9090, Loki at http://localhost:3100/ready, Jaeger at http://localhost:16686, and Alloy at http://localhost:12345.

Stop the lab with:

```powershell
docker compose down
```

## Generate additional checkout traffic

Create baseline checkout traffic, then deterministic failures. Wait for two Prometheus scrapes before querying metrics.

```powershell
1..20 | ForEach-Object { curl.exe -s http://localhost:8001/checkout | Out-Null }
1..5 | ForEach-Object { curl.exe -s "http://localhost:8001/checkout?force_error=true" | Out-Null }
Start-Sleep -Seconds 15
```

`force_error=true` asks inventory for an impossible quantity. Inventory returns 409, `demo-app` returns 502, and both services emit correlated telemetry.

To simulate an external payment-provider failure after inventory succeeds:

```powershell
curl.exe -s "http://localhost:8001/checkout?payment_error=true"
```

`payment-service` returns 503 from its simulated external API, then `demo-app` returns 502. The trace contains the `inventory.database.query` and `payment.external_api.authorize` spans without requiring a database or external API.

## Runtime query mapping

```promql
up{job="demo-app"}

up{job="payment-service"}

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
