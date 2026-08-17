import logging
import json
import time
import random
from datetime import datetime
from flask import Flask, jsonify
from pythonjsonlogger import jsonlogger

app = Flask(__name__)


# Configure JSON logging
class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(
            log_record,
            record,
            message_dict
        )

        log_record["timestamp"] = datetime.utcnow().isoformat()
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["app"] = "sample-flask-app"


logger = logging.getLogger()

logHandler = logging.StreamHandler()

formatter = CustomJsonFormatter(
    "%(timestamp)s %(level)s %(name)s %(message)s"
)

logHandler.setFormatter(formatter)

logger.addHandler(logHandler)
logger.setLevel(logging.INFO)


# Simulate various log levels
LOG_MESSAGES = {
    "INFO": [
        "User logged in successfully",
        "API request processed",
        "Cache hit for key: session_{}",
        "Database query completed in {}ms",
        "Request routed to backend service",
        "Authentication token validated",
    ],

    "WARNING": [
        "API rate limit approaching for user_id: {}",
        "Database connection pool at 80% capacity",
        "Slow query detected: {}ms",
        "Memory usage above 75% threshold",
        "Retry attempt {} for failed operation",
    ],

    "ERROR": [
        "Failed to connect to database: connection timeout",
        "API authentication failed for token: invalid_token_{}",
        "Unexpected error in payment processing: {}",
        "Service dependency unavailable: external-api",
        "Data validation failed for request",
        "Failed to write to cache: Redis connection error",
    ]
}


@app.route("/")
def index():
    logger.info("Homepage accessed")

    return jsonify({
        "status": "healthy",
        "app": "sample-flask-app",
        "version": "1.0"
    })


@app.route("/generate-logs")
def generate_logs():
    """Generate a variety of log messages"""

    count = 0

    # Generate INFO logs (70%)
    for _ in range(7):
        msg = random.choice(LOG_MESSAGES["INFO"])

        if "{}" in msg:
            msg = msg.format(random.randint(1, 1000))

        logger.info(
            msg,
            extra={
                "request_id": f"req-{random.randint(1000, 9999)}"
            }
        )

        count += 1

    # Generate WARNING logs (20%)
    for _ in range(2):
        msg = random.choice(LOG_MESSAGES["WARNING"])

        if "{}" in msg:
            msg = msg.format(random.randint(100, 500))

        logger.warning(
            msg,
            extra={
                "request_id": f"req-{random.randint(1000, 9999)}"
            }
        )

        count += 1

    # Generate ERROR logs (10%)
    for _ in range(1):
        msg = random.choice(LOG_MESSAGES["ERROR"])

        if "{}" in msg:
            msg = msg.format(random.randint(1, 100))

        logger.error(
            msg,
            extra={
                "request_id": f"req-{random.randint(1000, 9999)}"
            }
        )

        count += 1

    return jsonify({
        "status": "success",
        "logs_generated": count,
        "message": "Check Loki for generated logs"
    })


@app.route("/health")
def health():
    logger.debug("Health check endpoint called")

    return jsonify({
        "status": "UP",
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route("/simulate-error")
def simulate_error():
    logger.error(
        "Simulated error occurred",
        extra={
            "error_code": "SIM_ERROR_500",
            "user_action": "checkout",
            "trace_id": f"trace-{random.randint(10000, 99999)}",
            "request_id": f"req-{random.randint(1000, 9999)}"
        }
    )

    return jsonify({
        "error": "Simulated error",
        "code": "SIM_ERROR_500"
    }), 500


@app.route("/simulate-warning")
def simulate_warning():
    logger.warning(
        "Performance degradation detected",
        extra={
            "response_time_ms": random.randint(1000, 5000),
            "threshold_ms": 1000,
            "service": "database",
            "request_id": f"req-{random.randint(1000, 9999)}"
        }
    )

    return jsonify({
        "warning": "Performance degradation detected",
        "check_logs": True
    })


if __name__ == "__main__":
    logger.info(
        "Sample Flask application starting...",
        extra={
            "port": 5000,
            "environment": "lab",
            "log_format": "json"
        }
    )

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )
