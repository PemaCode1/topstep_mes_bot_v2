from collections import deque
from typing import Optional
from ..config import AppConfig
from ..indicators import vwap_and_std
from ..models import Bar, Signal, Side


class MeanReversionStrategy:
    """Optional strategy. Disabled by default.

    Mean reversion can work in chop, but it is dangerous in trend days.
    Keep it off until ORB/EMA are tested and journaled.
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.bars: deque[Bar] = deque(maxlen=300)

    def on_bar(self, bar: Bar) -> None:
        self.bars.append(bar)

    def signal(self, bar: Bar) -> Optional[Signal]:
        if not self.cfg.strategy.enable_mean_reversion:
            return None
        if len(self.bars) < self.cfg.strategy.mean_reversion_min_bars:
            return None

        vwap, std = vwap_and_std(self.bars)
        if vwap is None or std is None or std == 0:
            return None

        upper = vwap + std * self.cfg.strategy.mean_reversion_vwap_std_mult
        lower = vwap - std * self.cfg.strategy.mean_reversion_vwap_std_mult

        if bar.close >= upper:
            return Signal(
                side=Side.SHORT,
                strategy_name="VWAP_MEAN_REVERSION_SHORT",
                entry_reference_price=bar.close,
                confidence="experimental",
                reason=f"Close above VWAP upper band. VWAP={vwap:.2f}, upper={upper:.2f}."
            )
        if bar.close <= lower:
            return Signal(
                side=Side.LONG,
                strategy_name="VWAP_MEAN_REVERSION_LONG",
                entry_reference_price=bar.close,
                confidence="experimental",
                reason=f"Close below VWAP lower band. VWAP={vwap:.2f}, lower={lower:.2f}."
            )
        return None
