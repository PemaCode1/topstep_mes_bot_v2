from collections import deque
from typing import Optional
from zoneinfo import ZoneInfo

from ..config import AppConfig
from ..indicators import ema, vwap_and_std
from ..models import Bar, Signal, Side


class ConfluenceEngine:
    """
    Stable V2 strategy brain with session-based indicators.

    Core playbooks:
    1. EMA/VWAP trend pullback
    2. Liquidity sweep / failed breakout

    Important fix:
    EMA, VWAP, swing highs/lows, and failed breakout logic now use
    only the current CME/Chicago trading date.

    Why:
    MES trades on CME, which uses Chicago/Central Time.
    Raw timestamp.date() can group bars by the wrong day if the timestamp
    is UTC or another timezone.
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.bars: deque[Bar] = deque(maxlen=500)
        self.last_signal_bar_ts = None
        self.exchange_tz = ZoneInfo("America/Chicago")

    def on_bar(self, bar: Bar) -> None:
        self.bars.append(bar)

    def signal(self, bar: Bar) -> Optional[Signal]:
        if not getattr(self.cfg.strategy, "enable_confluence_engine", False):
            return None

        # Prevent duplicate signals on the same candle.
        if self.last_signal_bar_ts == bar.timestamp:
            return None

        all_bars = list(self.bars)
        bars = self._current_session_bars(all_bars)

        min_bars = max(
            self.cfg.strategy.ema_slow + 5,
            self.cfg.strategy.swing_lookback_bars + 5,
            getattr(self.cfg.strategy, "failed_breakout_lookback_bars", 10) + 5,
            40,
        )

        if len(bars) < min_bars:
            return None

        closes = [b.close for b in bars]

        fast = ema(closes, self.cfg.strategy.ema_fast)
        slow = ema(closes, self.cfg.strategy.ema_slow)
        vwap, _ = vwap_and_std(bars)

        if fast is None or slow is None or vwap is None:
            return None

        long_score, long_reasons = self._score_long(
            bar=bar,
            bars=bars,
            fast=fast,
            slow=slow,
            vwap=vwap,
        )

        short_score, short_reasons = self._score_short(
            bar=bar,
            bars=bars,
            fast=fast,
            slow=slow,
            vwap=vwap,
        )

        threshold = self.cfg.strategy.min_score_to_trade

        if long_score >= threshold and long_score > short_score:
            self.last_signal_bar_ts = bar.timestamp
            return Signal(
                side=Side.LONG,
                strategy_name="CONFLUENCE_LONG",
                entry_reference_price=bar.close,
                confidence=self._confidence(long_score),
                reason=f"Long confluence score={long_score}: " + "; ".join(long_reasons),
            )

        if short_score >= threshold and short_score > long_score:
            self.last_signal_bar_ts = bar.timestamp
            return Signal(
                side=Side.SHORT,
                strategy_name="CONFLUENCE_SHORT",
                entry_reference_price=bar.close,
                confidence=self._confidence(short_score),
                reason=f"Short confluence score={short_score}: " + "; ".join(short_reasons),
            )

        return None

    def _score_long(
        self,
        bar: Bar,
        bars: list[Bar],
        fast: float,
        slow: float,
        vwap: float,
    ) -> tuple[int, list[str]]:
        score = 0
        reasons = []

        tick = self.cfg.instrument.tick_size
        candle_ticks = self._candle_ticks(bar)

        bullish = bar.close > bar.open
        trend_up = fast > slow
        above_vwap = bar.close > vwap

        if not self._valid_candle_size(candle_ticks):
            return 0, []

        # Playbook 1: EMA/VWAP trend pullback.
        if self.cfg.strategy.enable_ema_vwap_pullback:
            tolerance = self.cfg.strategy.ema_pullback_tolerance_ticks * tick

            touched_fast_ema = (
                bar.low <= fast + tolerance
                and bar.high >= fast - tolerance
            )

            if trend_up and above_vwap and touched_fast_ema and bullish and bar.close > fast:
                score += 2
                reasons.append("EMA/VWAP trend pullback")

        # Playbook 2A: liquidity sweep reclaim.
        if self.cfg.strategy.enable_liquidity_sweep:
            if self._swept_low_and_reclaimed(bar, bars):
                score += 2
                reasons.append("liquidity sweep reclaim")

        # Playbook 2B: failed breakdown reclaim.
        if getattr(self.cfg.strategy, "enable_failed_breakout", True):
            if self._failed_breakout_long(bar, bars):
                score += 2
                reasons.append("failed breakdown reclaim")

        return score, reasons

    def _score_short(
        self,
        bar: Bar,
        bars: list[Bar],
        fast: float,
        slow: float,
        vwap: float,
    ) -> tuple[int, list[str]]:
        score = 0
        reasons = []

        tick = self.cfg.instrument.tick_size
        candle_ticks = self._candle_ticks(bar)

        bearish = bar.close < bar.open
        trend_down = fast < slow
        below_vwap = bar.close < vwap

        if not self._valid_candle_size(candle_ticks):
            return 0, []

        # Playbook 1: EMA/VWAP trend pullback.
        if self.cfg.strategy.enable_ema_vwap_pullback:
            tolerance = self.cfg.strategy.ema_pullback_tolerance_ticks * tick

            touched_fast_ema = (
                bar.low <= fast + tolerance
                and bar.high >= fast - tolerance
            )

            if trend_down and below_vwap and touched_fast_ema and bearish and bar.close < fast:
                score += 2
                reasons.append("EMA/VWAP trend pullback")

        # Playbook 2A: liquidity sweep reject.
        if self.cfg.strategy.enable_liquidity_sweep:
            if self._swept_high_and_rejected(bar, bars):
                score += 2
                reasons.append("liquidity sweep reject")

        # Playbook 2B: failed breakout reject.
        if getattr(self.cfg.strategy, "enable_failed_breakout", True):
            if self._failed_breakout_short(bar, bars):
                score += 2
                reasons.append("failed breakout reject")

        return score, reasons

    def _valid_candle_size(self, candle_ticks: int) -> bool:
        return (
            candle_ticks >= self.cfg.strategy.min_signal_candle_ticks
            and candle_ticks <= self.cfg.strategy.max_signal_candle_ticks
        )

    def _candle_ticks(self, bar: Bar) -> int:
        tick = self.cfg.instrument.tick_size
        return int(round(abs(bar.close - bar.open) / tick))

    def _recent_swing_low(self, bars: list[Bar]) -> float:
        lookback = self.cfg.strategy.swing_lookback_bars
        previous = bars[-lookback - 1:-1]
        return min(b.low for b in previous)

    def _recent_swing_high(self, bars: list[Bar]) -> float:
        lookback = self.cfg.strategy.swing_lookback_bars
        previous = bars[-lookback - 1:-1]
        return max(b.high for b in previous)

    def _swept_low_and_reclaimed(self, bar: Bar, bars: list[Bar]) -> bool:
        swing_low = self._recent_swing_low(bars)

        return (
            bar.low < swing_low
            and bar.close > swing_low
            and bar.close > bar.open
        )

    def _swept_high_and_rejected(self, bar: Bar, bars: list[Bar]) -> bool:
        swing_high = self._recent_swing_high(bars)

        return (
            bar.high > swing_high
            and bar.close < swing_high
            and bar.close < bar.open
        )

    def _failed_breakout_long(self, bar: Bar, bars: list[Bar]) -> bool:
        """
        Long failed breakdown:
        - price breaks below recent range low
        - price fails to continue lower
        - candle closes back above the prior low
        """

        lookback = getattr(self.cfg.strategy, "failed_breakout_lookback_bars", 10)
        previous = bars[-lookback - 1:-1]

        if len(previous) < lookback:
            return False

        range_low = min(b.low for b in previous)

        return (
            bar.low < range_low
            and bar.close > range_low
            and bar.close > bar.open
        )

    def _failed_breakout_short(self, bar: Bar, bars: list[Bar]) -> bool:
        """
        Short failed breakout:
        - price breaks above recent range high
        - price fails to continue higher
        - candle closes back below the prior high
        """

        lookback = getattr(self.cfg.strategy, "failed_breakout_lookback_bars", 10)
        previous = bars[-lookback - 1:-1]

        if len(previous) < lookback:
            return False

        range_high = max(b.high for b in previous)

        return (
            bar.high > range_high
            and bar.close < range_high
            and bar.close < bar.open
        )

    def _current_session_bars(self, bars: list[Bar]) -> list[Bar]:
        """
        Returns only bars from the current CME/Chicago trading date.

        This keeps VWAP, EMA, swing highs/lows, and failed breakout logic
        session-based instead of accidentally using prior days.

        We use Chicago time because MES trades on CME.
        """

        if not bars:
            return []

        current_day = self._chicago_date(bars[-1])

        return [
            b
            for b in bars
            if self._chicago_date(b) == current_day
        ]

    def _chicago_date(self, bar: Bar):
        return bar.timestamp.astimezone(self.exchange_tz).date()

    def _confidence(self, score: int) -> str:
        if score >= 5:
            return "high"

        if score >= 3:
            return "medium-high"

        return "medium"