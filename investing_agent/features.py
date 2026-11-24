"""Technical features and the composite score, computed as date x symbol matrices.

Every value at row t uses data up to and including day t's close only. Trades are
entered on day t+1 (see backtest.py), so there is no look-ahead.
"""
import numpy as np
import pandas as pd


def to_wide(panel: pd.DataFrame) -> dict:
    """Pivot the long panel into date x symbol matrices with split/bonus-adjusted prices.

    NSE's PREV_CLOSE is adjusted on ex-dates, so close/prev_close-1 is a clean daily
    return. We chain those into an adjusted close and scale open/high/low by the same
    factor (adj_close / close) so intraday ranges stay consistent with it.
    """
    def piv(col):
        return panel.pivot(index="date", columns="symbol", values=col).sort_index()

    close, prev = piv("close"), piv("prev_close")
    ret = (close / prev - 1).where(close.notna() & (prev > 0))
    adj_close = (1 + ret.fillna(0)).cumprod().where(close.notna())
    factor = adj_close / close
    return {
        "close": close,
        "adj_close": adj_close,
        "adj_open": piv("open") * factor,
        "adj_high": piv("high") * factor,
        "adj_low": piv("low") * factor,
        "volume": piv("volume"),
        "turnover": piv("turnover_lacs"),
        "deliv_per": piv("deliv_per"),
    }


def wilder(x: pd.DataFrame, n: int) -> pd.DataFrame:
    """Wilder smoothing: seed with the simple mean of the first n valid values, then
    avg += (x - avg) / n. Handles stocks that start trading mid-panel (leading NaNs)."""
    a = x.to_numpy(dtype=float)
    out = np.full_like(a, np.nan)
    avg = np.full(a.shape[1], np.nan)
    acc, cnt = np.zeros(a.shape[1]), np.zeros(a.shape[1])
    for t in range(a.shape[0]):
        v = a[t]
        ok = np.isfinite(v)
        seeded = np.isfinite(avg)
        upd = seeded & ok
        avg[upd] += (v[upd] - avg[upd]) / n
        pre = ~seeded & ok
        acc[pre] += v[pre]
        cnt[pre] += 1
        done = pre & (cnt == n)
        avg[done] = acc[done] / n
        out[t] = avg
    return pd.DataFrame(out, index=x.index, columns=x.columns)


def rsi(adj_close: pd.DataFrame, n: int = 14) -> pd.DataFrame:
    delta = adj_close.diff()
    up, down = wilder(delta.clip(lower=0), n), wilder((-delta).clip(lower=0), n)
    rs = up / down
    out = 100 - 100 / (1 + rs)
    return out.where(down != 0, 100.0).where(up.notna() & down.notna())


def atr(w: dict, n: int = 14) -> pd.DataFrame:
    c_prev = w["adj_close"].shift(1)
    tr = pd.concat(
        [w["adj_high"] - w["adj_low"], (w["adj_high"] - c_prev).abs(), (w["adj_low"] - c_prev).abs()]
    ).groupby(level=0).max()  # element-wise max across the three components
    return wilder(tr.reindex_like(w["adj_close"]), n)


def compute_features(w: dict, cfg: dict) -> dict:
    u, weights = cfg["universe"], cfg["strategy"]["weights"]
    adj, close = w["adj_close"], w["close"]

    sma50, sma200 = adj.rolling(50).mean(), adj.rolling(200).mean()
    hi252 = w["adj_high"].rolling(252, min_periods=200).max()
    liq = w["turnover"].rolling(20, min_periods=15).mean()
    vsurge = w["turnover"].rolling(5).mean() / w["turnover"].rolling(50).mean()
    atr14 = atr(w)
    atr_pct = atr14 / adj
    rsi14 = rsi(adj)
    ret63 = adj / adj.shift(63) - 1

    tradable = (close >= u["min_price"]) & (liq >= u["min_avg_turnover_lacs"]) & adj.notna()
    # Rank momentum only among tradable names, so illiquid junk can't distort percentiles.
    rel_strength = ret63.where(tradable).rank(axis=1, pct=True)

    trend = ((adj > sma50) & (sma50 > sma200)).astype(float)
    near_high = (adj / hi252)
    parts = {
        "rel_strength": rel_strength,
        "trend": trend,
        "near_52w_high": ((near_high - 0.7) / 0.3).clip(0, 1),
        "volume_surge": (vsurge - 1).clip(0, 1),          # 1x avg -> 0, 2x or more -> 1
        "rsi_band": 1 - ((rsi14 - 60).abs() / 25).clip(0, 1),  # peaks at RSI 60
    }
    score = sum(weights[k] * parts[k] for k in weights)

    eligible = (
        tradable
        & (trend == 1)
        & sma200.notna() & hi252.notna() & rsi14.notna() & atr14.notna()
        & (rsi14 < 80)
        & (atr_pct <= u["max_atr_pct"])
    )
    return {
        "score": score.where(eligible),
        "atr": atr14,
        "liq": liq,
        "rsi": rsi14,
        "ret63": ret63,
        "near_high": near_high,
        "vsurge": vsurge,
        "tradable": tradable,
    }
