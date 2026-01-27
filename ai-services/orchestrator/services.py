"""
Service integration layer for calling other sage microservices
"""
import httpx
import logging
from typing import Dict, List, Any, Optional
import uuid

class SageServices:
    """Handles HTTP calls to all sage microservices"""
    
    def __init__(self, contact_sage_url: str, anomaly_sage_url: str, 
                 transaction_sage_url: str, money_sage_url: str, logger: logging.Logger):
        self.contact_sage_url = contact_sage_url.rstrip('/')
        self.anomaly_sage_url = anomaly_sage_url.rstrip('/')
        self.transaction_sage_url = transaction_sage_url.rstrip('/')
        self.money_sage_url = money_sage_url.rstrip('/')
        self.logger = logger
        self.timeout = httpx.Timeout(30.0)  # 30 seconds timeout
    
    def _get_headers(self, auth_header: str) -> Dict[str, str]:
        """Get standard headers with JWT authorization"""
        return {
            "Authorization": auth_header,
            "Content-Type": "application/json"
        }
    
    async def _make_request(self, method: str, url: str, auth_header: str, 
                          json_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request with error handling"""
        headers = self._get_headers(auth_header)
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=json_data)
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=headers, json=json_data)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response.raise_for_status()
                
                # Handle different response types
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json()
                else:
                    # Handle plain text responses (like transaction-sage's "ok")
                    return {"response": response.text, "status_code": response.status_code}
                    
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error for {method} {url}: {e.response.status_code} - {e.response.text}")
            try:
                error_detail = e.response.json().get("detail", str(e))
            except:
                error_detail = e.response.text or str(e)
            return {"error": error_detail, "status_code": e.response.status_code}
        except httpx.RequestError as e:
            self.logger.error(f"Request error for {method} {url}: {str(e)}")
            return {"error": f"Request failed: {str(e)}"}
        except Exception as e:
            self.logger.error(f"Unexpected error for {method} {url}: {str(e)}")
            return {"error": f"Unexpected error: {str(e)}"}

    # Contact Sage Methods
    async def get_contacts(self, account_id: str, auth_header: str) -> Dict[str, Any]:
        """Get all contacts for an account"""
        url = f"{self.contact_sage_url}/contacts/{account_id}"
        return await self._make_request("GET", url, auth_header)
    
    async def add_contact(self, account_id: str, contact_data: Dict[str, Any], 
                         auth_header: str) -> Dict[str, Any]:
        """Add a new contact"""
        url = f"{self.contact_sage_url}/contacts/{account_id}"
        return await self._make_request("POST", url, auth_header, contact_data)
    
    async def update_contact(self, account_id: str, contact_label: str, 
                           contact_data: Dict[str, Any], auth_header: str) -> Dict[str, Any]:
        """Update an existing contact"""
        url = f"{self.contact_sage_url}/contacts/{account_id}/{contact_label}"
        return await self._make_request("PUT", url, auth_header, contact_data)
    
    async def delete_contact(self, account_id: str, contact_label: str, 
                           auth_header: str) -> Dict[str, Any]:
        """Delete a contact"""
        url = f"{self.contact_sage_url}/contacts/{account_id}/{contact_label}"
        return await self._make_request("DELETE", url, auth_header)
    
    async def resolve_contact(self, recipient_name: str, account_id: str, 
                            auth_header: str) -> Dict[str, Any]:
        """Resolve contact name to account number using fuzzy search"""
        url = f"{self.contact_sage_url}/contacts/resolve"
        data = {
            "recipient": recipient_name,
            "account_id": account_id
        }
        return await self._make_request("POST", url, auth_header, data)

    # Money Sage Methods  
    async def get_balance(self, account_id: str, auth_header: str) -> Dict[str, Any]:
        """Get account balance"""
        url = f"{self.money_sage_url}/balance/{account_id}"
        return await self._make_request("GET", url, auth_header)
    
    async def get_transactions(self, account_id: str, auth_header: str,
                              limit: int = 5, order: str = "desc",
                              transaction_type: Optional[str] = None,
                              anomaly_status: Optional[str] = None,
                              include_total: bool = False) -> Dict[str, Any]:
        """Get transaction history with optional filters
        
        Args:
            account_id: User's account ID
            limit: Maximum number of transactions to return (default 5)
            order: Sort order - 'desc' for newest first (default), 'asc' for oldest first
            transaction_type: Optional filter - 'debit' or 'credit'
            anomaly_status: Optional filter - 'normal', 'pending', 'confirmed', 'cancelled', 'expired', 'fraud'
            include_total: If True, also fetch total transaction count
        """
        # Build query parameters
        params = [f"limit={limit}", f"order={order}"]
        if transaction_type:
            params.append(f"transaction_type={transaction_type}")
        if anomaly_status:
            # Match new status names
            if anomaly_status == 'suspicious':
                anomaly_status = 'pending'
            params.append(f"anomaly_status={anomaly_status}")
        
        query_string = "&".join(params)
        url = f"{self.money_sage_url}/transactions/{account_id}?{query_string}"
        
        result = await self._make_request("GET", url, auth_header)
        
        # If include_total is requested, fetch total count
        if include_total and isinstance(result, dict) and "error" not in result:
            total_url = f"{self.money_sage_url}/transactions/{account_id}/count"
            total_result = await self._make_request("GET", total_url, auth_header)
            if isinstance(total_result, dict) and "total_count" in total_result:
                result["total_count"] = total_result["total_count"]
        
        return result
    
    async def get_budgets(self, account_id: str, auth_header: str) -> Dict[str, Any]:
        """Get all budgets for an account"""
        url = f"{self.money_sage_url}/budgets/{account_id}"
        return await self._make_request("GET", url, auth_header)
    
    async def create_budget(self, account_id: str, budget_data: Dict[str, Any], 
                          auth_header: str) -> Dict[str, Any]:
        """Create a new budget"""
        url = f"{self.money_sage_url}/budgets/{account_id}"
        return await self._make_request("POST", url, auth_header, budget_data)
    
    async def update_budget(self, account_id: str, category: str, 
                          budget_data: Dict[str, Any], auth_header: str) -> Dict[str, Any]:
        """Update an existing budget"""
        url = f"{self.money_sage_url}/budgets/{account_id}/{category}"
        return await self._make_request("PUT", url, auth_header, budget_data)
    
    async def delete_budget(self, account_id: str, category: str, 
                          auth_header: str) -> Dict[str, Any]:
        """Delete a budget"""
        url = f"{self.money_sage_url}/budgets/{account_id}/{category}"
        return await self._make_request("DELETE", url, auth_header)
    
    async def get_spending_summary(self, account_id: str, auth_header: str) -> Dict[str, Any]:
        """Get spending summary by category"""
        url = f"{self.money_sage_url}/summary/{account_id}"
        return await self._make_request("GET", url, auth_header)
    
    async def get_budget_overview(self, account_id: str, auth_header: str) -> Dict[str, Any]:
        """Get budget overview showing spending vs limits"""
        url = f"{self.money_sage_url}/overview/{account_id}"
        return await self._make_request("GET", url, auth_header)
    
    async def get_saving_tips(self, account_id: str, auth_header: str) -> Dict[str, Any]:
        """Get personalized saving tips"""
        url = f"{self.money_sage_url}/tips/{account_id}"
        return await self._make_request("GET", url, auth_header)

    # Anomaly Sage Methods
    async def detect_anomaly(self, account_id: str, amount_cents: int, 
                           recipient_id: str, is_external: bool, 
                           auth_header: str) -> Dict[str, Any]:
        """Detect anomalies in a proposed transaction"""
        # Align with anomaly-sage code path (exposes /detect-anomaly)
        data = {
            "account_id": account_id,
            "amount_cents": amount_cents,
            "recipient_id": recipient_id,
            "is_external": is_external
        }
        # Use unversioned path used by current anomaly-sage implementation
        url = f"{self.anomaly_sage_url}/detect-anomaly"
        return await self._make_request("POST", url, auth_header, data)

    async def confirm_pending_transaction(self, log_id: str, auth_header: str) -> Dict[str, Any]:
        """Confirm a pending transaction in anomaly-sage"""
        url = f"{self.anomaly_sage_url}/confirm-pending/{log_id}"
        return await self._make_request("POST", url, auth_header)

    async def cancel_pending_transaction(self, log_id: str, auth_header: str) -> Dict[str, Any]:
        """Cancel a pending transaction in anomaly-sage"""
        url = f"{self.anomaly_sage_url}/cancel-pending/{log_id}"
        return await self._make_request("POST", url, auth_header)

    async def confirm_suspicious_transaction(self, log_id: str, auth_header: str) -> Dict[str, Any]:
        """DEPRECATED: Use confirm_pending_transaction. Maintains compat for old calls."""
        return await self.confirm_pending_transaction(log_id, auth_header)

    # Transaction Sage Methods
    async def execute_transaction(self, transaction_data: Dict[str, Any], 
                                auth_header: str) -> Dict[str, Any]:
        """Execute a transaction after validation"""
        # Align payload to Transaction-Sage's expected schema
        mapped_payload = {
            "account_id": transaction_data.get("fromAccountNum") or transaction_data.get("account_id"),
            "recipient_id": transaction_data.get("toAccountNum") or transaction_data.get("recipient_id"),
            "recipient_routing_num": transaction_data.get("toRoutingNum") or transaction_data.get("recipient_routing_num"),
            "amount_cents": transaction_data.get("amount") or transaction_data.get("amount_cents"),
            "description": transaction_data.get("description", ""),
            "category": transaction_data.get("category"),
            "is_external": transaction_data.get("is_external", False),
            "uuid": transaction_data.get("uuid") or transaction_data.get("request_uuid")
        }
        url = f"{self.transaction_sage_url}/v1/execute-transaction"
        return await self._make_request("POST", url, auth_header, mapped_payload)

    async def deposit_funds(self, deposit_data: Dict[str, Any], auth_header: str) -> Dict[str, Any]:
        """Execute a deposit from external account"""
        mapped_payload = {
            "account_id": deposit_data.get("account_id"),
            "external_account_id": deposit_data.get("external_account_id"),
            "external_routing_num": deposit_data.get("external_routing_num"),
            "amount_cents": deposit_data.get("amount_cents"),
            "description": deposit_data.get("description", "Deposit via Assistant"),
            "uuid": deposit_data.get("uuid", str(uuid.uuid4()))
        }
        url = f"{self.transaction_sage_url}/v1/deposit"
        return await self._make_request("POST", url, auth_header, mapped_payload)

    # Health check methods for monitoring
    async def check_service_health(self, auth_header: str) -> Dict[str, Dict[str, Any]]:
        """Check health of all sage services"""
        services = {
            "contact-sage": f"{self.contact_sage_url}/health",
            "money-sage": f"{self.money_sage_url}/health", 
            "anomaly-sage": f"{self.anomaly_sage_url}/health",
            "transaction-sage": f"{self.transaction_sage_url}/health"
        }
        
        results = {}
        for service_name, url in services.items():
            try:
                result = await self._make_request("GET", url, auth_header)
                results[service_name] = {
                    "status": "healthy" if not result.get("error") else "unhealthy",
                    "response": result
                }
            except Exception as e:
                results[service_name] = {
                    "status": "unhealthy", 
                    "error": str(e)
                }
        
        return results
    
    async def get_transaction_count(self, account_id: str, auth_header: str,
                                   transaction_type: Optional[str] = None,
                                   anomaly_status: Optional[str] = None) -> Dict[str, Any]:
        """Get total transaction count from money-sage"""
        params = []
        if transaction_type:
            params.append(f"transaction_type={transaction_type}")
        if anomaly_status:
            params.append(f"anomaly_status={anomaly_status}")
        
        query_string = "&".join(params)
        url = f"{self.money_sage_url}/transactions/{account_id}/count"
        if query_string:
            url += f"?{query_string}"
            
        return await self._make_request("GET", url, auth_header)

    async def get_anomalies(self, account_id: str, auth_header: str, limit: int = 50) -> Dict[str, Any]:
        """Get anomaly logs for an account from anomaly-sage"""
        url = f"{self.anomaly_sage_url}/anomalies/{account_id}?limit={limit}"
        return await self._make_request("GET", url, auth_header)

    async def get_bank_info(self, auth_header: str) -> Dict[str, Any]:
        """Get general bank information - Placeholder as this usually comes from a CMS or static info"""
        # In a real app, this might call another service or a database
        return {
            "name": "Bank of Anthos",
            "routing_number": "883745000",
            "support_email": "support@bankofanthos.com",
            "daily_limit": 50000
        }