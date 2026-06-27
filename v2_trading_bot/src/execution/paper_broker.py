from datetime import datetime
from typing import Optional

from ..config import AppConfig
from ..models import Bar, BracketOrder, ExitReason, OrderStatus, Side, Signal
from ..utils.session import parse_hhmm, to_session_time


class PaperBroker:
    """
    Paper broker / backtest execution simulator.

    Responsibilities:
    - open one bracket order at a time
    - check stop/target exits on each bar
    - force session flatten
    - calculate MES PnL with commission
    - preserve research metadata from the signal
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.open_order: Optional[BracketOrder] = None
        self.closed_orders: list[BracketOrder] = []
        self._order_counter = 0

    def place_bracket_order(
        self,
        signal: Signal,
        qty: int,
        entry_price: float,
        stop_price: float,
        target_price: float,
        opened_at: datetime,
    ) -> BracketOrder:
        if self.open_order is not None:
            raise RuntimeError("Cannot open a new order while another order is open.")

        self._order_counter += 1
        order_id = f"PAPER-{self._order_counter:06d}"

        order = BracketOrder(
            order_id=order_id,
            side=signal.side,
            qty=qty,
            entry_price=entry_price,
            stop_price=stop_price,
            target_price=target_price,
            opened_at=opened_at,
            strategy_name=signal.strategy_name,
            signal_reason=signal.reason,
            signal_score=self._extract_signal_score(signal.reason),
            setup_components=self._extract_setup_components(signal.reason),
            status=OrderStatus.OPEN,
        )

        self.open_order = order
        return order

    def on_bar(self, bar: Bar) -> Optional[BracketOrder]:
        if self.open_order is None:
            return None

        self.open_order.bars_held += 1

        order = self.open_order
        session_time = to_session_time(bar.timestamp, self.cfg.session.timezone)
        flatten_time = parse_hhmm(self.cfg.session.flatten_by)

        if session_time >= flatten_time:
            return self._close(
                bar=bar,
                exit_price=bar.close,
                reason=ExitReason.SESSION_FLATTEN,
            )

        if order.side == Side.LONG:
            stop_hit = bar.low <= order.stop_price
            target_hit = bar.high >= order.target_price

            # Conservative assumption:
            # if both stop and target are inside same candle, assume stop hit first.
            if stop_hit:
                return self._close(
                    bar=bar,
                    exit_price=order.stop_price,
                    reason=ExitReason.STOP_LOSS,
                )

            if target_hit:
                return self._close(
                    bar=bar,
                    exit_price=order.target_price,
                    reason=ExitReason.TAKE_PROFIT,
                )

        if order.side == Side.SHORT:
            stop_hit = bar.high >= order.stop_price
            target_hit = bar.low <= order.target_price

            # Conservative assumption:
            # if both stop and target are inside same candle, assume stop hit first.
            if stop_hit:
                return self._close(
                    bar=bar,
                    exit_price=order.stop_price,
                    reason=ExitReason.STOP_LOSS,
                )

            if target_hit:
                return self._close(
                    bar=bar,
                    exit_price=order.target_price,
                    reason=ExitReason.TAKE_PROFIT,
                )

        return None

    def _close(
        self,
        bar: Bar,
        exit_price: float,
        reason: ExitReason,
    ) -> BracketOrder:
        if self.open_order is None:
            raise RuntimeError("No open order to close.")

        order = self.open_order
        order.status = OrderStatus.CLOSED
        order.closed_at = bar.timestamp
        order.exit_price = exit_price
        order.exit_reason = reason
        order.pnl = self._calculate_pnl(order)

        self.closed_orders.append(order)
        self.open_order = None

        return order

    def _calculate_pnl(self, order: BracketOrder) -> float:
        points = order.exit_price - order.entry_price

        if order.side == Side.SHORT:
            points *= -1

        gross_pnl = points * self.cfg.instrument.point_value * order.qty
        commission = getattr(self.cfg.risk, "commission_per_round_trip", 0.0)

        return round(gross_pnl - commission, 2)

    def _extract_signal_score(self, reason: str) -> int:
        """
        Pulls score number out of strings like:
        'Long confluence score=2: EMA/VWAP trend pullback'
        """

        marker = "score="

        if marker not in reason:
            return 0

        after_marker = reason.split(marker, 1)[1]
        score_text = after_marker.split(":", 1)[0].strip()

        try:
            return int(score_text)
        except ValueError:
            return 0

    def _extract_setup_components(self, reason: str) -> str:
        """
        Pulls setup components out of strings like:
        'Short confluence score=4: liquidity sweep reject; failed breakout reject'
        """

        if ":" not in reason:
            return reason

        return reason.split(":", 1)[1].strip()