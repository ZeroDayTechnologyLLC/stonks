import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

try:
    from plyer import notification
except ImportError:
    notification = None


@dataclass
class AlertManager:
    smtp_server: str
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    recipients: list[str] = None

    def __post_init__(self) -> None:
        if self.recipients is None:
            self.recipients = []

    def send_email(self, subject: str, body: str) -> None:
        if not self.smtp_server or not self.smtp_user or not self.smtp_password or not self.recipients:
            logger.debug("Email alert skipped because SMTP settings are incomplete")
            return

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.smtp_user
        message["To"] = ", ".join(self.recipients)
        message.set_content(body)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=20) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)
                logger.info("Sent email alert: %s", subject)
        except Exception as exc:
            logger.exception("Failed to send email alert: %s", exc)

    def send_desktop(self, title: str, message: str) -> None:
        if notification is None:
            logger.debug("Desktop notifications unavailable")
            return
        try:
            notification.notify(title=title, message=message, timeout=10)
            logger.info("Displayed desktop notification: %s", title)
        except Exception as exc:
            logger.exception("Failed to send desktop notification: %s", exc)

    def _build_message(self, subject: str, details: Iterable[str]) -> str:
        return f"{subject}\n\n" + "\n".join(details)

    def notify_trade_opened(self, signal: "TradeSignal", paper_mode: bool) -> None:
        title = f"{'Paper' if paper_mode else 'Live'} trade opened: {signal.symbol}"
        details = [
            f"Confidence: {signal.confidence:.1f}",
            f"Price: {signal.current_price:.6f}",
            f"Stop loss: {signal.stop_loss:.6f}",
            f"Take profit: {signal.take_profit:.6f}",
            f"Strategy: {signal.strategy_name}",
            f"Reason: {signal.reason}",
        ]
        body = self._build_message(title, details)
        self.send_desktop(title, body)
        self.send_email(title, body)

    def notify_trade_closed(self, trade: dict, exit_price: float, pnl: float, reason: str) -> None:
        title = f"Trade closed: {trade['symbol']}"
        details = [
            f"Side: {trade['side']}",
            f"Entry: {trade['entry_price']:.6f}",
            f"Exit: {exit_price:.6f}",
            f"Quantity: {trade['quantity']}",
            f"PnL: {pnl:.6f}",
            f"Reason: {reason}",
        ]
        body = self._build_message(title, details)
        self.send_desktop(title, body)
        self.send_email(title, body)

    def notify_daily_limit_reached(self) -> None:
        title = "Daily loss limit reached"
        body = self._build_message(title, ["Trading has been paused for 24 hours.", "Review risk controls before resuming."])
        self.send_desktop(title, body)
        self.send_email(title, body)

    def notify_trading_disabled(self) -> None:
        title = "Live trading disabled"
        body = self._build_message(title, ["ENABLE_LIVE_TRADING is not enabled.", "Paper trading mode remains active."])
        self.send_desktop(title, body)
        self.send_email(title, body)
