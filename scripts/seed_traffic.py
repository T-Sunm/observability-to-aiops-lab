import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

READY_URLS = (
    "http://prometheus:9090/-/ready",
    "http://demo-app:8000/metrics/",
    "http://inventory-service:8000/metrics/",
    "http://payment-service:8000/metrics/",
)
CHECKOUT_URL = "http://demo-app:8000/checkout"


def request_status(url: str) -> int:
    try:
        with urlopen(url, timeout=2) as response:
            return response.status
    except HTTPError as error:
        return error.code


def wait_until_ready(url: str) -> None:
    for _ in range(30):
        try:
            if request_status(url) < 400:
                return
        except URLError:
            pass
        time.sleep(1)
    raise RuntimeError(f"Service did not become ready: {url}")


def send_checkout(url: str, expected_status: int) -> None:
    status = request_status(url)
    if status != expected_status:
        raise RuntimeError(f"Expected HTTP {expected_status} from {url}, got {status}")


def main() -> None:
    for url in READY_URLS:
        wait_until_ready(url)

    for _ in range(10):
        send_checkout(CHECKOUT_URL, 200)
        time.sleep(1)

    send_checkout(f"{CHECKOUT_URL}?force_error=true", 502)
    send_checkout(f"{CHECKOUT_URL}?payment_error=true", 502)
    print("Seeded 10 successful checkouts and 2 deterministic failures.")


if __name__ == "__main__":
    main()
