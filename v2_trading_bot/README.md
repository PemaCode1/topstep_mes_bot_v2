## Strategy Design

The system is structured as a modular strategy research framework for MES futures.

The current version focuses on rule-based intraday strategy testing with conservative risk controls and realistic execution assumptions.

Current strategy components include:

* Opening range breakout logic
* Score-based trade filtering
* EMA/VWAP pullback research module
* Mean reversion research module
* Session-aware trade filtering
* Fixed bracket-style exits using predefined stop-loss and take-profit levels

The current active checkpoint emphasizes opening range logic and score-based filtering. EMA/VWAP pullback logic exists as a research module but is disabled in the current tested configuration.

Current active configuration:

```python
stop_loss_ticks = 10
take_profit_ticks = 26
cooldown_after_loss_minutes = 0
min_score_to_trade = 2
enable_ema_vwap_pullback = False
```

The strategy is evaluated through historical backtesting, trade logs, and performance metrics rather than live execution. The system is intentionally designed to prioritize risk control, reproducibility, and honest performance review over aggressive optimization.
