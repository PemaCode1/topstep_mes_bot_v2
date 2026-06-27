from typing import Iterable, Optional, Tuple
import math
from .models import Bar


def ema(values: Iterable[float], period: int) -> Optional[float]:
    vals = list(values)
    if period <= 0 or len(vals) < period:
        return None
    k = 2 / (period + 1)
    current = sum(vals[:period]) / period
    for value in vals[period:]:
        current = value * k + current * (1 - k)
    return current


def vwap_and_std(bars: Iterable[Bar]) -> Tuple[Optional[float], Optional[float]]:
    bars = list(bars)
    if not bars:
        return None, None
    cum_pv = 0.0
    cum_vol = 0.0
    typical_prices = []
    for bar in bars:
        typical = (bar.high + bar.low + bar.close) / 3.0
        cum_pv += typical * bar.volume
        cum_vol += bar.volume
        typical_prices.append(typical)
    if cum_vol <= 0:
        return None, None
    vwap = cum_pv / cum_vol
    variance = sum((x - vwap) ** 2 for x in typical_prices) / len(typical_prices)
    return vwap, math.sqrt(variance)


def round_to_tick(price: float, tick_size: float) -> float:
    return round(round(price / tick_size) * tick_size, 2)
