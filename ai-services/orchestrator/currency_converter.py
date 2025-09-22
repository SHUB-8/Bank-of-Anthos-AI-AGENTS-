# currency_converter.py
"""
Currency conversion service with caching and fallback strategies
"""
import httpx
import logging
from typing import Optional
from db import OrchestratorDb

class CurrencyConverter:
    """Handles currency conversion with smart caching"""
    
    def __init__(self, db: OrchestratorDb):
        self.db = db
        self.api_url = "https://api.exchangerate-api.com/v4/latest/USD"
        self.fallback_api_url = "https://api.fxratesapi.com/latest"
        self.timeout = httpx.Timeout(10.0)  # 10 seconds timeout for currency API
        self.logger = logging.getLogger(__name__)

    async def normalize_to_usd_cents(self, amount: float, currency_code: str) -> int:
        """
        Convert any currency amount to USD cents
        
        Args:
            amount: The amount in the original currency
            currency_code: ISO currency code (e.g., 'EUR', 'GBP', 'USD')
            
        Returns:
            Amount in USD cents (integer)
            
        Raises:
            ValueError: If currency conversion fails
        """
        currency_code = currency_code.upper().strip()
        
        # Handle USD directly
        if currency_code == "USD":
            return int(round(amount * 100))

        # Try to get exchange rate
        rate = await self._get_exchange_rate(currency_code)
        if not rate:
            raise ValueError(f"Unable to get exchange rate for {currency_code}")

        # Convert to USD and then to cents
        usd_amount = amount * float(rate)
        return int(round(usd_amount * 100))

    async def _get_exchange_rate(self, currency_code: str) -> Optional[float]:
        """Get exchange rate for currency to USD"""
        
        # First try to get from database cache
        rate = self.db.get_exchange_rate(currency_code)
        if rate is not None:
            self.logger.info(f"Using cached exchange rate for {currency_code}: {rate}")
            return rate

        # If not cached or stale, fetch from API
        self.logger.info(f"Fetching fresh exchange rate for {currency_code}")
        
        # Try primary API
        rate = await self._fetch_from_primary_api(currency_code)
        if rate is not None:
            self.db.update_exchange_rate(currency_code, rate)
            return rate

        # Try fallback API
        self.logger.warning(f"Primary API failed, trying fallback for {currency_code}")
        rate = await self._fetch_from_fallback_api(currency_code)
        if rate is not None:
            self.db.update_exchange_rate(currency_code, rate)
            return rate

        # If both APIs fail, try to get any cached rate (even if stale)
        self.logger.error(f"All APIs failed, looking for any cached rate for {currency_code}")
        return self.db.get_exchange_rate(currency_code, allow_stale=True)

    async def _fetch_from_primary_api(self, currency_code: str) -> Optional[float]:
        """Fetch exchange rate from primary API"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.api_url)
                response.raise_for_status()
                data = response.json()
                
                rates = data.get("rates", {})
                if currency_code in rates:
                    # Convert from USD rate to rate that converts currency to USD
                    usd_to_currency_rate = rates[currency_code]
                    currency_to_usd_rate = 1 / usd_to_currency_rate
                    self.logger.info(f"Primary API: {currency_code} to USD rate: {currency_to_usd_rate}")
                    return currency_to_usd_rate
                else:
                    self.logger.error(f"Currency {currency_code} not found in primary API response")
                    return None
                    
        except httpx.HTTPStatusError as e:
            self.logger.error(f"Primary currency API HTTP error: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            self.logger.error(f"Primary currency API request error: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Primary currency API unexpected error: {str(e)}")
            return None

    async def _fetch_from_fallback_api(self, currency_code: str) -> Optional[float]:
        """Fetch exchange rate from fallback API"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Use base=USD to get rates from USD to other currencies
                response = await client.get(f"{self.fallback_api_url}?base=USD")
                response.raise_for_status()
                data = response.json()
                
                rates = data.get("rates", {})
                if currency_code in rates:
                    # Convert from USD rate to rate that converts currency to USD
                    usd_to_currency_rate = rates[currency_code]
                    currency_to_usd_rate = 1 / usd_to_currency_rate
                    self.logger.info(f"Fallback API: {currency_code} to USD rate: {currency_to_usd_rate}")
                    return currency_to_usd_rate
                else:
                    self.logger.error(f"Currency {currency_code} not found in fallback API response")
                    return None
                    
        except httpx.HTTPStatusError as e:
            self.logger.error(f"Fallback currency API HTTP error: {e.response.status_code}")
            return None
        except httpx.RequestError as e:
            self.logger.error(f"Fallback currency API request error: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Fallback currency API unexpected error: {str(e)}")
            return None

    def get_supported_currencies(self) -> list:
        """Get list of commonly supported currencies"""
        return [
            "USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "CNY", 
            "SEK", "NZD", "MXN", "SGD", "HKD", "NOK", "KRW", "TRY",
            "RUB", "INR", "BRL", "ZAR"
        ]

    async def get_currency_info(self, currency_code: str) -> dict:
        """Get detailed information about a currency"""
        currency_info = {
            "USD": {"name": "US Dollar", "symbol": "$"},
            "EUR": {"name": "Euro", "symbol": "€"},
            "GBP": {"name": "British Pound", "symbol": "£"},
            "JPY": {"name": "Japanese Yen", "symbol": "¥"},
            "AUD": {"name": "Australian Dollar", "symbol": "A$"},
            "CAD": {"name": "Canadian Dollar", "symbol": "C$"},
            "CHF": {"name": "Swiss Franc", "symbol": "CHF"},
            "CNY": {"name": "Chinese Yuan", "symbol": "¥"},
            "INR": {"name": "Indian Rupee", "symbol": "₹"},
        }
        
        currency_code = currency_code.upper()
        info = currency_info.get(currency_code, {"name": currency_code, "symbol": currency_code})
        
        # Add current rate if available
        try:
            rate = await self._get_exchange_rate(currency_code)
            if rate:
                info["rate_to_usd"] = rate
        except:
            pass
            
        return info