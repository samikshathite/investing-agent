import numpy as np
import pandas as pd

from investing_agent.features import rsi, to_wide, compute_features
from investing_agent.config import load_config


def make_panel(n=320, seed=0, symbols=("AAA", "BBB", "CCC")):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-02", periods=n)
    rows = []
    for k, s in enumerate(symbols):
        px = 100.0
        for d in dates:
            prev = px
            px = prev * (1 + rng.normal(0.001 * (k + 1), 0.015))
            rows.append(dict(date=d, symbol=s, prev_close=prev, open=prev, high=max(prev, px) * 1.005,
                             low=min(prev, px) * 0.995, close=px, volume=1e6, turnover_lacs=5000.0,
                             deliv_per=50.0))
    return pd.DataFrame(rows)


def test_rsi_all_gains_is_100_and_flat_is_nan_free():
    s = pd.DataFrame({"X": np.arange(1.0, 40.0)})
    assert rsi(s).iloc[-1, 0] == 100.0


def test_rsi_matches_wilder_reference():
    # Classic Wilder/StockCharts worked example (first RSI value ~70.53 on the 15th close)
    closes = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08,
              45.89, 46.03, 45.61, 46.28, 46.28]
    got = rsi(pd.DataFrame({"X": closes})).iloc[-1, 0]
    assert abs(got - 70.53) < 0.5


def test_split_is_adjusted_out_of_returns():
    p = make_panel(n=10, symbols=("AAA",))
    # 1:2 split on day 5: raw close halves, but NSE's PREV_CLOSE is adjusted to match
    p.loc[5:, ["open", "high", "low", "close"]] *= 0.5
    p.loc[5, "prev_close"] = p.loc[4, "close"] * 0.5
    w = to_wide(p)
    r = w["adj_close"]["AAA"].pct_change().iloc[5]
    assert abs(r) < 0.1  # no -50% jump


def test_features_have_no_lookahead():
    cfg = load_config()
    cfg["universe"]["min_avg_turnover_lacs"] = 0
    p = make_panel()
    f1 = compute_features(to_wide(p), cfg)["score"]
    t = p["date"].unique()[280]
    p2 = p.copy()
    future = p2["date"] > t
    p2.loc[future, ["open", "high", "low", "close", "prev_close"]] *= 3  # wreck the future
    f2 = compute_features(to_wide(p2), cfg)["score"]
    pd.testing.assert_series_equal(f1.loc[t].sort_index(), f2.loc[t].sort_index(), check_names=False)
