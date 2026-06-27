from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from ..config import AppConfig
from ..indicators import round_to_tick
from ..models import BracketOrder, ExitReason, Side, TradeDecision


@dataclass
class DailyRiskState:
    day: date
    realized_pnl: float = 0.0
    trades_taken: int = 0
    consecutive_losses: int = 0
    locked: bool = False
    lock_reason: str = ""

    # Cooldown state.
    # After a stop loss, the bot pauses before taking another trade.
    last_stop_loss_at: Optional[datetime] = None


class RiskManager:
    """
    Prop-firm style risk guardrails.

    This class is intentionally strict. The purpose is not to maximize entries.
    The purpose is to prevent one bad bot day from destroying an evaluation.

    Current protections:
    - one trade at a time
    - daily loss limit
    - max trades per day
    - max consecutive losses
    - cooldown after stop loss
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.state = DailyRiskState(day=date.today())

    def reset_new_day(self, current_day: date) -> None:
        if current_day != self.state.day:
            self.state = DailyRiskState(day=current_day)

    def lock(self, reason: str) -> None:
        self.state.locked = True
        self.state.lock_reason = reason

    def can_enter(
        self,
        open_order: Optional[BracketOrder],
        current_time: Optional[datetime] = None,
    ) -> TradeDecision:
        if self.state.locked:
            return TradeDecision(False, f"BOT LOCKED: {self.state.lock_reason}")

        if open_order is not None:
            return TradeDecision(False, "Open position exists. One trade at a time only.")

        cooldown_decision = self._cooldown_check(current_time)

        if not cooldown_decision.allowed:
            return cooldown_decision

        if self.state.realized_pnl <= -abs(self.cfg.risk.max_daily_loss_dollars):
            self.lock("Daily bot loss limit hit.")
            return TradeDecision(False, "Daily bot loss limit hit.")

        if self.state.trades_taken >= self.cfg.risk.max_trades_per_day:
            return TradeDecision(False, "Max trades per day reached.")

        if self.state.consecutive_losses >= self.cfg.risk.max_consecutive_losses:
            self.lock("Max consecutive losses hit.")
            return TradeDecision(False, "Max consecutive losses hit.")

        return TradeDecision(True, "OK")

    def build_bracket_prices(self, side: Side, entry_price: float) -> tuple[float, float]:
        tick = self.cfg.instrument.tick_size
        sl_offset = self.cfg.risk.stop_loss_ticks * tick
        tp_offset = self.cfg.risk.take_profit_ticks * tick

        if side == Side.LONG:
            stop = entry_price - sl_offset
            target = entry_price + tp_offset
        else:
            stop = entry_price + sl_offset
            target = entry_price - tp_offset

        return round_to_tick(stop, tick), round_to_tick(target, tick)

    def register_closed_trade(self, order: BracketOrder) -> None:
        self.state.realized_pnl += order.pnl
        self.state.trades_taken += 1

        if order.pnl < 0:
            self.state.consecutive_losses += 1
        else:
            self.state.consecutive_losses = 0

        if order.exit_reason == ExitReason.STOP_LOSS and order.closed_at is not None:
            self.state.last_stop_loss_at = order.closed_at

        if self.state.realized_pnl <= -abs(self.cfg.risk.max_daily_loss_dollars):
            self.lock("Daily bot loss limit hit after trade close.")

        if self.state.consecutive_losses >= self.cfg.risk.max_consecutive_losses:
            self.lock("Consecutive loss limit hit after trade close.")

    def _cooldown_check(self, current_time: Optional[datetime]) -> TradeDecision:
        if current_time is None:
            return TradeDecision(True, "OK")

        if self.state.last_stop_loss_at is None:
            return TradeDecision(True, "OK")

        cooldown_minutes = getattr(self.cfg.risk, "cooldown_after_loss_minutes", 0)

        if cooldown_minutes <= 0:
            return TradeDecision(True, "OK")

        cooldown_until = self.state.last_stop_loss_at + timedelta(minutes=cooldown_minutes)

        if current_time < cooldown_until:
            return TradeDecision(
                False,
                f"Cooldown active after stop loss until {cooldown_until.isoformat()}",
            )

        return TradeDecision(True, "OK")