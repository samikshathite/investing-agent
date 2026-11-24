"""Non-overlapping monthly walk-forward backtest.

At each rebalance close t: rank by score, take the top N. Enter at the OPEN of t+1 (plus
slippage). Stop = entry - stop_atr_mult * ATR(t). Exit at the stop (or the open, if the
stock gaps below it) or at the close of day t+hold_days. Costs and slippage are charged
on both sides. Results are compared with an equal-weight basket of every tradable stock
over the same windows, because beating the market basket is the real question.

Known limits: survivorship bias (the panel only holds stocks listed in the window and
delisted names vanish), no circuit-limit/liquidity-fill modelling, and EOD data only.
"""
import numpy as np
import pandas as pd


def slippage(liq_lakhs: float, cfg: dict) -> float:
    s = cfg["costs"]["slippage_pct_per_side"]
    pct = s["liquid"] if liq_lakhs >= 5000 else s["mid"] if liq_lakhs >= 1000 else s["thin"]
    return pct / 100


def simulate_trade(opens, highs, lows, closes, i, sym, atr_t, cfg, liq_t):
    """Trade signalled at row i. Returns net return, or None if it cannot be entered."""
    hold = cfg["strategy"]["hold_days"]
    if i + hold >= len(closes):
        return None
    entry_raw = opens[sym].iloc[i + 1]
    if not np.isfinite(entry_raw) or entry_raw <= 0:
        return None
    slip = slippage(liq_t, cfg)
    entry = entry_raw * (1 + slip)
    stop = entry_raw - cfg["strategy"]["stop_atr_mult"] * atr_t
    exit_px = None
    for j in range(i + 1, i + hold + 1):
        lo = lows[sym].iloc[j]
        if np.isfinite(lo) and lo <= stop:
            op = opens[sym].iloc[j]
            exit_px = min(op, stop) if (j > i + 1 and np.isfinite(op)) else stop
            break
    if exit_px is None:
        exit_px = closes[sym].iloc[i + hold]
        if not np.isfinite(exit_px):
            exit_px = closes[sym].iloc[i + 1: i + hold + 1].ffill().iloc[-1]
    exit_px *= 1 - slip
    return exit_px / entry - 1 - cfg["costs"]["round_trip_pct"] / 100


def run_backtest(w: dict, feats: dict, cfg: dict, start=None, top_n=None):
    hold = cfg["strategy"]["hold_days"]
    n = top_n or cfg["risk"]["max_positions"]
    score, dates = feats["score"], feats["score"].index
    opens, highs, lows, closes = w["adj_open"], w["adj_high"], w["adj_low"], w["adj_close"]
    first = 252  # warm-up for the 200d average and 52-week high
    if start is not None:
        first = max(first, int(dates.searchsorted(pd.Timestamp(start))))

    rows, trades = [], []
    for i in range(first, len(dates) - hold - 1, hold):
        s = score.iloc[i].dropna().sort_values(ascending=False).head(n)
        rets = []
        for sym in s.index:
            r = simulate_trade(opens, highs, lows, closes, i, sym, feats["atr"][sym].iloc[i], cfg,
                               feats["liq"][sym].iloc[i])
            if r is not None:
                rets.append(r)
                trades.append({"signal_date": dates[i], "symbol": sym, "score": s[sym], "return": r})
        # Benchmark: equal-weight all tradable stocks, same entry/exit, same slippage-free windows.
        univ = feats["tradable"].iloc[i]
        syms = univ[univ].index
        bench = (closes[syms].iloc[i + hold] / opens[syms].iloc[i + 1] - 1).dropna()
        rows.append({
            "signal_date": dates[i],
            "n_trades": len(rets),
            "ret": float(np.mean(rets)) if rets else 0.0,
            "bench": float(bench.clip(upper=2).mean()) if len(bench) else 0.0,
        })
    return pd.DataFrame(rows), pd.DataFrame(trades)


def summarize(periods: pd.DataFrame, trades: pd.DataFrame, hold_days: int) -> dict:
    if periods.empty:
        return {}
    eq = (1 + periods["ret"]).cumprod()
    beq = (1 + periods["bench"]).cumprod()
    years = len(periods) * hold_days / 252
    dd = (eq / eq.cummax() - 1).min()
    return {
        "periods": len(periods),
        "years": round(years, 2),
        "total_return_pct": round((eq.iloc[-1] - 1) * 100, 1),
        "cagr_pct": round((eq.iloc[-1] ** (1 / years) - 1) * 100, 1) if years > 0 else None,
        "avg_period_return_pct": round(periods["ret"].mean() * 100, 2),
        "median_period_return_pct": round(periods["ret"].median() * 100, 2),
        "pct_periods_ge_10": round((periods["ret"] >= 0.10).mean() * 100, 1),
        "pct_periods_negative": round((periods["ret"] < 0).mean() * 100, 1),
        "worst_period_pct": round(periods["ret"].min() * 100, 1),
        "max_drawdown_pct": round(dd * 100, 1),
        "trade_win_rate_pct": round((trades["return"] > 0).mean() * 100, 1) if len(trades) else None,
        "n_trades": len(trades),
        "bench_total_return_pct": round((beq.iloc[-1] - 1) * 100, 1),
        "bench_avg_period_pct": round(periods["bench"].mean() * 100, 2),
    }
