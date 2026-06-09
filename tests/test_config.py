import os

from config import AppConfig


def test_load_app_config_defaults(monkeypatch):
    monkeypatch.setenv("ENABLE_LIVE_TRADING", "false")
    monkeypatch.setenv("WATCHLIST", "BTC-USD,ETH-USD")
    monkeypatch.setenv("CONFIDENCE_THRESHOLD", "75.0")
    monkeypatch.delenv("ROBINHOOD_USERNAME", raising=False)
    monkeypatch.delenv("ROBINHOOD_PASSWORD", raising=False)

    config = AppConfig.load()

    assert config.enable_live_trading is False
    assert config.watchlist == ["BTC-USD", "ETH-USD"]
    assert config.confidence_threshold == 75.0
    assert config.max_risk_pct == 0.01
    assert config.max_position_pct == 0.25
    assert config.daily_loss_limit_pct == 0.05
