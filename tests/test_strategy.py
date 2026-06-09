import pandas as pd

from strategy import MomentumBreakoutStrategy


def create_test_history() -> pd.DataFrame:
    length = 30
    close = [100 + i * 0.5 for i in range(length)]
    high = [value + 1.0 for value in close]
    low = [value - 1.0 for value in close]
    open_values = [value - 0.5 for value in close]
    volume = [1000 + i * 20 for i in range(length)]

    return pd.DataFrame(
        {
            "Open": open_values,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }
    )


def test_momentum_breakout_strategy_generates_signal():
    history = create_test_history()
    signal = MomentumBreakoutStrategy().evaluate(
        symbol="BTC-USD",
        history=history,
        current_price=115.0,
        latest_change_pct=5.0,
        news_sentiment=0.5,
    )

    assert signal.symbol == "BTC-USD"
    assert signal.confidence >= 0
    assert signal.recommendation in {"buy", "watch", "avoid"}
    assert signal.stop_loss < signal.current_price
    assert signal.take_profit > signal.current_price
