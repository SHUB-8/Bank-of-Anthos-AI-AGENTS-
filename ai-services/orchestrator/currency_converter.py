# currency_converter.py
"""
Currency conversion service with caching and fallback strategies
"""
import httpx
import logging
from typing import Optional, Dict
from db import OrchestratorDb
from config import CONFIG

class CurrencyConverter:
    """Handles currency conversion with smart caching"""
    
    def __init__(self, db: OrchestratorDb):
        self.db = db
        self.api_key = CONFIG.exchange_rate_api_key if hasattr(CONFIG, 'exchange_rate_api_key') else None
        # v6.exchangerate-api.com endpoint - this returns rates relative to USD
        self.api_url = f"https://v6.exchangerate-api.com/v6/{self.api_key}/latest/USD" if self.api_key else None
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
        # rate is "how many USD per 1 unit of currency"
        usd_amount = amount * float(rate)
        return int(round(usd_amount * 100))

    async def _get_exchange_rate(self, currency_code: str) -> Optional[float]:
        """Get exchange rate for currency to USD (how many USD per 1 unit of the currency)"""
        
        # First try to get from database cache
        rate = self.db.get_exchange_rate(currency_code)
        if rate is not None:
            self.logger.info(f"Using cached exchange rate for {currency_code}: {rate}")
            return rate

        # If not cached or stale, fetch from API
        self.logger.info(f"Fetching fresh exchange rate for {currency_code}")
        
        # Fetch from API and update all rates
        success = await self._fetch_and_update_all_rates()
        if success:
            # Try to get the rate again from DB (should now be updated)
            rate = self.db.get_exchange_rate(currency_code)
            if rate is not None:
                return rate

        # If API fetch failed, try to get any cached rate (even if stale)
        self.logger.error(f"API fetch failed, looking for any cached rate for {currency_code}")
        return self.db.get_exchange_rate(currency_code, allow_stale=True)

    async def _fetch_and_update_all_rates(self) -> bool:
        """Fetch all exchange rates from API and update the database"""
        try:
            if not self.api_url:
                self.logger.error("Exchange rate API key not configured")
                return False
                
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.api_url)
                response.raise_for_status()
                data = response.json()
                
                # v6 returns { conversion_rates: { USD: 1, EUR: 0.9, INR: 84.5, ... } }
                # These rates are "how many units of currency X per 1 USD"
                rates = data.get("conversion_rates", {})
                
                if not rates:
                    self.logger.error("No conversion_rates found in API response")
                    return False
                
                # Update all rates in the database
                updated_count = 0
                for currency_code, usd_to_currency_rate in rates.items():
                    if currency_code == "USD":
                        continue  # Skip USD
                    
                    try:
                        # Convert from "USD to currency" rate to "currency to USD" rate
                        # If 1 USD = 84.5 INR, then 1 INR = 1/84.5 USD ≈ 0.0118 USD
                        if float(usd_to_currency_rate) != 0:
                            currency_to_usd_rate = 1 / float(usd_to_currency_rate)
                            if self.db.update_exchange_rate(currency_code, currency_to_usd_rate):
                                updated_count += 1
                    except (ValueError, ZeroDivisionError) as e:
                        self.logger.warning(f"Could not process rate for {currency_code}: {e}")
                        continue
                
                self.logger.info(f"Updated {updated_count} exchange rates from API")
                return updated_count > 0
                    
        except httpx.HTTPStatusError as e:
            self.logger.error(f"Currency API HTTP error: {e.response.status_code}")
            return False
        except httpx.RequestError as e:
            self.logger.error(f"Currency API request error: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Currency API unexpected error: {str(e)}")
            return False

    async def _fetch_from_primary_api(self, currency_code: str) -> Optional[float]:
        """Fetch exchange rate for a single currency from primary API (deprecated - use _fetch_and_update_all_rates)"""
        try:
            if not self.api_url:
                self.logger.error("Exchange rate API key not configured")
                return None
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(self.api_url)
                response.raise_for_status()
                data = response.json()
                # v6 returns { conversion_rates: { USD: 1, EUR: 0.9, ... } }
                rates = data.get("conversion_rates", {}) or data.get("rates", {})
                if currency_code in rates:
                    # Convert from USD rate to rate that converts currency to USD
                    usd_to_currency_rate = rates[currency_code]
                    currency_to_usd_rate = 1 / float(usd_to_currency_rate) if float(usd_to_currency_rate) != 0 else None
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
    
    async def convert_amount(self, amount: float, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Convert an amount from one currency to another.
        
        Args:
            amount: The amount to convert
            from_currency: Source currency code (e.g., 'EUR')
            to_currency: Target currency code (e.g., 'USD')
            
        Returns:
            Converted amount, or None if conversion fails
        """
        from_currency = from_currency.upper().strip()
        to_currency = to_currency.upper().strip()
        
        # Same currency, no conversion needed
        if from_currency == to_currency:
            return amount
        
        try:
            # Get rates for both currencies (to USD)
            if from_currency == "USD":
                from_rate = 1.0
            else:
                from_rate = await self._get_exchange_rate(from_currency)
                if from_rate is None:
                    return None
            
            if to_currency == "USD":
                to_rate = 1.0
            else:
                to_rate = await self._get_exchange_rate(to_currency)
                if to_rate is None:
                    return None
            
            # Convert: amount in from_currency -> USD -> to_currency
            # from_rate is "USD per from_currency"
            # to_rate is "USD per to_currency", so we need "to_currency per USD" = 1/to_rate
            usd_amount = amount * from_rate
            result = usd_amount / to_rate if to_rate != 0 else None
            
            return result
        except Exception as e:
            self.logger.error(f"Error converting {amount} {from_currency} to {to_currency}: {e}")
            return None