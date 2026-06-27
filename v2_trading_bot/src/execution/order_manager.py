from typing import Optional
from ..config import AppConfig
from ..models import Bar, BracketOrder, ExitReason, Signal
from ..risk.risk_manager import RiskManager
from .paper_broker import PaperBroker


class OrderManager:
    def __init__(self, cfg: AppConfig, broker: PaperBroker, risk: RiskManager):
        self.cfg = cfg
        self.broker = broker
        self.risk = risk

    def manage_open_order(self, bar: Bar) -> Optional[BracketOrder]:
        # Broker-side bracket check first.
        closed = self.broker.on_bar(bar)
        if closed:
            self.risk.register_closed_trade(closed)
            return closed

        # Emergency fail-safe if the market blows beyond the stop.
        closed = self.broker.emergency_check(bar)
        if closed:
            self.risk.register_closed_trade(closed)
            self.risk.lock("Emergency flatten triggered.")
            return closed
        return None

    def enter_from_signal(self, signal: Signal, bar: Bar) -> tuple[Optional[BracketOrder], str]:
        decision = self.risk.can_enter(self.broker.open_order)
        if not decision.allowed:
            return None, decision.reason

        qty = self.cfg.risk.max_contracts
        entry = signal.entry_reference_price
        stop, target = self.risk.build_bracket_prices(signal.side, entry)
        order = self.broker.place_bracket_order(
            side=signal.side,
            qty=qty,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            strategy_name=signal.strategy_name,
            opened_at=bar.timestamp,
        )
        return order, "ORDER_PLACED"

    def session_flatten(self, bar: Bar) -> Optional[BracketOrder]:
        closed = self.broker.flatten_all(bar.close, bar.timestamp, ExitReason.SESSION_FLATTEN)
        if closed:
            self.risk.register_closed_trade(closed)
        return closed
