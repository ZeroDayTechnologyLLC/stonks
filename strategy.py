from dataclasses import dataclass
from typing import Optional

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator


@dataclass
class TradeSignal:
    symbol: str
    confidence: float
    recommendation: str
    reason: str
    stop_loss: float
    take_profit: float
    current_price: float
    strategy_name: str


class TradingStrategy:
    name = "base"

    def evaluate(
        self,
        symbol: str,
        history: pd.DataFrame,
        current_price: float,
        latest_change_pct: float,
        news_sentiment: Optional[float] = None,
    ) -> TradeSignal:
        raise NotImplementedError


class MomentumBreakoutStrategy(TradingStrategy):
    name = "momentum_breakout"

    def evaluate(
        self,
        symbol: str,
        history: pd.DataFrame,
        current_price: float,
        latest_change_pct: float,
        news_sentiment: Optional[float] = None,
    ) -> TradeSignal:
        if history.empty or len(history) < 20 or current_price <= 0:
            return TradeSignal(
                symbol=symbol,
                confidence=0.0,
                recommendation="avoid",
                reason="insufficient data",
                stop_loss=0.0,
                take_profit=0.0,
                current_price=current_price,
                strategy_name=self.name,
            )

        close = history["Close"].astype(float)
        high = history["High"].astype(float)
        volume = history["Volume"].astype(float)

        rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
        macd = MACD(close).macd_diff().iloc[-1]
        sma20 = SMAIndicator(close, window=20).sma_indicator().iloc[-1]
        sma50 = SMAIndicator(close, window=50).sma_indicator().iloc[-1]

        avg_volume = volume.rolling(20).mean().iloc[-1]
        relative_volume = float(volume.iloc[-1] / avg_volume) if avg_volume > 0 else 0.0

        recent_resistance = high.shift(1).rolling(window=20).max().iloc[-1]
        breakout = current_price > recent_resistance if recent_resistance > 0 else False

        confidence = 0.0
        reasons: list[str] = []

        if latest_change_pct >= 0:
            confidence += min(latest_change_pct, 15) * 2
            reasons.append(f"{latest_change_pct:.1f}% move")
        if relative_volume >= 1.0:
            confidence += min(relative_volume, 3) * 10
            reasons.append(f"relative volume {relative_volume:.2f}")
        if breakout:
            confidence += 20
            reasons.append("breakout")
        if macd > 0:
            confidence += 15
            reasons.append("MACD positive")
        if 40 < rsi < 70:
            confidence += 10
            reasons.append(f"RSI {float(rsi):.0f}")
        if current_price > sma20 > sma50:
            confidence += 10
            reasons.append("trend aligned")
        if news_sentiment is not None and news_sentiment > 0:
            confidence += 10
            reasons.append("positive news")

        confidence = min(max(confidence, 0.0), 100.0)
        recommendation = "avoid"
        if confidence >= 85 and breakout:
            recommendation = "buy"
        elif confidence >= 60:
            recommendation = "watch"

        stop_loss = round(current_price * 0.96, 6)
        take_profit = round(current_price * 1.12, 6)
        reason_text = "; ".join(reasons) if reasons else "no strong momentum"

        return TradeSignal(
            symbol=symbol,
            confidence=confidence,
            recommendation=recommendation,
            reason=reason_text,
            stop_loss=stop_loss,
            take_profit=take_profit,
            current_price=current_price,
            strategy_name=self.name,
        )
