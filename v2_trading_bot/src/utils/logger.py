import csv
import os
from datetime import datetime
from typing import Optional
from ..models import BracketOrder


class EventLogger:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def log(self, message: str, level: str = "INFO") -> None:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] [{level}] {message}"
        print(line)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


class TradeLogger:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "order_id", "strategy", "side", "qty", "opened_at", "closed_at",
                    "entry", "stop", "target", "exit_price", "exit_reason", "pnl"
                ])

    def record(self, order: BracketOrder) -> None:
        with open(self.path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                order.order_id,
                order.strategy_name,
                order.side.value,
                order.qty,
                order.opened_at.isoformat(),
                order.closed_at.isoformat() if order.closed_at else "",
                order.entry_price,
                order.stop_price,
                order.target_price,
                order.exit_price if order.exit_price is not None else "",
                order.exit_reason.value if order.exit_reason else "",
                round(order.pnl, 2),
            ])
