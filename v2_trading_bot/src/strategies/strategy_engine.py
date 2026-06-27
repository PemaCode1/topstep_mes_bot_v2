from typing import Optional

from ..config import AppConfig
from ..models import Bar, Signal
from ..utils.session import parse_hhmm, to_session_time
from .confluence_engine import ConfluenceEngine


class StrategyEngine:
    """
    V2 strategy router.

    Old ORB/EMA/mean-reversion strategies stay in the folder as backup,
    but this engine now uses the new 5-strategy confluence system.
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.confluence = ConfluenceEngine(cfg)

    def on_bar(self, bar: Bar) -> None:
        self.confluence.on_bar(bar)

    def get_signal(self, bar: Bar) -> Optional[Signal]:
        current = to_session_time(bar.timestamp, self.cfg.session.timezone)

        if current < parse_hhmm(self.cfg.session.no_trade_before):
            return None

        if current > parse_hhmm(self.cfg.session.no_new_trades_after):
            return None

        return self.confluence.signal(bar)