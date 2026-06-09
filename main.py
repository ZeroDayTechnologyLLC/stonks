import argparse
from config import AppConfig
from logger import configure_logging
from database import Database
from broker import PaperBroker, RobinhoodBroker
from market_data import MarketDataClient
from alerts import AlertManager
from trade_engine import TradingBot

TEST_SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"]


def build_alert_manager(config: AppConfig) -> AlertManager:
    return AlertManager(
        smtp_server=config.email_smtp_server,
        smtp_port=config.email_smtp_port,
        smtp_user=config.email_smtp_user,
        smtp_password=config.email_smtp_password,
        recipients=config.alert_recipients,
    )


def build_broker(config: AppConfig):
    if config.enable_live_trading:
        return RobinhoodBroker(config)
    return PaperBroker(config)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crypto trading bot CLI")
    parser.add_argument(
        "mode",
        choices=["run", "cycle", "dashboard"],
        default="cycle",
        nargs="?",
        help="Operation mode: run continuous loop, cycle one scan, or launch dashboard.",
    )
    parser.add_argument(
        "--test-data",
        action="store_true",
        help="Print latest BTC, ETH, SOL, and DOGE prices from available market data providers.",
    )
    args = parser.parse_args()

    config = AppConfig.load()
    configure_logging(config.log_path)
    db = Database(config.database_path)
    broker = build_broker(config)
    alerts = build_alert_manager(config)
    data_client = MarketDataClient(config.market_data_provider)
    bot = TradingBot(config, broker, data_client, db, alerts)

    if args.test_data:
        print("Testing market data providers for crypto prices")
        for symbol in TEST_SYMBOLS:
            price = data_client.get_quote(symbol)
            if price is not None:
                print(f"{symbol}: ${price:.6f}")
            else:
                print(f"{symbol}: failed to retrieve price")
        return

    if args.mode == "run":
        bot.start()
    elif args.mode == "cycle":
        bot.run_cycle()
    else:
        print("Launch the Streamlit dashboard with: streamlit run dashboard.py")


if __name__ == "__main__":
    main()
