import csv
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

from ..config import AppConfig
from ..execution.paper_broker import PaperBroker
from ..models import Bar, BracketOrder, Signal
from ..risk.risk_manager import RiskManager
from ..strategies.strategy_engine import StrategyEngine
from ..utils.logger import EventLogger


class Backtester:
    """
    Runs the bot candle-by-candle.

    Important execution realism fix:
    - A signal is created after a bar closes.
    - The trade is entered on the next bar's open.

    This avoids lookahead/fill bias from entering at the same close
    that generated the signal.
    """

    def __init__(self, cfg: AppConfig, bars: Iterable[Bar]):
        self.cfg = cfg
        self.bars = list(bars)

        self.events = EventLogger(cfg.event_log_file)
        self.risk = RiskManager(cfg)
        self.broker = PaperBroker(cfg)
        self.strategy = StrategyEngine(cfg)

        # Signal generated on prior bar close.
        # Filled on next bar open.
        self.pending_signal: Optional[Signal] = None
        self.pending_signal_day = None

    def run(self) -> dict:
        for bar in self.bars:
            self._on_bar(bar)

        self._write_trade_csv()

        return self.summary()

    def _on_bar(self, bar: Bar) -> None:
        current_day = bar.timestamp.date()
        old_day = self.risk.state.day

        self.risk.reset_new_day(current_day)

        if current_day != old_day:
            self.events.log(f"New session: {current_day}")

            # Do not carry yesterday's signal into a new session.
            self.pending_signal = None
            self.pending_signal_day = None

        # 1. Fill prior-bar signal at this bar's OPEN.
        self._try_fill_pending_signal(bar)

        # 2. Check whether the existing open trade hit stop, target, or flatten
        # during this bar.
        closed_order = self.broker.on_bar(bar)

        if closed_order is not None:
            self.risk.register_closed_trade(closed_order)

            if closed_order.exit_reason is not None:
                self.events.log(
                    f"Closed {closed_order.order_id}: "
                    f"{closed_order.exit_reason.value} "
                    f"PnL=${closed_order.pnl:.2f}"
                )
            else:
                self.events.log(
                    f"Closed {closed_order.order_id}: "
                    f"PnL=${closed_order.pnl:.2f}"
                )

        # 3. Update strategy indicators with this completed bar.
        self.strategy.on_bar(bar)

        # 4. Generate signal from this bar close.
        # It will NOT enter now. It enters on the next bar open.
        signal = self.strategy.get_signal(bar)

        if signal is not None:
            self.pending_signal = signal
            self.pending_signal_day = current_day

    def _try_fill_pending_signal(self, bar: Bar) -> None:
        if self.pending_signal is None:
            return

        # Do not fill stale signal from a previous day.
        if self.pending_signal_day != bar.timestamp.date():
            self.pending_signal = None
            self.pending_signal_day = None
            return

        signal = self.pending_signal

        decision = self.risk.can_enter(self.broker.open_order, bar.timestamp)

        if not decision.allowed:
            if getattr(self.cfg.report, "print_rejected_signals", True):
                self.events.log(f"Pending signal rejected: {decision.reason}")

            self.pending_signal = None
            self.pending_signal_day = None
            return

        # Realistic backtest entry:
        # signal formed on prior close, filled at next bar open.
        entry_price = bar.open

        stop_price, target_price = self.risk.build_bracket_prices(
            signal.side,
            entry_price,
        )

        order = self.broker.place_bracket_order(
            signal=signal,
            qty=self.cfg.risk.max_contracts,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            opened_at=bar.timestamp,
        )

        self.events.log(
            f"OPEN {order.order_id} {order.side.value} {order.qty}x "
            f"entry={order.entry_price:.2f} "
            f"stop={order.stop_price:.2f} "
            f"target={order.target_price:.2f} "
            f"strategy={order.strategy_name} | "
            f"{order.signal_reason}"
        )

        self.pending_signal = None
        self.pending_signal_day = None

    def summary(self) -> dict:
        orders = self.broker.closed_orders

        if not orders:
            return {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
                "by_strategy": {},
                "by_side": {},
                "by_score": {},
                "by_setup_component": {},
                "by_exit_reason": {},
                "by_day": {},
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "max_drawdown": 0.0,
                "longest_win_streak": 0,
                "longest_loss_streak": 0,
                "avg_bars_held": 0.0,
            }

        total_pnl = round(sum(order.pnl for order in orders), 2)
        wins = [order for order in orders if order.pnl > 0]
        losses = [order for order in orders if order.pnl < 0]

        gross_profit = sum(order.pnl for order in wins)
        gross_loss = abs(sum(order.pnl for order in losses))

        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0.0
        avg_win = round(gross_profit / len(wins), 2) if wins else 0.0
        avg_loss = round(sum(order.pnl for order in losses) / len(losses), 2) if losses else 0.0

        return {
            "trades": len(orders),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round((len(wins) / len(orders)) * 100, 2),
            "total_pnl": total_pnl,
            "avg_pnl": round(total_pnl / len(orders), 2),
            "by_strategy": self._pnl_by(orders, lambda order: order.strategy_name),
            "by_side": self._pnl_by(orders, lambda order: order.side.value),
            "by_score": self._pnl_by(orders, lambda order: f"score_{order.signal_score}"),
            "by_setup_component": self._pnl_by_setup_component(orders),
            "by_exit_reason": self._pnl_by(
                orders,
                lambda order: order.exit_reason.value if order.exit_reason else "UNKNOWN",
            ),
            "by_day": self._pnl_by(
                orders,
                lambda order: order.opened_at.date().isoformat(),
            ),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "max_drawdown": self._max_drawdown(orders),
            "longest_win_streak": self._longest_streak(orders, winning=True),
            "longest_loss_streak": self._longest_streak(orders, winning=False),
            "avg_bars_held": self._avg_bars_held(orders),
        }

    def _write_trade_csv(self) -> None:
        path = Path(self.cfg.trade_log_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "order_id",
            "opened_at",
            "closed_at",
            "side",
            "strategy_name",
            "signal_score",
            "setup_components",
            "signal_reason",
            "qty",
            "entry_price",
            "stop_price",
            "target_price",
            "exit_price",
            "exit_reason",
            "pnl",
            "bars_held",
        ]

        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()

            for order in self.broker.closed_orders:
                writer.writerow(
                    {
                        "order_id": order.order_id,
                        "opened_at": order.opened_at.isoformat() if order.opened_at else "",
                        "closed_at": order.closed_at.isoformat() if order.closed_at else "",
                        "side": order.side.value,
                        "strategy_name": order.strategy_name,
                        "signal_score": order.signal_score,
                        "setup_components": order.setup_components,
                        "signal_reason": order.signal_reason,
                        "qty": order.qty,
                        "entry_price": order.entry_price,
                        "stop_price": order.stop_price,
                        "target_price": order.target_price,
                        "exit_price": order.exit_price if order.exit_price is not None else "",
                        "exit_reason": order.exit_reason.value if order.exit_reason else "",
                        "pnl": order.pnl,
                        "bars_held": order.bars_held,
                    }
                )

    def _pnl_by(self, orders: list[BracketOrder], key_func) -> dict:
        result = defaultdict(float)

        for order in orders:
            key = key_func(order)
            result[key] += order.pnl

        return {key: round(value, 2) for key, value in result.items()}

    def _pnl_by_setup_component(self, orders: list[BracketOrder]) -> dict:
        result = defaultdict(float)

        for order in orders:
            components = order.setup_components.split(";")

            for component in components:
                clean_component = component.strip()

                if not clean_component:
                    clean_component = "UNKNOWN"

                result[clean_component] += order.pnl

        return {key: round(value, 2) for key, value in result.items()}

    def _max_drawdown(self, orders: list[BracketOrder]) -> float:
        equity = 0.0
        peak = 0.0
        max_drawdown = 0.0

        for order in orders:
            equity += order.pnl
            peak = max(peak, equity)
            drawdown = peak - equity
            max_drawdown = max(max_drawdown, drawdown)

        return round(max_drawdown, 2)

    def _longest_streak(self, orders: list[BracketOrder], winning: bool) -> int:
        longest = 0
        current = 0

        for order in orders:
            is_target_type = order.pnl > 0 if winning else order.pnl < 0

            if is_target_type:
                current += 1
                longest = max(longest, current)
            else:
                current = 0

        return longest

    def _avg_bars_held(self, orders: list[BracketOrder]) -> float:
        if not orders:
            return 0.0

        total_bars = sum(order.bars_held for order in orders)
        return round(total_bars / len(orders), 2)