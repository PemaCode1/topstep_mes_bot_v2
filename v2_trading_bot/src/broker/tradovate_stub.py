class TradovateLiveAdapterNotEnabled(Exception):
    pass


class TradovateAdapter:
    """Placeholder for real broker connectivity.

    I am intentionally not wiring live execution in V1. The safe workflow is:
    1. Run demo simulation.
    2. Backtest on historical MES data.
    3. Paper trade with broker sandbox.
    4. Add live adapter after the exact account/API rules are verified.

    This prevents an unfinished prototype from firing orders into a real prop account.
    """

    def __init__(self, *args, **kwargs):
        raise TradovateLiveAdapterNotEnabled(
            "Live Tradovate adapter is disabled in V1. Use PaperBroker/backtest first."
        )
