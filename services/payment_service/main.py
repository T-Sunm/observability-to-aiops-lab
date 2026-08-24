import asyncio
import json
import logging
import time
from datetime import UTC, datetime

from fastapi import FastAPI, Response
from opentelemetry import trace
from prometheus_client import Counter, Histogram, make_asgi_app

tracer = trace.get_tracer(__name__)
logger = logging.getLogger("payment-service")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def current_trace_fields():
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return {}

    return {
        "trace_id": format(span_context.trace_id, "032x"),
        "span_id": format(span_context.span_id, "016x"),
    }


def log_event(level, event, **fields):
    level_name = level.upper()
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": level_name,
        "service": "payment-service",
        "environment": "local",
        "service_version": "1.0.0",
        "event": event,
        **current_trace_fields(),
        **fields,
    }
    logger.log(getattr(logging, level_name), json.dumps(payload, separators=(",", ":")))


REQUEST_COUNT = Counter(
    "payment_requests_total",
    "Total number of payment HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "payment_request_latency_seconds",
    "Payment HTTP request latency in seconds",
    ["method", "endpoint"],
)

app = FastAPI()


@app.middleware("http")
async def collect_metrics(request, call_next):
    if request.url.path in {"/metrics", "/metrics/"}:
        return await call_next(request)

    start = time.time()
    response = await call_next(request)
    route = request.scope.get("route")
    endpoint = route.path if route else request.url.path

    REQUEST_LATENCY.labels(request.method, endpoint).observe(time.time() - start)
    REQUEST_COUNT.labels(request.method, endpoint, str(response.status_code)).inc()
    log_event(
        "info" if response.status_code < 500 else "error",
        "http_request",
        method=request.method,
        path=request.url.path,
        endpoint=endpoint,
        status_code=response.status_code,
        duration_ms=round((time.time() - start) * 1000, 2),
    )
    return response


@app.post("/payments/authorize")
async def authorize_payment(amount: float, force_error: bool = False):
    with tracer.start_as_current_span("payment.external_api.authorize") as span:
        span.set_attribute("dependency.type", "simulated_external_api")
        span.set_attribute("payment.amount", amount)
        await asyncio.sleep(0.15)

        if force_error:
            error = "Payment provider unavailable"
            span.record_exception(RuntimeError(error))
            log_event(
                "error",
                "external_api_unavailable",
                dependency="simulated-payment-provider",
                amount=amount,
            )
            return Response(error, status_code=503)

    return {"authorized": True, "amount": amount}


app.mount("/metrics", make_asgi_app())
