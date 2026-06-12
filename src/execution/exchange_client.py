import time
import json
import hmac
import hashlib
import logging
import asyncio
import aiohttp
from decimal import Decimal
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from src.config import EnvironmentConfig
from src.models.enums import Direction

logger = logging.getLogger("trading.api.gateio")

class GateIOClient:
    """
    Production-grade asynchronous Gate.io API v4 Wrapper.
    Implements secure HMAC SHA512 signature generation and resilient request handling.
    """
    
    BASE_URL = "https://api.gateio.ws/api/v4"

    def __init__(self, config: EnvironmentConfig):
        self.api_key = config.GATEIO_API_KEY
        self.api_secret = config.GATEIO_API_SECRET
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Manages the aiohttp session lifecycle."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )
        return self.session

    def _generate_signature(self, method: str, url: str, query_string: str, payload_string: str) -> Dict[str, str]:
        """
        Generates the Gate.io v4 API signature.
        Payload format: Method\nURL\nQueryString\nHex(SHA512(Body))\nTimestamp
        """
        timestamp = str(int(time.time()))
        
        # Hash the request body
        m = hashlib.sha512()
        m.update((payload_string or "").encode('utf-8'))
        hashed_payload = m.hexdigest()
        
        # Construct the signature string
        sig_string = f"{method}\n{url}\n{query_string}\n{hashed_payload}\n{timestamp}"
        
        # HMAC SHA512 signature
        sign = hmac.new(
            self.api_secret.encode('utf-8'), 
            sig_string.encode('utf-8'), 
            hashlib.sha512
        ).hexdigest()
        
        return {
            "KEY": self.api_key,
            "Timestamp": timestamp,
            "SIGN": sign
        }

    async def _request(self, method: str, endpoint: str, params: dict = None, body: dict = None) -> Dict[str, Any]:
        """Executes the HTTP request with exponential backoff for rate limits."""
        url_path = f"/api/v4{endpoint}"
        query_string = urlencode(params) if params else ""
        payload_string = json.dumps(body) if body else ""
        
        headers = self._generate_signature(method, url_path, query_string, payload_string)
        full_url = f"{self.BASE_URL}{endpoint}"
        if query_string:
            full_url += f"?{query_string}"

        session = await self._get_session()
        retries = 3
        
        for attempt in range(retries):
            try:
                async with session.request(method, full_url, headers=headers, data=payload_string) as response:
                    # Rate limit handling (HTTP 429)
                    if response.status == 429:
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limit hit. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                        
                    response.raise_for_status()
                    return await response.json()
                    
            except aiohttp.ClientResponseError as e:
                logger.error(f"API Error [{e.status}]: {e.message}")
                if attempt == retries - 1:
                    raise Exception(f"Gate.io API request failed after {retries} attempts: {str(e)}")
            except Exception as e:
                logger.error(f"Network error during API call: {str(e)}")
                if attempt == retries - 1:
                    raise

        return {}

    async def get_ticker(self, currency_pair: str) -> Dict[str, Any]:
        """Fetches the latest ticker data for a specific pair."""
        return await self._request("GET", "/spot/tickers", params={"currency_pair": currency_pair})

    async def create_order(self, currency_pair: str, side: str, amount: str, price: Optional[str] = None, order_type: str = "market") -> Dict[str, Any]:
        """
        Executes a live spot order.
        Side: 'buy' or 'sell'
        """
        body = {
            "currency_pair": currency_pair,
            "side": side,
            "amount": amount,
            "time_in_force": "ioc" if order_type == "market" else "gtc",
            "type": order_type
        }
        if price and order_type == "limit":
            body["price"] = price

        logger.info(f"Submitting {order_type.upper()} {side.upper()} order for {amount} {currency_pair}")
        return await self._request("POST", "/spot/orders", body=body)

    async def close(self):
        """Cleanly closes the async HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()
