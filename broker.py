from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

import robin_stocks.robinhood as rh

from config import AppConfig

logger = logging.getLogger(__name__)


class Broker(ABC):
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    @abstractmethod
    def login(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_account_summary(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        quantity: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def close_position(self, symbol: str) -> dict[str, Any]:
        raise NotImplementedError


class RobinhoodBroker(Broker):
    def __init__(self, config: AppConfig) -> None:
        super().__init__(config)
        self.logged_in = False

    def login(self) -> None:
        if self.logged_in:
            return

        if not self.config.robinhood_username or not self.config.robinhood_password:
            raise ValueError("Robinhood username and password are required for live trading.")

        logger.info("Logging into Robinhood crypto API")
        rh.authentication.login(
            username=self.config.robinhood_username,
            password=self.config.robinhood_password,
            expiresIn=86400,
            by_sms=False,
            store_session=False,
        )
        self.logged_in = True

    def get_account_summary(self) -> dict[str, Any]:
        self.login()
        profile = rh.profiles.load_account_profile()
        equity = float(profile.get("portfolio_equity") or 0)
        buying_power = float(profile.get("cash_available") or 0)
        return {
            "account_value": equity,
            "buying_power": buying_power,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _normalize_symbol(self, symbol: str) -> str:
        symbol = symbol.upper()
        return symbol.split("-")[0] if "-" in symbol else symbol

    def get_positions(self) -> list[dict[str, Any]]:
        self.login()
        positions = rh.crypto.get_crypto_positions()
        active_positions: list[dict[str, Any]] = []
        for position in positions:
            quantity = float(position.get("quantity") or 0)
            symbol = position.get("currency")
            if quantity <= 0 or not symbol:
                continue
            quote = rh.crypto.get_crypto_quote(symbol)
            active_positions.append(
                {
                    "symbol": symbol,
                    "quantity": quantity,
                    "current_price": float(quote.get("mark_price") or 0),
                    "average_buy_price": float(position.get("average_buy_price") or 0),
                }
            )
        return active_positions

    def place_order(
        self,
        symbol: str,
        quantity: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> dict[str, Any]:
        self.login()
        if side not in {"buy", "sell"}:
            raise ValueError("side must be buy or sell")

        asset_symbol = self._normalize_symbol(symbol)
        logger.info("Placing %s order for %s qty %s", side, asset_symbol, quantity)

        if order_type == "limit" and limit_price is not None:
            order = rh.orders.order_buy_crypto_limit(
                asset_symbol,
                quantity,
                limit_price,
                timeInForce="gtc",
            ) if side == "buy" else rh.orders.order_sell_crypto_limit(
                asset_symbol,
                quantity,
                limit_price,
                timeInForce="gtc",
            )
        else:
            order = rh.orders.order_buy_crypto_by_quantity(asset_symbol, quantity) if side == "buy" else rh.orders.order_sell_crypto_by_quantity(asset_symbol, quantity)

        logger.debug("Robinhood order response: %s", order)
        return order or {}

    def close_position(self, symbol: str) -> dict[str, Any]:
        self.login()
        asset_symbol = self._normalize_symbol(symbol)
        positions = self.get_positions()
        position = next((pos for pos in positions if self._normalize_symbol(pos["symbol"]) == asset_symbol), None)
        if not position or position["quantity"] <= 0:
            return {"status": "no_position"}

        quantity = position["quantity"]
        logger.info("Closing position %s quantity %s", asset_symbol, quantity)
        order = rh.orders.order_sell_crypto_by_quantity(asset_symbol, quantity)
        logger.debug("Close position response: %s", order)
        return order or {}


class PaperBroker(Broker):
    def __init__(self, config: AppConfig) -> None:
        super().__init__(config)
        self.cash = 100_000.0
        self.positions: dict[str, dict[str, Any]] = {}

    def login(self) -> None:
        pass

    def get_account_summary(self) -> dict[str, Any]:
        account_value = self.cash + sum(
            pos["quantity"] * pos["current_price"] for pos in self.positions.values()
        )
        return {
            "account_value": account_value,
            "buying_power": self.cash,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_positions(self) -> list[dict[str, Any]]:
        return list(self.positions.values())

    def place_order(
        self,
        symbol: str,
        quantity: float,
        side: str,
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ) -> dict[str, Any]:
        symbol = symbol.upper()
        if side == "buy":
            if limit_price is None:
                raise ValueError("Paper broker requires current market price for market orders")
            price = limit_price
            self.cash -= quantity * price
            self.positions[symbol] = {
                "symbol": symbol,
                "quantity": quantity,
                "current_price": price,
                "average_buy_price": price,
            }
            return {"symbol": symbol, "quantity": quantity, "price": price, "status": "filled"}

        if side == "sell":
            position = self.positions.pop(symbol, None)
            if not position:
                return {"status": "no_position"}
            price = limit_price or position["current_price"]
            self.cash += quantity * price
            return {"symbol": symbol, "quantity": quantity, "price": price, "status": "closed"}

        raise ValueError("Unsupported order side")

    def close_position(self, symbol: str) -> dict[str, Any]:
        position = self.positions.pop(symbol.upper(), None)
        if not position:
            return {"status": "no_position"}
        self.cash += position["quantity"] * position["current_price"]
        return {"symbol": symbol.upper(), "quantity": position["quantity"], "price": position["current_price"], "status": "closed"}
