from dataclasses import dataclass
from enum import Enum


class BotMode(str, Enum):
    PAPER = "PAPER"
    BACKTEST = "BACKTEST"
    LIVE = "LIVE"  # Blocked until broker execution is fully tested.


@dataclass(frozen=True)
class InstrumentConfig:
    """
    MES = Micro E-mini S&P 500 futures.

    MES math:
    - Minimum tick size: 0.25 points
    - 1 tick = $1.25
    - 1 full point = $5.00
    - 1 contract only for now
    """

    symbol: str = "MES"
    tick_size: float = 0.25
    tick_value: float = 1.25
    point_value: float = 5.00


@dataclass(frozen=True)
class RiskConfig:
    """
    Prop-firm survival settings.

    Goal:
    - Keep losses small
    - Avoid revenge trading
    - Stop after bad conditions
    - Protect evaluation/funded accounts
    """

    # Position sizing
    max_contracts: int = 1
    max_open_positions: int = 1

    # Trade bracket
    # MES: 1 tick = $1.25
    # 10 ticks = $12.50 risk
    # 14 ticks = $17.50 target
    stop_loss_ticks: int = 10
    take_profit_ticks: int = 26

    # Emergency buffer if flattening slips
    emergency_slippage_ticks: int = 3

    # Daily safety controls
    max_daily_loss_dollars: float = 40.00
    max_trades_per_day: int = 5
    max_consecutive_losses: int = 2
    cooldown_after_loss_minutes: int = 0

    # Time safety
    flatten_minutes_before_close: int = 15

    # Backtest realism
    # Estimated round-trip cost per MES trade. Adjust later based on Topstep/platform fees.
    commission_per_round_trip: float = 2.50


@dataclass(frozen=True)
class SessionConfig:
    """
    CME equity index futures regular trading hours in Chicago time.

    We avoid:
    - first 15 minutes of chaos
    - lunch chop
    - late-day close risk
    """

    timezone: str = "America/Chicago"

    session_open: str = "08:30"
    session_close: str = "15:10"

    # Wait until after opening range forms.
    no_trade_before: str = "08:50"

    # Only trade the cleaner morning session.
    no_new_trades_after: str = "11:00"

    # Flatten before Topstep/exchange close rules become an issue.
    flatten_by: str = "14:55"


@dataclass(frozen=True)
class StrategyConfig:
    """
    V2 confluence + regime strategy settings.

    The bot does not blindly run every strategy all day.

    It first classifies the market:
    - TREND_UP
    - TREND_DOWN
    - RANGE
    - CHOP

    Then it routes to the correct strategy group:
    - Trend market: EMA/VWAP pullback, momentum continuation, opening-drive pullback
    - Range market: liquidity sweep, failed breakout, VWAP rejection
    - Chop market: no trade
    """

    # Master switch
    enable_confluence_engine: bool = True
    enable_regime_filter: bool = True

    # Old strategies disabled while testing confluence engine.
    enable_orb: bool = False
    enable_ema_pullback: bool = False
    enable_mean_reversion: bool = False

    # Core indicators
    ema_fast: int = 9
    ema_slow: int = 21

    # Regime detection
    regime_lookback_bars: int = 20
    trend_min_ema_spread_ticks: int = 6
    range_max_ema_spread_ticks: int = 4
    chop_max_total_range_ticks: int = 28

    # Swing/range structure
    swing_lookback_bars: int = 8
    compression_lookback_bars: int = 12

    # Signal scoring
    # 2 = testing mode, more trades
    # 3 = balanced mode
    # 4 = strict prop-firm mode
    min_score_to_trade: int = 2

    # Candle quality filters
    min_signal_candle_ticks: int = 2
    max_signal_candle_ticks: int = 32

    # Trend strategies
    enable_ema_vwap_pullback: bool = False
    enable_momentum_continuation: bool = True
    enable_opening_drive_pullback: bool = True

    ema_pullback_tolerance_ticks: int = 4
    momentum_lookback_bars: int = 2
    opening_drive_minutes: int = 20
    opening_drive_min_move_ticks: int = 16

    # Range/reversal strategies
    enable_liquidity_sweep: bool = True
    enable_failed_breakout: bool = True
    enable_vwap_rejection: bool = True

    vwap_rejection_tolerance_ticks: int = 5
    failed_breakout_lookback_bars: int = 10

    # Compression breakout
    enable_compression_breakout: bool = True
    compression_max_range_ticks: int = 32
    breakout_buffer_ticks: int = 1

    # Old ORB compatibility settings.
    # These stay here so older files do not break, but ORB is disabled above.
    orb_start: str = "08:30"
    orb_minutes: int = 15
    orb_trade_until: str = "10:00"
    orb_min_range_ticks: int = 12
    orb_max_range_ticks: int = 60
    orb_breakout_buffer_ticks: int = 2
    require_ema_filter_for_orb: bool = True

    # Old mean reversion compatibility.
    mean_reversion_vwap_std_mult: float = 2.0
    mean_reversion_min_bars: int = 40

@dataclass(frozen=True)
class ReportConfig:
    """
    Backtest report settings.
    """

    print_trade_details: bool = True
    print_rejected_signals: bool = False
    save_trade_log: bool = True
    save_event_log: bool = True


@dataclass(frozen=True)
class AppConfig:
    mode: BotMode = BotMode.BACKTEST

    instrument: InstrumentConfig = InstrumentConfig()
    risk: RiskConfig = RiskConfig()
    session: SessionConfig = SessionConfig()
    strategy: StrategyConfig = StrategyConfig()
    report: ReportConfig = ReportConfig()

    log_dir: str = "logs"
    trade_log_file: str = "logs/trades.csv"
    event_log_file: str = "logs/events.log"