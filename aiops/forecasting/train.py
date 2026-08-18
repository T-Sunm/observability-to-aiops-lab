#!/usr/bin/env python3
"""
AI-Driven Forecasting - Model Training Script
Module 5: AIOps Foundations

This script trains Prophet time-series forecasting models on historical
metrics from Prometheus. It learns trends and seasonal patterns to enable
proactive capacity planning.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import warnings
import logging

# Suppress warnings and logging
warnings.filterwarnings('ignore')
logging.getLogger('prophet').setLevel(logging.ERROR)
logging.getLogger('cmdstanpy').setLevel(logging.ERROR)

try:
    import pandas as pd
    import numpy as np
    from prometheus_api_client import PrometheusConnect
    import pickle

    # Import Prophet and let it initialize cmdstan
    from prophet import Prophet

except ImportError as e:
    print(f"Error: Missing required package: {e}")
    print("\nPlease install packages:")
    print("   uv sync --group aiops")
    sys.exit(1)


# Configuration
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
MODEL_DIR = Path(
    os.getenv(
        "AIOPS_ARTIFACT_DIR",
        str(Path(__file__).resolve().parents[1] / "artifacts"),
    )
) / "forecasting_models"
TRAINING_HOURS = 1
MIN_DATA_POINTS = 20


# Metrics to forecast
METRICS_CONFIG = {
    'cpu_usage': {
        'query': '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
        'name': 'CPU Usage (%)',
        'threshold': 80,
        'unit': '%'
    },
    'memory_available': {
        'query': 'node_memory_MemAvailable_bytes / 1024 / 1024 / 1024',
        'name': 'Memory Available (GB)',
        'threshold': 3,
        'unit': 'GB',
        'inverse': True
    },
    'disk_usage': {
        'query': '(1 - node_filesystem_avail_bytes{fstype=~"ext4|xfs|btrfs"} / node_filesystem_size_bytes{fstype=~"ext4|xfs|btrfs"}) * 100',
        'name': 'Disk Usage (%)',
        'threshold': 90,
        'unit': '%'
    }
}


def print_header():
    """Print script header."""
    print("\n" + "=" * 70)
    print("AI-Driven Forecasting - Model Training")
    print("Module 5: AIOps Foundations")
    print("=" * 70 + "\n")


def connect_to_prometheus():
    """Connect to Prometheus API."""
    try:
        print(f"Connecting to Prometheus at {PROMETHEUS_URL}...")

        prom = PrometheusConnect(
            url=PROMETHEUS_URL,
            disable_ssl=True
        )

        prom.check_prometheus_connection()

        print("Connected to Prometheus successfully\n")

        return prom

    except Exception as e:
        print(f"Error connecting to Prometheus: {e}")
        print("Make sure Prometheus is running: docker compose ps")
        sys.exit(1)


def fetch_metric_data(prom, metric_name, query, hours=1):
    """Fetch historical metric data from Prometheus."""
    try:
        print(f"Fetching {metric_name} data...")

        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        # Use 30-second resolution for lab environment
        result = prom.custom_query_range(
            query=query,
            start_time=start_time,
            end_time=end_time,
            step='30s'
        )

        if not result or len(result) == 0:
            print(f"No data returned for {metric_name}")
            return None

        values = result[0]['values']

        if len(values) < MIN_DATA_POINTS:
            print(
                f"Insufficient data for {metric_name}: "
                f"{len(values)} points"
            )
            print(
                f"Need at least {MIN_DATA_POINTS} points"
            )
            print(
                "Tip: Wait longer or check Prometheus "
                "is collecting metrics"
            )
            return None

        # Convert to DataFrame
        df = pd.DataFrame(
            values,
            columns=['timestamp', 'value']
        )

        df['timestamp'] = pd.to_datetime(
            df['timestamp'],
            unit='s'
        )

        df['value'] = pd.to_numeric(
            df['value'],
            errors='coerce'
        )

        # Remove NaN values
        df = df.dropna()

        if len(df) < MIN_DATA_POINTS:
            print(
                "Insufficient valid data after cleaning: "
                f"{len(df)} points"
            )
            return None

        print(
            f"Fetched {len(df)} data points "
            f"for {metric_name}"
        )

        print(
            f"Time range: "
            f"{df['timestamp'].min()} "
            f"to {df['timestamp'].max()}"
        )

        print(
            f"Current value: "
            f"{df['value'].iloc[-1]:.2f}"
        )

        print(
            f"Mean: {df['value'].mean():.2f}, "
            f"Std: {df['value'].std():.2f}"
        )

        # Lab warning for limited data
        if len(df) < 500:
            data_hours = len(df) * 30 / 3600

            print(
                f"\nLab Environment Note: "
                f"Only {len(df)} data points available "
                f"(~{data_hours:.1f} hours of data)."
            )

            print(
                "Prophet requires 2+ weeks "
                "for seasonality learning:"
            )

            print(
                "  Daily patterns: "
                "Need 2+ days of data"
            )

            print(
                "  Weekly patterns: "
                "Need 2+ weeks of data"
            )

            print(
                "  Strong trend detection: "
                "Need 1+ week of stable data"
            )

            print(
                "\nUsing simplified model "
                "for lab demonstration:"
            )

            print(
                "  growth='logistic' for % metrics "
                "(bounded 0-100%)"
            )

            print(
                "  growth='linear' for other metrics"
            )

            print(
                "  seasonality disabled "
                "(insufficient data)"
            )

            print(
                "  30-second intervals "
                "(reduced memory usage)"
            )

            print(
                "  3 changepoints max"
            )

            print(
                "\nFor production: "
                "Collect 2+ weeks of data "
                "@ 10s intervals, then:"
            )

            print(
                "  daily_seasonality=True, "
                "weekly_seasonality=True"
            )

            print(
                "  changepoint_prior_scale=0.05"
            )

            print(
                "  n_changepoints=25"
            )

            print(
                "Continuing with available data...\n"
            )

        return df

    except Exception as e:
        print(
            f"Error fetching {metric_name}: {e}"
        )
        return None


def prepare_prophet_data(
    df,
    metric_config,
    metric_key
):
    """
    Convert DataFrame to Prophet format
    (ds, y) with optional cap/floor.
    """

    prophet_df = pd.DataFrame({
        'ds': df['timestamp'],
        'y': df['value']
    })

    # Percentage metrics get logistic bounds
    if metric_config.get('unit') == '%':
        prophet_df['cap'] = 100.0

        if metric_key == 'cpu_usage':
            prophet_df['floor'] = 1.0
        else:
            prophet_df['floor'] = 0.0

    return prophet_df


def train_prophet_model(
    df,
    metric_name,
    metric_config,
    metric_key
):
    """Train Prophet model on historical data."""

    try:
        print(
            f"\nTraining forecasting model "
            f"for {metric_name}..."
        )

        prophet_df = prepare_prophet_data(
            df,
            metric_config,
            metric_key
        )

        # Percentage metrics use logistic growth
        is_percentage = (
            metric_config.get('unit') == '%'
        )

        growth_type = (
            'logistic'
            if is_percentage
            else 'linear'
        )

        model = Prophet(
            growth=growth_type,
            daily_seasonality=False,
            weekly_seasonality=False,
            yearly_seasonality=False,
            n_changepoints=3,
            changepoint_prior_scale=0.001,
            interval_width=0.95,
            mcmc_samples=0,
            uncertainty_samples=100
        )

        print(
            f"Training on "
            f"{len(prophet_df)} data points..."
        )

        try:
            model.fit(prophet_df)

        except AttributeError as e:
            if 'stan_backend' in str(e):
                print(
                    "Warning: Prophet stan_backend "
                    "deprecation issue "
                    "(continuing anyway)"
                )
                pass
            else:
                print(
                    f"Error during model.fit(): {e}"
                )

                import traceback
                traceback.print_exc()

                return None

        except Exception as e:
            print(
                f"Error during model.fit(): {e}"
            )

            import traceback
            traceback.print_exc()

            return None

        if (
            not hasattr(model, 'params')
            or model.params is None
        ):
            print(
                f"Model training failed "
                f"for {metric_name}: "
                "model.params is None"
            )

            print(
                "This usually means cmdstan "
                "is not installed or working properly"
            )

            print(
                "Try: uv run --group aiops python -c "
                "\"from cmdstanpy import install_cmdstan; install_cmdstan()\""
            )

            return None

        print(
            f"Model trained successfully "
            f"for {metric_name}"
        )

        data_mean = prophet_df['y'].mean()
        data_std = prophet_df['y'].std()
        data_min = prophet_df['y'].min()
        data_max = prophet_df['y'].max()

        data_start = prophet_df['y'].iloc[0]
        data_end = prophet_df['y'].iloc[-1]

        trend = data_end - data_start

        print(
            f"Learned baseline: "
            f"mean={data_mean:.2f}, "
            f"std={data_std:.2f}"
        )

        print(
            f"Value range: "
            f"[{data_min:.2f}, {data_max:.2f}]"
        )

        print(
            f"Observed trend: "
            f"{trend:+.2f} "
            f"(from {data_start:.2f} "
            f"to {data_end:.2f})"
        )

        if is_percentage:
            print(
                "Model type: Logistic growth "
                "(bounded 0-100%)"
            )
        else:
            print(
                "Model type: Linear growth "
                "(restricted by "
                "changepoint_prior=0.001)"
            )

        return model

    except Exception as e:
        print(
            f"Error training model "
            f"for {metric_name}: {e}"
        )

        return None


def save_model(model, metric_key):
    """Save trained model to disk."""

    try:
        os.makedirs(
            MODEL_DIR,
            exist_ok=True
        )

        model_path = os.path.join(
            MODEL_DIR,
            f"{metric_key}_forecast_model.pkl"
        )

        with open(model_path, 'wb') as f:
            pickle.dump(model, f)

        print(
            f"Model saved: {model_path}"
        )

        return model_path

    except Exception as e:
        print(
            f"Error saving model: {e}"
        )

        return None


def main():
    """Main training workflow."""

    print_header()

    prom = connect_to_prometheus()

    trained_models = {}
    failed_metrics = []

    for metric_key, config in METRICS_CONFIG.items():

        print("\n" + "-" * 70)

        df = fetch_metric_data(
            prom,
            config['name'],
            config['query'],
            hours=TRAINING_HOURS
        )

        if df is None:
            failed_metrics.append(metric_key)
            continue

        model = train_prophet_model(
            df,
            config['name'],
            config,
            metric_key
        )

        if model is None:
            failed_metrics.append(metric_key)
            continue

        model_path = save_model(
            model,
            metric_key
        )

        if model_path:
            trained_models[metric_key] = {
                'model_path': model_path,
                'name': config['name'],
                'data_points': len(df)
            }

    print("\n" + "=" * 70)
    print("Training Summary")
    print("=" * 70)

    if trained_models:
        print(
            f"\nSuccessfully trained "
            f"{len(trained_models)} model(s):\n"
        )

        for metric_key, info in trained_models.items():

            print(
                f"   {info['name']}"
            )

            print(
                f"     Model: "
                f"{info['model_path']}"
            )

            print(
                f"     Training data: "
                f"{info['data_points']} points"
            )

    if failed_metrics:

        print(
            f"\nFailed to train "
            f"{len(failed_metrics)} model(s):"
        )

        for metric_key in failed_metrics:
            print(
                f"   "
                f"{METRICS_CONFIG[metric_key]['name']}"
            )

        print("\nCommon issues:")

        print(
            f"   - Insufficient historical data "
            f"(need {MIN_DATA_POINTS}+ points)"
        )

        print(
            "   - Prometheus not collecting metrics"
        )

        print(
            "   - Data quality issues "
            "(all NaN values)"
        )

        print(
            "\nTry waiting longer or check: "
            "docker compose logs prometheus"
        )

    if trained_models:

        print(
            "\nModels are ready for forecasting!"
        )

        print(
            "\nNext step: Generate forecasts"
        )

        print(
            "   uv run --group aiops python aiops/forecasting/forecast.py"
        )

    else:

        print(
            "\nNo models were trained successfully"
        )

        print(
            "Please resolve the issues above "
            "and try again"
        )

        sys.exit(1)

    print(
        "\n" + "=" * 70 + "\n"
    )


if __name__ == "__main__":
    main()
