from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import random
from ..models import Bar


def generate_demo_mes_bars(days: int = 5, seed: int = 7) -> list[Bar]:
    """Generate fake intraday MES-like bars for testing the bot mechanics.

    This is NOT real market data. Use it only to verify that code runs.
    """
    random.seed(seed)
    tz = ZoneInfo("America/Chicago")
    bars: list[Bar] = []
    base_price = 6000.0
    start_date = datetime.now(tz).date() - timedelta(days=days)

    for day_offset in range(days):
        day = start_date + timedelta(days=day_offset + 1)
        current = datetime(day.year, day.month, day.day, 8, 30, tzinfo=tz)
        price = base_price + random.uniform(-30, 30)
        trend = random.choice([-0.03, 0.03, 0.05, -0.05, 0.0])
        for i in range(390):
            # More volatile at open, calmer later.
            vol_scale = 2.0 if i < 45 else 0.85
            drift = trend + random.gauss(0, 0.40) * vol_scale
            open_ = price
            close = round_to_tick(open_ + drift)
            high = max(open_, close) + abs(random.gauss(0, 0.60)) * vol_scale
            low = min(open_, close) - abs(random.gauss(0, 0.60)) * vol_scale
            high = round_to_tick(high)
            low = round_to_tick(low)
            volume = max(1, int(random.gauss(1200 if i < 60 else 650, 160)))
            bars.append(Bar(current, round_to_tick(open_), high, low, close, volume))
            price = close
            current += timedelta(minutes=1)
    return bars


def round_to_tick(value: float, tick: float = 0.25) -> float:
    return round(round(value / tick) * tick, 2)
