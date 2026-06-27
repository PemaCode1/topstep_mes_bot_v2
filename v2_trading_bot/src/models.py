from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class OrderStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class ExitReason(str, Enum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    EMERGENCY_FLATTEN = "EMERGENCY_FLATTEN"
    SESSION_FLATTEN = "SESSION_FLATTEN"
    MANUAL = "MANUAL"


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Signal:
    side: Side
    strategy_name: str
    entry_reference_price: float
    confidence: str
    reason: str


@dataclass
class BracketOrder:
    order_id: str
    side: Side
    qty: int
    entry_price: float
    stop_price: float
    target_price: float
    strategy_name: str
    opened_at: datetime

    # Research metadata.
    # These fields help us study why trades win or lose.
    signal_reason: str = ""
    signal_score: int = 0
    setup_components: str = ""

    # Trade lifecycle.
    status: OrderStatus = OrderStatus.OPEN
    closed_at: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[ExitReason] = None
    pnl: float = 0.0
    bars_held: int = 0


@dataclass(frozen=True)
class TradeDecision:
    allowed: bool
    reason: str