#!/usr/bin/env python3
"""
AI-Driven Forecasting - Prediction Script
Module 5: AIOps Foundations

This script uses trained Prophet models to generate forecasts
for infrastructure metrics and predict capacity exhaustion dates
for proactive planning.
"""

import os
import sys
from datetime import datetime, timedelta
import warnings
import logging

warnings.filterwarnings('ignore')
logging.getLogger('prophet').setLevel(logging.ERROR)
logging.getLogger('cmdstanpy').setLevel(logging.ERROR)

try:
    import pandas as pd
    import numpy as np
    from prometheus_api_client import PrometheusConnect
    import pickle
    from prophet import Prophet

except ImportError as e:
    print(
        f"Error: Missing required package: {e}"
    )

    print(
        "\nPlease install packages:"
    )

    print(
        "   pip install -r requirements.txt"
    )

    sys.exit(1)


PROMETHEUS_URL = "http://localhost:9090"

MODEL_DIR = (
    "/root/monitoring/forecasting_models"
)


METRICS_CONFIG = {

    'cpu_usage': {
        'name': 'CPU Usage',
        'unit': '%',
        'threshold': 80,
        'threshold_type': 'upper',
        'format': '.1f'
    },

    'memory_available': {
        'name': 'Memory Available',
        'unit': 'GB',
        'threshold': 3.0,
        'threshold_type': 'lower',
        'format': '.2f'
    },

    'disk_usage': {
        'name': 'Disk Usage',
        'unit': '%',
        'threshold': 90,
        'threshold_type': 'upper',
        'format': '.1f'
    }
}


def print_header():
    """Print script header."""

    print(
        "\n" + "=" * 70
    )

    print(
        "AI-Driven Forecasting - Generate Predictions"
    )

    print(
        "Module 5: AIOps Foundations"
    )

    print(
        "=" * 70 + "\n"
    )


def connect_to_prometheus():
    """Connect to Prometheus API."""

    try:
        prom = PrometheusConnect(
            url=PROMETHEUS_URL,
            disable_ssl=True
        )

        prom.check_prometheus_connection()

        return prom

    except Exception as e:

        print(
            "Warning: Could not connect "
            f"to Prometheus: {e}"
        )

        return None


def get_current_value(
    prom,
    metric_key
):
    """Fetch current metric value from Prometheus."""

    if prom is None:
        return None

    try:
        query = None

        if metric_key == 'cpu_usage':

            query = (
                '100 - (avg(rate('
                'node_cpu_seconds_total'
                '{mode="idle"}[5m])) * 100)'
            )

        elif metric_key == 'memory_available':

            query = (
                'node_memory_MemAvailable_bytes '
                '/ 1024 / 1024 / 1024'
            )

        elif metric_key == 'disk_usage':

            query = (
                '(1 - '
                'node_filesystem_avail_bytes'
                '{fstype=~"ext4|xfs|btrfs"} '
                '/ '
                'node_filesystem_size_bytes'
                '{fstype=~"ext4|xfs|btrfs"}) '
                '* 100'
            )

        if query is None:
            return None

        result = prom.custom_query(
            query=query
        )

        if result and len(result) > 0:

            value = float(
                result[0]['value'][1]
            )

            return value

        return None

    except Exception as e:

        print(
            "Warning: Could not fetch "
            f"current value for {metric_key}: {e}"
        )

        return None


def load_model(metric_key):
    """Load trained model from disk."""

    model_path = os.path.join(
        MODEL_DIR,
        f"{metric_key}_forecast_model.pkl"
    )

    if not os.path.exists(model_path):
        return None

    try:

        with open(model_path, 'rb') as f:
            model = pickle.load(f)

        return model

    except Exception as e:

        print(
            f"Error loading model "
            f"for {metric_key}: {e}"
        )

        return None


