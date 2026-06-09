import streamlit as st
from pathlib import Path
from typing import Any, Optional

from alerts import AlertManager
from broker import PaperBroker, RobinhoodBroker
from config import AppConfig
from database import Database
from logger import configure_logging
from market_data import MarketDataClient
from trade_engine import TradingBot


def main() -> None:
    config = AppConfig.load()
    configure_logging(config.log_path)
    db = Database(config.database_path)
    data_client = MarketDataClient()

    if config.enable_live_trading:
        broker = RobinhoodBroker(config)
        try:
            broker.login()
        except Exception as exc:
            st.error(f"Live trading login failed: {exc}")
            broker = PaperBroker(config)
    else:
        broker = PaperBroker(config)

    alerts = AlertManager(
        smtp_server=config.email_smtp_server,
        smtp_port=config.email_smtp_port,
        smtp_user=config.email_smtp_user,
        smtp_password=config.email_smtp_password,
        recipients=config.alert_recipients,
    )
    bot = TradingBot(config, broker, data_client, db, alerts)

    st.set_page_config(page_title="Crypto Trading Bot", page_icon="💱", layout="wide")
    st.title("Crypto Trading Bot Dashboard")
    st.markdown(
        "This dashboard monitors crypto signals and live paper trading state. "
        "Trading is disabled by default until `ENABLE_LIVE_TRADING=true` is set in `.env`."
    )
    st.warning(
        "THIS IS NOT FINANCIAL ADVICE. ALL TRADING INVOLVES RISK. REVIEW RISK CONTROLS BEFORE TRADING."
    )

    account = broker.get_account_summary()
    trades = db.load_trade_history(limit=100)
    cycle_summary: Optional[dict[str, Any]] = None
    if config.enable_live_trading:
        positions = broker.get_positions()
    else:
        positions = db.load_open_trades()

    st.sidebar.header("Controls")
    if st.sidebar.button("Run one scan cycle"):
        with st.spinner("Running one trading cycle..."):
            cycle_summary = bot.run_cycle()
        trades = db.load_trade_history(limit=100)
        account = broker.get_account_summary()
        positions = broker.get_positions() if config.enable_live_trading else db.load_open_trades()

        if cycle_summary and cycle_summary.get("trades_placed", 0) > 0:
            st.success(f"Cycle complete. {cycle_summary['trades_placed']} new trade(s) recorded.")
        else:
            st.info("Cycle complete. No trades were placed this cycle.")

    cols = st.columns(3)
    cols[0].metric("Account Value", f"${account['account_value']:.2f}")
    cols[1].metric("Buying Power", f"${account['buying_power']:.2f}")
    cols[2].metric("Live Trading", str(config.enable_live_trading))

    st.subheader("Open Positions")
    if positions:
        st.dataframe(positions)
    else:
        st.write("No open positions.")

    st.subheader("Recent Trades")
    st.dataframe(trades)

    st.sidebar.markdown("### Watchlist")
    st.sidebar.write(config.watchlist or config.supported_symbols)
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**Warnings**\n\n"
        "- Live trading is disabled unless `ENABLE_LIVE_TRADING=true`.\n"
        "- Do not use leverage or margin.\n"
        "- This is a research and paper-trading system."
    )


if __name__ == "__main__":
    main()
