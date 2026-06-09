import sqlite3
from pathlib import Path
from typing import Any, Optional


def _dict_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> dict[str, Any]:
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = _dict_factory
            cursor = connection.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    confidence REAL NOT NULL,
                    strategy TEXT NOT NULL,
                    status TEXT NOT NULL,
                    opened_at TEXT NOT NULL,
                    closed_at TEXT,
                    pnl REAL,
                    notes TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS account_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    account_value REAL NOT NULL,
                    buying_power REAL,
                    unrealized_pl REAL,
                    daily_loss_pct REAL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS order_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    symbol TEXT,
                    detail TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def record_trade(self, trade_data: dict[str, Any]) -> int:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO trades (
                    symbol, side, quantity, entry_price, exit_price,
                    stop_loss, take_profit, confidence, strategy, status,
                    opened_at, closed_at, pnl, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade_data["symbol"],
                    trade_data["side"],
                    trade_data["quantity"],
                    trade_data["entry_price"],
                    trade_data.get("exit_price"),
                    trade_data.get("stop_loss"),
                    trade_data.get("take_profit"),
                    trade_data.get("confidence", 0.0),
                    trade_data.get("strategy", "unknown"),
                    trade_data["status"],
                    trade_data["opened_at"],
                    trade_data.get("closed_at"),
                    trade_data.get("pnl"),
                    trade_data.get("notes", ""),
                ),
            )
            connection.commit()
            return cursor.lastrowid

    def update_trade(self, trade_id: int, updates: dict[str, Any]) -> None:
        columns = ", ".join(f"{key} = ?" for key in updates.keys())
        values = list(updates.values())
        values.append(trade_id)

        with sqlite3.connect(self.path) as connection:
            cursor = connection.cursor()
            cursor.execute(f"UPDATE trades SET {columns} WHERE id = ?", values)
            connection.commit()

    def record_account_snapshot(self, snapshot: dict[str, Any]) -> None:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO account_snapshots (
                    timestamp, account_value, buying_power, unrealized_pl, daily_loss_pct
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot["timestamp"],
                    snapshot["account_value"],
                    snapshot.get("buying_power"),
                    snapshot.get("unrealized_pl"),
                    snapshot.get("daily_loss_pct"),
                ),
            )
            connection.commit()

    def record_system_state(self, key: str, value: str, timestamp: str) -> None:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO system_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, timestamp),
            )
            connection.commit()

    def load_system_state(self, key: str) -> Optional[str]:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = _dict_factory
            cursor = connection.cursor()
            cursor.execute("SELECT value FROM system_state WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None

    def load_trade_history(self, limit: int = 100) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = _dict_factory
            cursor = connection.cursor()
            cursor.execute(
                "SELECT * FROM trades ORDER BY opened_at DESC LIMIT ?",
                (limit,),
            )
            return cursor.fetchall()

    def record_order_log(self, operation: str, detail: str, symbol: Optional[str] = None) -> None:
        with sqlite3.connect(self.path) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO order_logs (timestamp, operation, symbol, detail) VALUES (datetime('now'), ?, ?, ?)",
                (operation, symbol, detail),
            )
            connection.commit()
