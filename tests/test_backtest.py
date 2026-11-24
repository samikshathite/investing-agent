import numpy as np
import pandas as pd

from investing_agent.backtest import simulate_trade, summarize
from investing_agent.config import load_config

CFG = load_config()
CFG["strategy"]["hold_days"] = 5
CFG["costs"]["round_trip_pct"] = 0.0
CFG["costs"]["slippage_pct_per_side"] = {"liquid": 0.0, "mid": 0.0, "thin": 0.0}


def frames(opens, highs, lows, closes):
    f = lambda v: pd.DataFrame({"X": v})
    return f(opens), f(highs), f(lows), f(closes)


def test_stop_hit_exits_at_stop():
    # signal on row 0, entry open row 1 = 100, ATR 5 -> stop 90 (mult 2). Row 2 trades through 90.
    o, h, l, c = frames([100] * 8, [101] * 8, [99, 99, 89, 99, 99, 99, 99, 99], [100] * 8)
    r = simulate_trade(o, h, l, c, 0, "X", 5.0, CFG, 9999)
    assert abs(r - (-0.10)) < 1e-9


def test_gap_below_stop_exits_at_open():
    o, h, l, c = frames([100, 100, 80, 80, 80, 80, 80, 80], [101] * 8, [99, 99, 79, 79, 79, 79, 79, 79], [100] * 8)
    r = simulate_trade(o, h, l, c, 0, "X", 5.0, CFG, 9999)
    assert abs(r - (-0.20)) < 1e-9  # filled at the 80 open, not the 90 stop


def test_time_exit_uses_close_of_hold_day():
    o, h, l, c = frames([100] * 8, [120] * 8, [95] * 8, [100, 100, 100, 100, 100, 112, 100, 100])
    r = simulate_trade(o, h, l, c, 0, "X", 5.0, CFG, 9999)
    assert abs(r - 0.12) < 1e-9


def test_entry_uses_next_open_not_signal_close():
    o, h, l, c = frames([100, 110, 110, 110, 110, 110, 110, 110], [111] * 8, [105] * 8, [100, 110, 110, 110, 110, 121, 110, 110])
    r = simulate_trade(o, h, l, c, 0, "X", 5.0, CFG, 9999)
    assert abs(r - 0.10) < 1e-9  # 110 -> 121


def test_costs_reduce_return():
    cfg = {**CFG, "costs": {"round_trip_pct": 0.5, "slippage_pct_per_side": {"liquid": 0.1, "mid": 0.1, "thin": 0.1}}}
    o, h, l, c = frames([100] * 8, [120] * 8, [95] * 8, [100, 100, 100, 100, 100, 110, 100, 100])
    r = simulate_trade(o, h, l, c, 0, "X", 5.0, cfg, 9999)
    assert r < 0.10 - 0.005


def test_summarize_drawdown_and_hit_rate():
    periods = pd.DataFrame({"ret": [0.10, -0.20, 0.15], "bench": [0.01] * 3})
    trades = pd.DataFrame({"return": [0.1, -0.2, 0.15]})
    s = summarize(periods, trades, 21)
    assert s["max_drawdown_pct"] == -20.0
    assert round(s["pct_periods_ge_10"], 1) == 66.7
