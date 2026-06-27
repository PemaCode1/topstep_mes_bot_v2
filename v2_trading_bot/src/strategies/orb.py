from collections import deque
from datetime import datetime
from typing import Optional
from ..config import AppConfig
from ..indicators import ema
from ..models import Bar, Signal, Side
from ..utils.session import parse_hhmm, to_session_time


class ORBStrategy:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.bars: deque[Bar] = deque(maxlen=300)
        self.orb_high: Optional[float] = None
        self.orb_low: Optional[float] = None
        self.orb_ready = False
        self.orb_day = None
        self.used_today = False

    def on_bar(self, bar: Bar) -> None:
        self.bars.append(bar)
        bar_day = bar.timestamp.date()
        if self.orb_day != bar_day:
            self.orb_day = bar_day
            self.orb_high = None
            self.orb_low = None
            self.orb_ready = False
            self.used_today = False

        current = to_session_time(bar.timestamp, self.cfg.session.timezone)
        start = parse_hhmm(self.cfg.strategy.orb_start)
        end_minutes = self.cfg.strategy.orb_minutes
        # Simple minute math because ORB is same-day intraday.
        end_total = start.hour * 60 + start.minute + end_minutes
        end = parse_hhmm(f"{end_total // 60:02d}:{end_total % 60:02d}")

        if start <= current <= end:
            self.orb_high = bar.high if self.orb_high is None else max(self.orb_high, bar.high)
            self.orb_low = bar.low if self.orb_low is None else min(self.orb_low, bar.low)
        elif current > end and self.orb_high is not None and self.orb_low is not None:
            self.orb_ready = True

    def signal(self, bar: Bar) -> Optional[Signal]:
        if not self.cfg.strategy.enable_orb or self.used_today or not self.orb_ready:
            return None

        current = to_session_time(bar.timestamp, self.cfg.session.timezone)
        if current > parse_hhmm(self.cfg.strategy.orb_trade_until):
            return None

        if self.orb_high is None or self.orb_low is None:
            return None

        tick = self.cfg.instrument.tick_size
        range_ticks = int(round((self.orb_high - self.orb_low) / tick))
        if range_ticks < self.cfg.strategy.orb_min_range_ticks:
            return None
        if range_ticks > self.cfg.strategy.orb_max_range_ticks:
            return None

        closes = [b.close for b in self.bars]
        fast = ema(closes, self.cfg.strategy.ema_fast)
        slow = ema(closes, self.cfg.strategy.ema_slow)
        if fast is None or slow is None:
            return None

        buffer = self.cfg.strategy.orb_breakout_buffer_ticks * tick
        long_break = bar.close >= self.orb_high + buffer
        short_break = bar.close <= self.orb_low - buffer

        if self.cfg.strategy.require_ema_filter_for_orb:
            long_break = long_break and fast > slow
            short_break = short_break and fast < slow

        if long_break:
            self.used_today = True
            return Signal(
                side=Side.LONG,
                strategy_name="ORB_LONG",
                entry_reference_price=bar.close,
                confidence="medium",
                reason=f"Close broke OR high {self.orb_high:.2f} with EMA trend filter."
            )
        if short_break:
            self.used_today = True
            return Signal(
                side=Side.SHORT,
                strategy_name="ORB_SHORT",
                entry_reference_price=bar.close,
                confidence="medium",
                reason=f"Close broke OR low {self.orb_low:.2f} with EMA trend filter."
            )
        return None
