from risk_manager import RiskManager


def test_calculate_quantity_returns_none_for_invalid_input():
    manager = RiskManager()
    assert manager.calculate_quantity(0, 10, 9) is None
    assert manager.calculate_quantity(100000, 0, -1) is None
    assert manager.calculate_quantity(100000, 100, 100) is None


def test_calculate_quantity_limits_position_size():
    manager = RiskManager(max_risk_pct=0.01, max_position_pct=0.25)
    quantity = manager.calculate_quantity(100000, 100, 95)
    assert quantity is not None
    assert quantity <= 250


def test_should_trade_considers_threshold_and_daily_loss():
    manager = RiskManager(daily_loss_limit_pct=0.05)
    assert manager.should_trade(100000, 0.01, 80, 70)
    assert not manager.should_trade(100000, 0.06, 90, 70)
    assert not manager.should_trade(100000, 0.01, 60, 70)
