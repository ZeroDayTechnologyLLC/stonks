from dataclasses import dataclass, field
from pathlib import Path
import os
from typing import Optional, List, Union

from dotenv import load_dotenv


def parse_bool(value: Union[str, bool, None], default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def parse_float(value: Union[str, float, None], default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_list(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip().upper() for item in str(value).split(",") if item.strip()]


@dataclass
class AppConfig:
    robinhood_username: str
    robinhood_password: str
    enable_live_trading: bool = False
    watchlist: list[str] = field(default_factory=list)
    supported_symbols: list[str] = field(default_factory=lambda: ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"])
    enabled_strategies: list[str] = field(default_factory=lambda: ["momentum_breakout"])
    confidence_threshold: float = 70.0
    max_risk_pct: float = 0.01
    max_position_pct: float = 0.25
    daily_loss_limit_pct: float = 0.05
    stop_trading_on_loss: bool = True
    emergency_kill: bool = False
    email_smtp_server: str = ""
    email_smtp_port: int = 587
    email_smtp_user: str = ""
    email_smtp_password: str = ""
    alert_recipients: list[str] = field(default_factory=list)
    log_path: Path = field(default_factory=lambda: Path.cwd() / "logs" / "trading.log")
    database_path: Path = field(default_factory=lambda: Path.cwd() / "data" / "trading.db")
    market_data_provider: str = "auto"
    live_trading_warning: str = "LIVE TRADING ENABLED. THIS IS NOT FINANCIAL ADVICE. TRADING INVOLVES RISK."

    @staticmethod
    def load() -> "AppConfig":
        load_dotenv()

        return AppConfig(
            robinhood_username=os.getenv("ROBINHOOD_USERNAME", ""),
            robinhood_password=os.getenv("ROBINHOOD_PASSWORD", ""),
            enable_live_trading=parse_bool(os.getenv("ENABLE_LIVE_TRADING"), False),
            watchlist=parse_list(os.getenv("WATCHLIST")),
            supported_symbols=parse_list(os.getenv("SUPPORTED_SYMBOLS")) or ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"],
            enabled_strategies=parse_list(os.getenv("ENABLED_STRATEGIES")) or ["momentum_breakout"],
            market_data_provider=os.getenv("MARKET_DATA_PROVIDER", "auto").strip().lower() or "auto",
            confidence_threshold=parse_float(os.getenv("CONFIDENCE_THRESHOLD"), 70.0),
            max_risk_pct=parse_float(os.getenv("MAX_RISK_PCT"), 0.01),
            max_position_pct=parse_float(os.getenv("MAX_POSITION_PCT"), 0.25),
            daily_loss_limit_pct=parse_float(os.getenv("DAILY_LOSS_LIMIT_PCT"), 0.05),
            stop_trading_on_loss=parse_bool(os.getenv("STOP_TRADING_ON_LOSS"), True),
            emergency_kill=parse_bool(os.getenv("EMERGENCY_KILL"), False),
            email_smtp_server=os.getenv("EMAIL_SMTP_SERVER", ""),
            email_smtp_port=int(os.getenv("EMAIL_SMTP_PORT", "587")),
            email_smtp_user=os.getenv("EMAIL_SMTP_USER", ""),
            email_smtp_password=os.getenv("EMAIL_SMTP_PASSWORD", ""),
            alert_recipients=parse_list(os.getenv("ALERT_RECIPIENTS")),
            log_path=Path(os.getenv("LOG_PATH", "logs/trading.log")),
            database_path=Path(os.getenv("DATABASE_PATH", "data/trading.db")),
        )