def generate_forecast(
    model,
    metric_key,
    periods=7
):
    """Generate forecast for specified number of days."""

    try:

        # Number of 30-second intervals
        future_periods = (
            periods
            * 24
            * 60
            * 2
        )

        future = model.make_future_dataframe(
            periods=future_periods,
            freq='30S'
        )

        # Logistic growth requires cap/floor
        if (
            hasattr(model, 'growth')
            and model.growth == 'logistic'
        ):

            future['cap'] = 100.0

            if metric_key == 'cpu_usage':
                future['floor'] = 1.0
            else:
                future['floor'] = 0.0

        forecast = model.predict(
            future
        )

        return forecast

    except AttributeError as e:

        if 'stan_backend' in str(e):

            print(
                "Warning: Prophet stan_backend "
                "deprecation issue"
            )

            return None

        print(
            f"Error generating forecast: {e}"
        )

        import traceback
        traceback.print_exc()

        return None

    except Exception as e:

        print(
            f"Error generating forecast: {e}"
        )

        import traceback
        traceback.print_exc()

        return None


def analyze_forecast(
    forecast,
    config,
    current_value,
    periods=7
):
    """
    Analyze forecast results
    and identify capacity issues.
    """

    future_points = (
        periods
        * 24
        * 60
        * 2
    )

    # Only future period
    forecast_period = forecast.tail(
        future_points
    )

    forecast_mean = (
        forecast_period['yhat'].mean()
    )

    forecast_max = (
        forecast_period['yhat'].max()
    )

    forecast_min = (
        forecast_period['yhat'].min()
    )

    trend_start = (
        forecast_period['yhat'].iloc[0]
    )

    trend_end = (
        forecast_period['yhat'].iloc[-1]
    )

    trend_change = (
        trend_end - trend_start
    )

    trend_per_day = (
        trend_change / periods
    )

    ci_width = (
        forecast_period['yhat_upper']
        - forecast_period['yhat_lower']
    ).mean()

    threshold = config['threshold']

    threshold_type = (
        config['threshold_type']
    )

    days_to_threshold = None
    threshold_breached = False

    if threshold_type == 'upper':

        breach_df = forecast_period[
            forecast_period['yhat']
            > threshold
        ]

        if not breach_df.empty:

            threshold_breached = True

            first_breach_pos = (
                breach_df.index.get_loc(
                    breach_df.index[0]
                )
            )

            forecast_start_pos = (
                forecast_period.index.get_loc(
                    forecast_period.index[0]
                )
            )

            points_to_breach = (
                first_breach_pos
                - forecast_start_pos
            )

            days_to_threshold = (
                points_to_breach
                * 30
            ) / (
                24 * 60 * 60
            )

    elif threshold_type == 'lower':

        breach_df = forecast_period[
            forecast_period['yhat']
            < threshold
        ]

        if not breach_df.empty:

            threshold_breached = True

            first_breach_pos = (
                breach_df.index.get_loc(
                    breach_df.index[0]
                )
            )

            forecast_start_pos = (
                forecast_period.index.get_loc(
                    forecast_period.index[0]
                )
            )

            points_to_breach = (
                first_breach_pos
                - forecast_start_pos
            )

            days_to_threshold = (
                points_to_breach
                * 30
            ) / (
                24 * 60 * 60
            )

    return {

        'current_value':
            current_value,

        'forecast_mean':
            forecast_mean,

        'forecast_max':
            forecast_max,

        'forecast_min':
            forecast_min,

        'trend_per_day':
            trend_per_day,

        'ci_width':
            ci_width,

        'threshold_breached':
            threshold_breached,

        'days_to_threshold':
            days_to_threshold
    }


