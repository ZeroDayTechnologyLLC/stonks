import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)

SYMBOL_NORMALIZATION = {
    "BTC-USD": "BTC",
    "ETH-USD": "ETH",
    "SOL-USD": "SOL",
    "DOGE-USD": "DOGE",
}

COINGECKO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "DOGE": "dogecoin",
}


class MarketDataProvider:
    name = "base"

    def get_quote(self, symbol: str) -> Optional[float]:
        raise NotImplementedError


class YFinanceProvider(MarketDataProvider):
    name = "yfinance"

    def get_quote(self, symbol: str) -> Optional[float]:
        yf_symbol = f"{symbol}-USD" if not symbol.endswith("-USD") else symbol
        ticker = yf.Ticker(yf_symbol)
        price = ticker.fast_info.get("last_price")
        if price is None:
            history = ticker.history(period="1d", interval="1m")
            if history.empty:
                return None
            price = history["Close"].iloc[-1]
        return float(price) if price is not None else None

    def get_history(self, symbol: str, period: str = "30d", interval: str = "1h") -> pd.DataFrame:
        yf_symbol = f"{symbol}-USD" if not symbol.endswith("-USD") else symbol
        history = yf.Ticker(yf_symbol).history(period=period, interval=interval, actions=False)
        return history if not history.empty else pd.DataFrame()


class CoinbaseProvider(MarketDataProvider):
    name = "coinbase"

    def get_quote(self, symbol: str) -> Optional[float]:
        asset = SYMBOL_NORMALIZATION.get(symbol.upper(), symbol.upper()).replace("-USD", "")
        url = f"https://api.coinbase.com/v2/prices/{asset}-USD/spot"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        amount = data.get("data", {}).get("amount")
        return float(amount) if amount is not None else None


class CoinGeckoProvider(MarketDataProvider):
    name = "coingecko"

    def get_quote(self, symbol: str) -> Optional[float]:
        key = SYMBOL_NORMALIZATION.get(symbol.upper(), symbol.upper()).replace("-USD", "")
        asset_id = COINGECKO_IDS.get(key)
        if not asset_id:
            return None
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={asset_id}&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        price = data.get(asset_id, {}).get("usd")
        return float(price) if price is not None else None


class MarketDataClient:
    def __init__(self, provider: str = "auto") -> None:
        self.provider = provider.lower().strip() or "auto"
        self.providers = self._build_providers()

    def _build_providers(self) -> List[MarketDataProvider]:
        available: Dict[str, MarketDataProvider] = {
            "yfinance": YFinanceProvider(),
            "coinbase": CoinbaseProvider(),
            "coingecko": CoinGeckoProvider(),
        }
        if self.provider == "auto":
            return [available["yfinance"], available["coinbase"], available["coingecko"]]
        if self.provider == "yfinance":
            return [available["yfinance"], available["coinbase"], available["coingecko"]]
        if self.provider == "coinbase":
            return [available["coinbase"], available["coingecko"], available["yfinance"]]
        if self.provider == "coingecko":
            return [available["coingecko"], available["coinbase"], available["yfinance"]]
        return [available["yfinance"], available["coinbase"], available["coingecko"]]

    def normalize_symbol(self, symbol: str) -> str:
        value = symbol.strip().upper()
        return SYMBOL_NORMALIZATION.get(value, value.replace("-USD", "").replace("/USD", ""))

    def get_quote(self, symbol: str) -> Optional[float]:
        normalized = self.normalize_symbol(symbol)
        for provider in self.providers:
            response = self._retry(provider.get_quote, normalized)
            if response is not None:
                logger.info("Market data found %s for %s using %s", response, symbol, provider.name)
                return response
            logger.warning("Provider %s failed for %s", provider.name, symbol)
        logger.error("All market data providers failed for %s", symbol)
        return None

    def get_history(self, symbol: str, period: str = "30d", interval: str = "1h") -> pd.DataFrame:
        return YFinanceProvider().get_history(symbol, period=period, interval=interval)

    def get_latest_volume(self, symbol: str) -> float:
        history = self.get_history(symbol, period="10d", interval="1h")
        if history.empty:
            return 0.0
        return float(history["Volume"].iloc[-1])

    def get_average_volume(self, symbol: str, periods: int = 20) -> float:
        history = self.get_history(symbol, period="30d", interval="1h")
        if history.empty:
            return 0.0
        return float(history["Volume"].rolling(periods).mean().iloc[-1])

    def get_last_price_and_time(self, symbol: str) -> tuple[Optional[float], Optional[datetime]]:
        quote = self.get_quote(symbol)
        return quote, datetime.utcnow() if quote is not None else (None, None)

    def _retry(self, func, symbol: str, retries: int = 3) -> Optional[float]:
        delay = 0.5
        for attempt in range(retries):
            try:
                value = func(symbol)
                if value is not None:
                    return value
            except Exception as exc:
                logger.warning(
                    "Provider exception for %s on %s attempt %d: %s",
                    symbol,
                    func.__self__.name if hasattr(func, "__self__") else "unknown",
                    attempt + 1,
                    exc,
                )
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
        return None
