# Topstep MES Bot V1 — Safe Build

This is a safer rebuild of the Claude prototype. It is **MES-first**, strict on risk, and runs in paper/backtest mode first.

## What this version does

- Trades **MES** logic, not ES.
- Uses correct MES risk math: **$1.25/tick**, **$5/point** per 1 contract.
- Uses one position at a time.
- Uses bracket-style entries in the paper broker:
  - stop loss
  - take profit
  - emergency flatten model
- Stops after strict daily limits:
  - max daily bot loss: `$100`
  - max trades per day: `3`
  - max consecutive losses: `2`
- Uses conservative backtest logic: if stop and target both hit in the same candle, the stop is assumed first.
- Logs every trade to `logs/trades.csv`.

## What this version does NOT do yet

It does **not** connect to live Tradovate/TopstepX yet. That is intentional.

Before live execution, you must verify:

1. Your exact Topstep account rules.
2. Whether automated trading is permitted for your account type.
3. Current broker/API requirements.
4. Current CME/order-tagging requirements.
5. Whether your platform supports server-side brackets the way you expect.

A bot that can immediately fire live orders without testing is not a flex. It is how people blow funded accounts.

## Install

```bash
cd topstep_mes_bot_v1
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Mac/Linux:

```bash
cd topstep_mes_bot_v1
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run demo simulation

```bash
python main.py
```

This uses fake generated MES-like bars only to verify the bot mechanics.

## Run with real historical CSV

Create a CSV with:

```text
timestamp,open,high,low,close,volume
```

Then run:

```bash
python main.py --csv path/to/your_mes_1min_data.csv
```

## Strategy design

### Strategy priority

1. ORB first
2. EMA pullback second
3. Mean reversion disabled by default

### Why mean reversion is disabled

Mean reversion can work during chop but can get destroyed on trend days. For a prop account, we do not start by fading strong moves. We start with trend-following and strict risk.

## Default risk settings

Open `src/config.py` to change settings.

```python
stop_loss_ticks = 16       # 4 points = about $20 on 1 MES
_take_profit_ticks = 24    # 6 points = about $30 on 1 MES
max_daily_loss_dollars = 100
max_trades_per_day = 3
max_consecutive_losses = 2
```

## Development roadmap

### V1

Paper/backtest engine + risk manager + strategy engine.

### V2

Add proper historical data source and metrics:

- profit factor
- max drawdown
- average win/loss
- expectancy
- day-by-day results

### V3

Add broker sandbox/paper adapter.

### V4

Only after paper testing: live adapter with locked execution mode, broker-side bracket validation, emergency kill switch, and logs.

## Safety rule

Never run a new auto-trading bot on a funded account first. Test on simulation and paper first.
