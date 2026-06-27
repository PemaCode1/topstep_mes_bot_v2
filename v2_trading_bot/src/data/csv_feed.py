from datetime import datetime
from pathlib import Path
import pandas as pd
from ..models import Bar


def load_bars_from_csv(path: str) -> list[Bar]:
    """Load OHLCV bars from a CSV.

    Required columns: timestamp, open, high, low, close, volume
    Timestamp should be parseable by pandas. Timezone-aware timestamps are preferred.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(p)
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    bars: list[Bar] = []
    for _, row in df.iterrows():
        ts = pd.to_datetime(row["timestamp"]).to_pydatetime()
        bars.append(Bar(
            timestamp=ts,
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        ))
    return bars
