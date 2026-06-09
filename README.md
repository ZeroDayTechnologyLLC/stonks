# Crypto Trading Bot

A Python-based crypto trading bot with optional Robinhood live trading mode, paper trading, and a Streamlit dashboard.

> **Disclaimer:** This system does not guarantee profits and is not financial advice. All trading involves risk. Trade only after reviewing controls.

## Features

- Live trading disabled by default
- Optional Robinhood crypto trading mode with `ENABLE_LIVE_TRADING=true`
- Supports Bitcoin, Ethereum, Solana, Dogecoin, and other Robinhood crypto symbols
- Paper trading mode for simulation
- 24/7 minute-based market scanning
- Technical signal generation with momentum, RSI, MACD, moving averages
- Risk management with position sizing, stop-loss, take-profit, and daily loss limits
- SQLite persistence for trades, account snapshots, system state, and logs
- Streamlit dashboard with account summary, positions, P/L, and trade history
- Email and desktop notifications for trade events and risk limits
- Configurable strategies and safe live trading defaults

## Project Structure

- `main.py` — CLI entrypoint for running the bot or one cycle
- `config.py` — environment-driven configuration loader
- `logger.py` — application logging setup
- `database.py` — SQLite persistence manager
- `broker.py` — Robinhood and paper broker abstractions
- `market_data.py` — market data collection with yfinance, Coinbase, and CoinGecko fallback
- `strategy.py` — signal generation and confidence scoring
- `risk_manager.py` — position sizing and daily risk checks
- `trade_engine.py` — trading loop, order execution, and monitoring
- `alerts.py` — email and desktop notification manager
- `dashboard.py` — Streamlit dashboard interface
- `requirements.txt` — Python dependencies
- `.env.example` — environment variable template
- `tests/` — unit tests for config, strategy, and risk manager

## Install

1. Open this folder in VS Code.
2. Create a Python virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Copy `.env.example` to `.env` and update your settings.

## Run

### Streamlit Dashboard

```powershell
streamlit run dashboard.py
```

### One Trading Cycle

```powershell
python main.py cycle
```

### Continuous Trading Loop

```powershell
python main.py run
```

### Market Data Smoke Test

```powershell
python main.py --test-data
```

This will print the latest BTC, ETH, SOL, and DOGE prices from the first working provider in the configured fallback list.

## Environment Variables

Use `.env` to configure the bot. Example values are in `.env.example`.

- `ENABLE_LIVE_TRADING` — must be `true` to enable live Robinhood mode
- `ROBINHOOD_USERNAME` — Robinhood account login email
- `ROBINHOOD_PASSWORD` — Robinhood account password
- `WATCHLIST` — comma-separated crypto symbols (e.g. `BTC-USD,ETH-USD`)
- `SUPPORTED_SYMBOLS` — fallback symbols for scan universe
- `MARKET_DATA_PROVIDER` — auto / yfinance / coinbase / coingecko
- `CONFIDENCE_THRESHOLD` — minimum signal confidence for execution
- `MAX_RISK_PCT` — percent of account risked per trade
- `MAX_POSITION_PCT` — max percent of account value per position
- `DAILY_LOSS_LIMIT_PCT` — stop trading if daily loss exceeds this
- `EMAIL_SMTP_SERVER` — SMTP host for alerts
- `EMAIL_SMTP_PORT` — SMTP port
- `EMAIL_SMTP_USER` — alert sender email
- `EMAIL_SMTP_PASSWORD` — alert SMTP password
- `ALERT_RECIPIENTS` — comma-separated recipient emails

## VS Code Notes

- Install the Python extension and select the `.venv` interpreter.
- Install Pylance for type hints and diagnostics.
- Use the built-in terminal to run the bot commands.
- Use `pytest` to run unit tests:

```powershell
pytest
```

## Risk Management

- No leverage
- No margin
- Max 1% risk per trade
- Max 25% position size
- Max daily loss limit 5%
- Pause trading for 24 hours after limit is reached
- Emergency kill switch support
- Stop-loss and take-profit orders enforced when possible

## Important

This bot is built for research and responsible live trading. It prioritizes capital preservation over aggressive profit seeking.