def print_forecast_report(
    metric_key,
    config,
    analysis,
    periods
):
    """Print forecast report."""

    fmt = config['format']
    unit = config['unit']

    print(
        f"\n{config['name']} Forecast:"
    )

    print(
        f"  Current: "
        f"{analysis['current_value']:{fmt}}"
        f"{unit}"
    )

    forecast_range = (
        f"{analysis['forecast_min']:{fmt}}"
        f"{unit} - "
        f"{analysis['forecast_max']:{fmt}}"
        f"{unit}"
    )

    print(
        f"  {periods}-day prediction: "
        f"{analysis['forecast_mean']:{fmt}}"
        f"{unit} "
        f"(range: {forecast_range})"
    )

    trend = analysis['trend_per_day']

    if abs(trend) > 0.01:

        direction = (
            "Increasing"
            if trend > 0
            else "Decreasing"
        )

        total_change = (
            trend * periods
        )

        print(
            f"  Trend: {direction} "
            f"({total_change:+{fmt}}"
            f"{unit} over {periods} days, "
            f"{trend:+{fmt}}"
            f"{unit}/day)"
        )

    else:

        print(
            "  Trend: Stable "
            "(minimal change)"
        )

    threshold = config['threshold']

    threshold_type = (
        config['threshold_type']
    )

    if analysis['threshold_breached']:

        days = analysis[
            'days_to_threshold'
        ]

        if threshold_type == 'upper':

            threshold_msg = (
                f"will exceed "
                f"{threshold}{unit}"
            )

        else:

            threshold_msg = (
                f"will drop below "
                f"{threshold}{unit}"
            )

        if days < 7:
            urgency = "CRITICAL"
        elif days < 14:
            urgency = "WARNING"
        else:
            urgency = "INFO"

        print(
            f"  Alert: [{urgency}] "
            f"{config['name']} "
            f"{threshold_msg} "
            f"in ~{days:.1f} days"
        )

        if metric_key == 'disk_usage':

            recommendation = (
                "Plan storage expansion "
                "or cleanup"
            )

        elif metric_key == 'cpu_usage':

            recommendation = (
                "Consider scaling up "
                "or optimizing workloads"
            )

        elif metric_key == 'memory_available':

            recommendation = (
                "Investigate memory leaks "
                "or add more RAM"
            )

        else:

            recommendation = (
                "Review capacity planning"
            )

        print(
            f"  Recommendation: "
            f"{recommendation}"
        )

    else:

        if threshold_type == 'upper':

            status_msg = (
                f"will not exceed "
                f"{threshold}{unit}"
            )

        else:

            status_msg = (
                f"will not drop below "
                f"{threshold}{unit}"
            )

        print(
            f"  Status: "
            f"{config['name']} "
            f"{status_msg} "
            f"within {periods} days"
        )

        print(
            "  Recommendation: "
            "Monitor trend, "
            "no immediate action needed"
        )


def prompt_forecast_horizon():
    """Ask user for forecast horizon."""

    print(
        "Select forecast horizon:"
    )

    print(
        "   1) 7 days "
        "(recommended for short-term planning)"
    )

    print(
        "   2) 14 days "
        "(recommended for capacity orders)"
    )

    print(
        "   3) 30 days "
        "(recommended for quarterly planning)"
    )

    print(
        "   4) Custom"
    )

    while True:

        try:

            choice = input(
                "\nEnter choice (1-4): "
            ).strip()

            if choice == '1':

                return 7

            elif choice == '2':

                return 14

            elif choice == '3':

                return 30

            elif choice == '4':

                days = input(
                    "Enter number of days (1-90): "
                ).strip()

                days = int(days)

                if 1 <= days <= 90:

                    return days

                print(
                    "Please enter a value "
                    "between 1 and 90"
                )

            else:

                print(
                    "Invalid choice, "
                    "please enter 1-4"
                )

        except (
            ValueError,
            KeyboardInterrupt
        ):

            print(
                "\nInvalid input, "
                "using default: 7 days"
            )

            return 7


