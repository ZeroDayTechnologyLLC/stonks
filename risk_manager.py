from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskManager:
    max_risk_pct: float = 0.01
    max_position_pct: float = 0.25
    daily_loss_limit_pct: float = 0.05

    def should_trade(self, account_value: float, daily_loss_pct: float, confidence: float, threshold: float) -> bool:
        if account_value <= 0:
            return False
        if daily_loss_pct >= self.daily_loss_limit_pct:
            return False
        if confidence < threshold:
            return False
        return True

    def calculate_quantity(
        self,
        account_value: float,
        current_price: float,
        stop_loss: float,
    ) -> Optional[float]:
        if account_value <= 0 or current_price <= 0 or stop_loss <= 0 or stop_loss >= current_price:
            return None

        max_position_value = account_value * self.max_position_pct
        risk_capital = account_value * self.max_risk_pct
        risk_per_unit = current_price - stop_loss
        if risk_per_unit <= 0:
            return None

        quantity_by_risk = risk_capital / risk_per_unit
        quantity_by_position = max_position_value / current_price
        quantity = min(quantity_by_risk, quantity_by_position)
        if quantity < 0.000001:
            return None
        return round(quantity, 6)

    def calculate_daily_loss_pct(self, starting_balance: float, current_balance: float) -> float:
        if starting_balance <= 0:
            return 0.0
        loss = starting_balance - current_balance
        return max(loss / starting_balance, 0.0)
