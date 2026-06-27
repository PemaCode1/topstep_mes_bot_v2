from src.config import AppConfig, BotMode
from src.data.demo_data import generate_demo_mes_bars
from src.data.csv_feed import load_bars_from_csv
from src.backtest.backtester import Backtester
import argparse
import json
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="Topstep MES Bot V1 — safe paper/backtest build")
    parser.add_argument("--csv", help="Optional CSV path with timestamp,open,high,low,close,volume")
    parser.add_argument("--days", type=int, default=5, help="Demo fake-market days if no CSV is provided")
    args = parser.parse_args()

    cfg = AppConfig(mode=BotMode.BACKTEST)
    os.makedirs(cfg.log_dir, exist_ok=True)

    if args.csv:
        bars = load_bars_from_csv(args.csv)
    else:
        bars = generate_demo_mes_bars(days=args.days)

    summary = Backtester(cfg, bars).run()
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print("\nTrade log:", cfg.trade_log_file)
    print("Event log:", cfg.event_log_file)


if __name__ == "__main__":
    main()
