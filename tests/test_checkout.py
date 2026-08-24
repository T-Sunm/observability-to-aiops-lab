import unittest
from typing import Self
from unittest.mock import patch

import httpx
from fastapi.responses import JSONResponse

from services.demo_app import main
from services.payment_service import main as payment_main


class FakeResponse:
    status_code = 409

    def raise_for_status(self) -> None:
        request = httpx.Request(
            "GET", "http://inventory-service:8000/inventory/sku-123"
        )
        raise httpx.HTTPStatusError("stock conflict", request=request, response=self)


class FakeAsyncClient:
    request_params: dict[str, int] | None = None

    def __init__(self, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None

    async def get(self, url: str, *, params: dict[str, int]) -> FakeResponse:
        type(self).request_params = params
        return FakeResponse()


class CheckoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_force_error_uses_an_impossible_inventory_quantity(self) -> None:
        with patch.object(main.httpx, "AsyncClient", FakeAsyncClient):
            response = await main.checkout(force_error=True)

        self.assertIsInstance(response, JSONResponse)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(FakeAsyncClient.request_params, {"quantity": 999})

    async def test_payment_error_returns_service_unavailable(self) -> None:
        response = await payment_main.authorize_payment(19.99, force_error=True)

        self.assertEqual(response.status_code, 503)