def main():
    """Main forecasting workflow."""

    print_header()

    if not os.path.exists(MODEL_DIR):

        print(
            f"Model directory not found: "
            f"{MODEL_DIR}"
        )

        print(
            "\nPlease train models first:"
        )

        print(
            "   python3 "
            "/root/monitoring/scripts/"
            "train_forecasting_model.py"
        )

        sys.exit(1)

    print(
        "Loading trained models..."
    )

    models = {}

    for metric_key, config in METRICS_CONFIG.items():

        model = load_model(
            metric_key
        )

        if model:

            models[metric_key] = model

            print(
                f"   Loaded model for "
                f"{config['name']}"
            )

        else:

            print(
                f"   Model not found for "
                f"{config['name']}"
            )

    if not models:

        print(
            "\nNo trained models found!"
        )

        print(
            "Please train models first:"
        )

        print(
            "   python3 "
            "/root/monitoring/scripts/"
            "train_forecasting_model.py"
        )

        sys.exit(1)

    print(
        f"\nLoaded "
        f"{len(models)} model(s)\n"
    )

    print(
        "Connecting to Prometheus..."
    )

    prom = connect_to_prometheus()

    if prom:

        print(
            "Connected to Prometheus\n"
        )

    else:

        print(
            "Could not connect to Prometheus - "
            "will use training end values\n"
        )

    periods = prompt_forecast_horizon()

    print(
        f"\nGenerating "
        f"{periods}-day forecasts...\n"
    )

    forecast_results = {}

    for metric_key, model in models.items():

        config = (
            METRICS_CONFIG[metric_key]
        )

        print(
            f"Processing "
            f"{config['name']}..."
        )

        current_value = get_current_value(
            prom,
            metric_key
        )

        if current_value is None:

            print(
                "   Could not fetch current value, "
                "using training end value"
            )

            temp_forecast = (
                generate_forecast(
                    model,
                    metric_key,
                    periods=1
                )
            )

            if temp_forecast is not None:

                future_points = (
                    1
                    * 24
                    * 60
                    * 2
                )

                current_value = (
                    temp_forecast.iloc[
                        -(future_points + 1)
                    ]['yhat']
                )

            else:

                print(
                    f"   Failed to get current value "
                    f"for {config['name']}"
                )

                continue

        forecast = generate_forecast(
            model,
            metric_key,
            periods=periods
        )

        if forecast is None:

            print(
                f"   Failed to generate forecast "
                f"for {config['name']}"
            )

            continue

        analysis = analyze_forecast(
            forecast,
            config,
            current_value,
            periods=periods
        )

        forecast_results[
            metric_key
        ] = {

            'forecast':
                forecast,

            'analysis':
                analysis
        }

        print(
            f"   Forecast generated for "
            f"{config['name']}"
        )

    print(
        "\n" + "=" * 70
    )

    print(
        f"{periods}-Day Forecast Results"
    )

    print(
        "=" * 70
    )

    for (
        metric_key,
        results
    ) in forecast_results.items():

        config = (
            METRICS_CONFIG[metric_key]
        )

        print_forecast_report(
            metric_key,
            config,
            results['analysis'],
            periods
        )

    print(
        "\n" + "=" * 70
    )

    print(
        "Summary"
    )

    print(
        "=" * 70
    )

    alerts = []
    ok_metrics = []

    for (
        metric_key,
        results
    ) in forecast_results.items():

        config = (
            METRICS_CONFIG[metric_key]
        )

        analysis = (
            results['analysis']
        )

        if analysis[
            'threshold_breached'
        ]:

            alerts.append({

                'metric':
                    config['name'],

                'days':
                    analysis[
                        'days_to_threshold'
                    ]
            })

        else:

            ok_metrics.append(
                config['name']
            )

    if alerts:

        print(
            f"\nCapacity Alerts "
            f"({len(alerts)}):"
        )

        alerts.sort(
            key=lambda x: x['days']
        )

        for alert in alerts:

            if alert['days'] < 7:
                urgency = "CRITICAL"
            elif alert['days'] < 14:
                urgency = "WARNING"
            else:
                urgency = "INFO"

            print(
                f"  [{urgency}] "
                f"{alert['metric']}: "
                f"Action needed in "
                f"~{alert['days']:.1f} days"
            )

    if ok_metrics:

        print(
            f"\nHealthy Metrics "
            f"({len(ok_metrics)}):"
        )

        for metric in ok_metrics:

            print(
                f"  {metric}"
            )

    print(
        "\n" + "=" * 70
    )

    print(
        "Forecast generation complete!"
    )

    print(
        "\nNext Steps:"
    )

    print(
        "  - Review forecasts weekly "
        "and retrain models monthly"
    )

    print(
        "  - Compare predictions "
        "to actual values "
        "to validate accuracy"
    )

    print(
        "  - View detailed metrics "
        "in Grafana dashboard"
    )

    print(
        "=" * 70 + "\n"
    )


if __name__ == "__main__":
    main()