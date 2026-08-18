#!/usr/bin/env python3

import os
import pickle
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from prometheus_api_client import PrometheusConnect

warnings.filterwarnings("ignore")

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
MODEL_PATH = Path(
    os.getenv(
        "AIOPS_ARTIFACT_DIR",
        str(Path(__file__).resolve().parents[1] / "artifacts"),
    )
) / "anomaly_model.pkl"

METRICS_QUERY = (
    '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
)

CHECK_INTERVAL = 30
LOOKBACK_MINUTES = 10


def load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            "Model not found. "
            "Run `uv run --group aiops python aiops/anomaly/train.py` first."
        )

    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)


def fetch_recent_metrics(prom):
    end_time = datetime.now()
    start_time = end_time - timedelta(
        minutes=LOOKBACK_MINUTES
    )

    result = prom.custom_query_range(
        query=METRICS_QUERY,
        start_time=start_time,
        end_time=end_time,
        step="10s",
    )

    if not result:
        raise ValueError(
            "No data returned from Prometheus"
        )

    timestamps = []
    values = []

    for sample in result[0]["values"]:
        timestamps.append(
            datetime.fromtimestamp(sample[0])
        )
        values.append(float(sample[1]))

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "cpu_usage": values,
        }
    )


def engineer_features(df):
    df["rolling_mean"] = (
        df["cpu_usage"]
        .rolling(window=5, min_periods=1)
        .mean()
    )

    df["rolling_std"] = (
        df["cpu_usage"]
        .rolling(window=5, min_periods=1)
        .std()
        .fillna(0)
    )

    df["rate_of_change"] = (
        df["cpu_usage"]
        .diff()
        .fillna(0)
    )

    df["hour"] = df["timestamp"].dt.hour

    return df.dropna()


def detect_anomalies(model, df):
    feature_columns = [
        "cpu_usage",
        "rolling_mean",
        "rolling_std",
        "rate_of_change",
        "hour",
    ]

    X = df[feature_columns]

    df["prediction"] = model.predict(X)
    df["anomaly_score"] = (
        model.decision_function(X)
    )

    df["is_anomaly"] = (
        df["prediction"] == -1
    )

    return df


def main():
    print("Loading model...")

    model = load_model()

    print("Connecting to Prometheus...")

    prom = PrometheusConnect(
        url=PROMETHEUS_URL,
        disable_ssl=True,
    )

    prom.check_prometheus_connection()

    while True:
        print(
            f"\nChecking at "
            f"{datetime.now():%Y-%m-%d %H:%M:%S}"
        )

        df = fetch_recent_metrics(prom)

        df = engineer_features(df)

        df = detect_anomalies(
            model,
            df,
        )

        anomalies = df[
            df["is_anomaly"]
        ]

        print(
            f"Samples: {len(df)} | "
            f"Anomalies: {len(anomalies)}"
        )

        if not anomalies.empty:
            print(
                anomalies[
                    [
                        "timestamp",
                        "cpu_usage",
                        "rolling_mean",
                        "rolling_std",
                        "rate_of_change",
                        "anomaly_score",
                    ]
                ].tail(10)
            )
        else:
            print("No anomalies detected.")

        print(
            f"Next check in "
            f"{CHECK_INTERVAL}s..."
        )

        time.sleep(
            CHECK_INTERVAL
        )


if __name__ == "__main__":
    main()
