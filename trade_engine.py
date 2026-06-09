from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, List, Optional

from broker import Broker, PaperBroker, RobinhoodBroker
from config import AppConfig
from database import Database
from market_data import MarketDataClient
from risk_manager import RiskManager
from strategy import MomentumBreakoutStrategy, TradeSignal, TradingStrategy
from alerts import AlertManager

logger = logging.getLogger(__name__)


class TradingBot:
    def __init__(
        self,
        config: AppConfig,
        broker: Broker,
        data_client: MarketDataClient,
        database: Database,
        alert_manager: AlertManager,
    ) -> None:
        self.config = config
        self.broker = broker
        self.data_client = data_client
        self.database = database
        self.alert_manager = alert_manager
        self.risk_manager = RiskManager(
            max_risk_pct=config.max_risk_pct,
            max_position_pct=config.max_position_pct,
            daily_loss_limit_pct=config.daily_loss_limit_pct,
        )
        self.last_cycle_summary: dict[str, Any] = {}
        available: dict[str, type[TradingStrategy]] = {
            "momentum_breakout": MomentumBreakoutStrategy,
        }
        self.strategies = [available[name]() for name in config.enabled_strategies if name in available]
        if not self.strategies:
            self.strategies = [MomentumBreakoutStrategy()]
        self.paused_until: Optional[datetime] = None

    def _load_system_pause(self) -> None:
        pause_value = self.database.load_system_state("pause_until")
        if pause_value:
            try:
                self.paused_until = datetime.fromisoformat(pause_value)
            except ValueError:
                self.paused_until = None

    def _save_system_pause(self, until: Optional[datetime]) -> None:
        self.paused_until = until
        value = until.isoformat() if until else ""
        self.database.record_system_state("pause_until", value, datetime.utcnow().isoformat())

    def _get_open_trades(self) -> List[dict]:
        trades = self.database.load_trade_history(limit=200)
        return [trade for trade in trades if trade["status"] == "open"]

    def _evaluate_symbol(self, symbol: str) -> Optional[TradeSignal]:
        price = self.data_client.get_quote(symbol)
        if price is None:
            return None

        history = self.data_client.get_history(symbol, period="30d", interval="1h")
        if history.empty:
            return None

        latest_change_pct = ((price - history["Close"].iloc[-2]) / history["Close"].iloc[-2]) * 100 if len(history) >= 2 else 0.0
        signals = [
            strategy.evaluate(
                symbol=symbol,
                history=history,
                current_price=price,
                latest_change_pct=latest_change_pct,
                news_sentiment=None,
            )
            for strategy in self.strategies
        ]
        signals = [signal for signal in signals if signal is not None]
        if not signals:
            return None
        return max(signals, key=lambda value: value.confidence)

    def _record_snapshot(self, account_value: float, buying_power: float, unrealized_pl: float, daily_loss_pct: float) -> None:
        self.database.record_account_snapshot(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "account_value": account_value,
                "buying_power": buying_power,
                "unrealized_pl": unrealized_pl,
                "daily_loss_pct": daily_loss_pct,
            }
        )

    def _gather_account_state(self) -> tuple[float, float, float]:
        account = self.broker.get_account_summary()
        account_value = float(account.get("account_value", 0.0))
        buying_power = float(account.get("buying_power", 0.0))
        unrealized_pl = 0.0
        return account_value, buying_power, unrealized_pl

    def _pause_trading_for_24h(self) -> None:
        until = datetime.utcnow() + timedelta(hours=24)
        self._save_system_pause(until)
        self.alert_manager.notify_daily_limit_reached()

    def _check_daily_limits(self, account_value: float) -> bool:
        if self.paused_until and datetime.utcnow() < self.paused_until:
            logger.warning("Trading paused until %s", self.paused_until.isoformat())
            return False
        recent_snapshot = self.database.load_system_state("starting_balance")
        if not recent_snapshot:
            self.database.record_system_state(
                "starting_balance", str(account_value), datetime.utcnow().isoformat(),
            )
            return True

        try:
            start_balance = float(recent_snapshot)
        except ValueError:
            start_balance = account_value

        daily_loss_pct = self.risk_manager.calculate_daily_loss_pct(start_balance, account_value)
        if daily_loss_pct >= self.config.daily_loss_limit_pct:
            logger.error("Daily loss limit exceeded: %.2f%%", daily_loss_pct * 100)
            self._pause_trading_for_24h()
            return False

        return True

    def _place_trade(self, signal: TradeSignal, account_value: float) -> bool:
        quantity = self.risk_manager.calculate_quantity(account_value, signal.current_price, signal.stop_loss)
        if quantity is None or quantity <= 0.0:
            logger.info("Trade skipped due to sizing constraints for %s", signal.symbol)
            return False

        if not self.config.enable_live_trading:
            logger.info("Paper trade: %s %s qty %.6f", signal.recommendation, signal.symbol, quantity)
            market_response = self.broker.place_order(
                symbol=signal.symbol,
                quantity=quantity,
                side="buy",
                order_type="market",
                limit_price=signal.current_price,
            )
            self.database.record_trade(
                {
                    "symbol": signal.symbol,
                    "side": "buy",
                    "quantity": quantity,
                    "entry_price": signal.current_price,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "confidence": signal.confidence,
                    "strategy": signal.strategy_name,
                    "status": "open",
                    "opened_at": datetime.utcnow().isoformat(),
                    "notes": f"paper trade; response={market_response}",
                }
            )
            self.alert_manager.notify_trade_opened(signal, paper_mode=True)
            return True

        logger.warning(self.config.live_trading_warning)
        self.broker.login()
        trade_response = self.broker.place_order(
            symbol=signal.symbol,
            quantity=quantity,
            side="buy",
            order_type="market",
        )
        self.database.record_order_log("buy", str(trade_response), signal.symbol)
        self.database.record_trade(
            {
                "symbol": signal.symbol,
                "side": "buy",
                "quantity": quantity,
                "entry_price": signal.current_price,
                "stop_loss": signal.stop_loss,
                "take_profit": signal.take_profit,
                "confidence": signal.confidence,
                "strategy": signal.strategy_name,
                "status": "open",
                "opened_at": datetime.utcnow().isoformat(),
                "notes": "live trade opened",
            }
        )
        self.alert_manager.notify_trade_opened(signal, paper_mode=False)
        return True

    def _close_trade(self, trade: dict, exit_price: float, reason: str) -> None:
        if trade["status"] != "open":
            return

        self.broker.close_position(trade["symbol"])
        pnl = (exit_price - trade["entry_price"]) * trade["quantity"]
        status = "closed"
        self.database.update_trade(
            trade["id"],
            {
                "exit_price": exit_price,
                "closed_at": datetime.utcnow().isoformat(),
                "status": status,
                "pnl": round(pnl, 6),
                "notes": f"closed by {reason}",
            },
        )
        self.database.record_order_log("close", f"reason={reason} price={exit_price} pnl={pnl}", trade["symbol"])
        self.alert_manager.notify_trade_closed(trade, exit_price, pnl, reason)

    def _monitor_positions(self) -> None:
        open_trades = self._get_open_trades()
        for trade in open_trades:
            quote = self.data_client.get_quote(trade["symbol"])
            if quote is None:
                continue

            if quote <= trade["stop_loss"]:
                self._close_trade(trade, quote, "stop_loss")
            elif quote >= trade["take_profit"]:
                self._close_trade(trade, quote, "take_profit")

    def run_cycle(self) -> None:
        self._load_system_pause()
        account_value, buying_power, unrealized_pl = self._gather_account_state()
        if not self._check_daily_limits(account_value):
            return

        self._monitor_positions()
        symbols = self.config.watchlist or self.config.supported_symbols
        summary: dict[str, Any] = {
            "evaluated": 0,
            "trades_placed": 0,
            "signals": [],
            "paused": False,
            "daily_limit_exceeded": False,
        }

        for symbol in symbols:
            summary["evaluated"] += 1
            signal = self._evaluate_symbol(symbol)
            if signal is None:
                summary["signals"].append(
                    {
                        "symbol": symbol,
                        "status": "no_data",
                        "confidence": None,
                        "recommendation": None,
                        "reason": "missing quote or history",
                    }
                )
                continue

            detail: dict[str, Any] = {
                "symbol": symbol,
                "confidence": signal.confidence,
                "recommendation": signal.recommendation,
                "reason": signal.reason,
            }

            if signal.recommendation == "avoid":
                detail["status"] = "avoid"
                summary["signals"].append(detail)
                continue

            if not self.risk_manager.should_trade(
                account_value=account_value,
                daily_loss_pct=0.0,
                confidence=signal.confidence,
                threshold=self.config.confidence_threshold,
            ):
                detail["status"] = "threshold" if signal.confidence < self.config.confidence_threshold else "risk"
                summary["signals"].append(detail)
                continue

            placed = self._place_trade(signal, account_value)
            if placed:
                detail["status"] = "placed"
                summary["trades_placed"] += 1
            else:
                detail["status"] = "size_constrained"
                detail["reason"] = "order quantity too small or invalid sizing"
            summary["signals"].append(detail)

        self._record_snapshot(account_value, buying_power, unrealized_pl, 0.0)
        self.last_cycle_summary = summary
        return summary

    def start(self) -> None:
        logger.info("Starting trading bot. Live trading=%s", self.config.enable_live_trading)
        while True:
            try:
                self.run_cycle()
                time.sleep(60)
            except KeyboardInterrupt:
                logger.info("Trading bot stopped by user")
                break
            except Exception as exc:
                logger.exception("Unexpected exception in trading loop: %s", exc)
                time.sleep(60)
