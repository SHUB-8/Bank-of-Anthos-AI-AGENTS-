# GENERATED: Orchestrator - produced by Gemini CLI. Do not include mock or dummy data in production code.

import os
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from middleware import get_logger
from schemas import (
    AnomalyCheckRequest, AnomalyCheckResponse,
    TransactionExecuteRequest, TransactionExecuteResponse,
    ContactResolveRequest, ContactResolveResponse
)

load_dotenv()

HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT_SECONDS", 10))
HTTP_RETRY_ATTEMPTS = int(os.getenv("HTTP_RETRY_ATTEMPTS", 3))

# --- Base Client with Retries ---

class BaseClient:
    def __init__(self, base_url: str, service_name: str):
        self.base_url = base_url
        self.service_name = service_name
        self.client = httpx.AsyncClient(http2=True, timeout=HTTP_TIMEOUT)

    def _get_headers(self, correlation_id: str, token: str, idempotency_key: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "X-Correlation-ID": correlation_id,
            "Authorization": f"Bearer {token}"
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    @retry(
        stop=stop_after_attempt(HTTP_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError)),
    )
    async def _request(self, method: str, url: str, headers: Dict[str, str], json: Optional[Dict] = None, params: Optional[Dict] = None):
        logger = get_logger(headers.get("X-Correlation-ID"))
        logger.info(f"Calling {self.service_name}: {method} {url}")
        # Note: The original Authorization header is passed through directly.
        response = await self.client.request(method, f"{self.base_url}{url}", headers=headers, json=json, params=params)
        response.raise_for_status() # Will raise HTTPStatusError for 4xx/5xx
        return response.json()

# --- Typed Clients ---

class AnomalySageClient(BaseClient):
    def __init__(self):
        super().__init__(os.getenv("ANOMALY_SAGE_URL"), "Anomaly-Sage")

    async def check_risk(self, request: AnomalyCheckRequest, correlation_id: str, token: str) -> AnomalyCheckResponse:
        headers = self._get_headers(correlation_id, token)
        response_json = await self._request("POST", "/v1/anomaly/check", headers, json=request.model_dump())
        return AnomalyCheckResponse(**response_json)

    async def confirm_transaction(self, confirmation_id: str, correlation_id: str, token: str) -> Dict[str, Any]:
        headers = self._get_headers(correlation_id, token)
        return await self._request("POST", f"/v1/anomaly/confirm/{confirmation_id}", headers)

class TransactionSageClient(BaseClient):
    def __init__(self):
        super().__init__(os.getenv("TRANSACTION_SAGE_URL"), "Transaction-Sage")

    async def execute_transaction(self, request: TransactionExecuteRequest, correlation_id: str, idempotency_key: str, token: str) -> TransactionExecuteResponse:
        headers = self._get_headers(correlation_id, token, idempotency_key)
        response_json = await self._request("POST", "/v1/transactions/execute", headers, json=request.model_dump())
        return TransactionExecuteResponse(**response_json)

class ContactSageClient(BaseClient):
    def __init__(self):
        super().__init__(os.getenv("CONTACT_SAGE_URL"), "Contact-Sage")

    async def resolve_contact(self, request: ContactResolveRequest, correlation_id: str, token: str) -> ContactResolveResponse:
        headers = self._get_headers(correlation_id, token)
        response_json = await self._request("POST", "/v1/contacts/resolve", headers, json=request.model_dump())
        return ContactResolveResponse(**response_json)

    async def get_contacts(self, account_id: str, correlation_id: str, token: str) -> List[Dict]:
        headers = self._get_headers(correlation_id, token)
        return await self._request("GET", f"/v1/contacts/{account_id}", headers)

    async def add_contact(self, account_id: str, contact: Dict, correlation_id: str, token: str) -> Dict:
        headers = self._get_headers(correlation_id, token)
        return await self._request("POST", f"/v1/contacts/{account_id}", headers, json=contact)

class MoneySageClient(BaseClient):
    def __init__(self):
        super().__init__(os.getenv("MONEY_SAGE_URL"), "Money-Sage")

    async def get_balance(self, account_id: str, correlation_id: str, token: str) -> Dict[str, Any]:
        headers = self._get_headers(correlation_id, token)
        return await self._request("GET", f"/v1/balance/{account_id}", headers)

    async def get_history(self, account_id: str, correlation_id: str, token: str) -> Dict[str, Any]:
        headers = self._get_headers(correlation_id, token)
        return await self._request("GET", f"/v1/history/{account_id}", headers)

    async def get_summary(self, account_id: str, period: str, correlation_id: str, token: str) -> Dict[str, Any]:
        headers = self._get_headers(correlation_id, token)
        return await self._request("GET", f"/v1/summary/{account_id}", headers, params={"period": period})

    async def get_budgets(self, account_id: str, correlation_id: str, token: str) -> List[Dict]:
        headers = self._get_headers(correlation_id, token)
        return await self._request("GET", f"/v1/budgets/{account_id}", headers)

    async def create_budget(self, account_id: str, budget: Dict, correlation_id: str, token: str) -> Dict:
        headers = self._get_headers(correlation_id, token)
        return await self._request("POST", f"/v1/budgets/{account_id}", headers, json=budget)

class ExchangeRateClient(BaseClient):
    def __init__(self):
        super().__init__("", "Exchange-Rate-Service")
    
    async def get_usd_conversion_rates(self, base_url: str, api_key: str, correlation_id: str) -> Dict[str, Any]:
        headers = {"X-Correlation-ID": correlation_id}
        # The API key is added as a path parameter for this specific API
        url_with_key = f"{base_url}/{api_key}/latest/USD"
        return await self._request("GET", url_with_key, headers)

# Instantiate clients for use in services
anomaly_sage_client = AnomalySageClient()
transaction_sage_client = TransactionSageClient()
contact_sage_client = ContactSageClient()
money_sage_client = MoneySageClient()
exchange_rate_client = ExchangeRateClient()
