# Investing agent

A paper-trading stock screener and backtester for the NSE cash market. It ranks stocks
with a technical score, backtests the rules on NSE's own daily bhavcopy, and keeps a
paper-trade journal. **It never places real orders and is not investment advice.**

## What it does

| Command | Purpose |
|---|---|
| `python -m investing_agent fetch --years 5` | Download NSE daily bhavcopy (cached in `data/raw`) and build `data/panel.pkl` |
| `python -m investing_agent scan --top 20` | Ranked watchlist with stop and position size |
| `python -m investing_agent backtest` | Monthly walk-forward backtest vs an equal-weight market basket |
| `python -m investing_agent paper open` / `update` / `status` | Paper-trade journal in SQLite |

Setup: `pip install -e ".[dev]"`, then `pytest`. All limits live in `config.yaml`.

## Method

- **Data:** `sec_bhavdata_full_*.csv` from `nsearchives.nseindia.com` (all series, with
  turnover and delivery %). `PREV_CLOSE` is NSE-adjusted for splits/bonuses, so returns
  are chained from `close/prev_close` instead of raw prices. Holiday files that duplicate
  the previous session are dropped.
- **Universe:** series `EQ` by default; minimum price and 20-day turnover filters keep
  out illiquid names. Add `SM`/`ST` in `config.yaml` to include SME-board stocks.
- **Score:** relative strength (3-month return rank), trend (price > 50DMA > 200DMA),
  proximity to the 52-week high, volume surge, and an RSI band. Weights are in config.
- **Backtest:** signal at close `t`, entry at next open, ATR stop, exit after
  `hold_days`, with costs and liquidity-based slippage. Features use only data up to `t`
  (covered by a test).

## Known limits

- **No fundamentals yet.** NSE's website blocks cloud IPs and Kite has no fundamentals
  endpoint. The planned route is a local fetcher for NSE quarterly results.
- **Survivorship bias:** delisted stocks drop out of the panel, which flatters results.
- EOD data only; no circuit-limit or partial-fill modelling; sizing uses last close as
  a stand-in for tomorrow's open.
- A 10-20% monthly return is a stretch target, not something this tool promises.
