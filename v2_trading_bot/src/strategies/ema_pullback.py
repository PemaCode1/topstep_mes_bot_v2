from collections import deque
from typing import Optional
from ..config import AppConfig
from ..indicators import ema
from ..models import Bar, Signal, Side


class EMAPullbackStrategy:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.bars: deque[Bar] = deque(maxlen=300)
        self.last_signal_bar_ts = None

    def on_bar(self, bar: Bar) -> None:
        self.bars.append(bar)

    def signal(self, bar: Bar) -> Optional[Signal]:
        if not self.cfg.strategy.enable_ema_pullback:
            return None
        if self.last_signal_bar_ts == bar.timestamp:
            return None
        minimum = self.cfg.strategy.ema_slow + self.cfg.strategy.ema_min_trend_bars + 2
        if len(self.bars) < minimum:
            return None

        closes = [b.close for b in self.bars]
        fast = ema(closes, self.cfg.strategy.ema_fast)
        slow = ema(closes, self.cfg.strategy.ema_slow)
        if fast is None or slow is None:
            return None

        tolerance = self.cfg.strategy.ema_pullback_tolerance_ticks * self.cfg.instrument.tick_size
        recent = list(self.bars)[-self.cfg.strategy.ema_min_trend_bars:]

        uptrend = fast > slow and all(b.close >= slow for b in recent)
        downtrend = fast < slow and all(b.close <= slow for b in recent)
        touched_fast = bar.low <= fast + tolerance and bar.high >= fast - tolerance
        bullish_close = bar.close > bar.open
        bearish_close = bar.close < bar.open

        if uptrend and touched_fast and bullish_close and bar.close > fast:
            self.last_signal_bar_ts = bar.timestamp
            return Signal(
                side=Side.LONG,
                strategy_name="EMA_PULLBACK_LONG",
                entry_reference_price=bar.close,
                confidence="low-medium",
                reason="Trend up, pullback touched fast EMA, candle reclaimed EMA."
            )
        if downtrend and touched_fast and bearish_close and bar.close < fast:
            self.last_signal_bar_ts = bar.timestamp
            return Signal(
                side=Side.SHORT,
                strategy_name="EMA_PULLBACK_SHORT",
                entry_reference_price=bar.close,
                confidence="low-medium",
                reason="Trend down, pullback touched fast EMA, candle rejected EMA."
            )
        return None
