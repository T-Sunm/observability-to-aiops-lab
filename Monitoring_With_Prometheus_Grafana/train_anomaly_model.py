#!/root/monitoring/scripts/venv/bin/python3

import os
import pickle
import warnings
from datetime import datetime, timedelta

import pandas as pd
from sklearn.ensemble import IsolationForest
from prometheus_api_client import PrometheusConnect

warnings.filterwarnings("ignore")

PROMETHEUS_URL = "http://localhost:9090"
MODEL_PATH = "/root/monitoring/anomaly_model.pkl"

METRICS_QUERY = (
    '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'
)

TRAINING_HOURS = 1
CONTAMINATION = 0.1
MIN_SAMPLES_REQUIRED = 15


def fetch_cpu_metrics(prom, hours):
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)

    result = prom.custom_query_range(
        query=METRICS_QUERY,
        start_time=start_time,
        end_time=end_time,
        step="10s",
    )

    if not result:
        raise ValueError(
            "No data returned from Prometheus. "
            "Ensure Node Exporter is running."
        )

    timestamps = []
    values = []

    for sample in result[0]["values"]:
        timestamps.append(datetime.fromtimestamp(sample[0]))
        values.append(float(sample[1]))

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "cpu_usage": values,
        }
    )


def engineer_features(df):
    # 5 samples × 10 seconds = ~50 second window
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


def train_model(df):
    feature_columns = [
        "cpu_usage",
        "rolling_mean",
        "rolling_std",
        "rate_of_change",
        "hour",
    ]

    X = df[feature_columns]

    model = IsolationForest(
        contamination=CONTAMINATION,
        random_state=42,
        n_estimators=100,
        max_samples="auto",
    )

    model.fit(X)

    predictions = model.predict(X)

    normal = (predictions == 1).sum()
    anomalies = (predictions == -1).sum()

    print(f"Normal: {normal}")
    print(f"Anomalies: {anomalies}")

    return model


def main():
    print("Connecting to Prometheus...")

    prom = PrometheusConnect(
        url=PROMETHEUS_URL,
        disable_ssl=True,
    )

    prom.check_prometheus_connection()

    print("Fetching CPU metrics...")

    df = fetch_cpu_metrics(
        prom,
        TRAINING_HOURS,
    )

    print(f"Fetched {len(df)} samples")

    if len(df) < MIN_SAMPLES_REQUIRED:
        print(
            f"Not enough data. Need at least "
            f"{MIN_SAMPLES_REQUIRED} samples."
        )
        return

    print("Engineering features...")

    df = engineer_features(df)

    print("Training Isolation Forest...")

    model = train_model(df)

    print("Saving model...")

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    print(f"Model saved to: {MODEL_PATH}")


if __name__ == "__main__":
    main()