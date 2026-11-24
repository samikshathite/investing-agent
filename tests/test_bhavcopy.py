import numpy as np
import pandas as pd

from investing_agent.data.bhavcopy import drop_stale_days


def test_stale_holiday_copy_is_dropped():
    syms = [f"S{i}" for i in range(80)]
    rng = np.random.default_rng(1)
    d1 = pd.DataFrame({"date": pd.Timestamp("2024-03-28"), "symbol": syms, "close": rng.uniform(10, 100, 80)})
    holiday = d1.assign(date=pd.Timestamp("2024-03-29"))             # exact copy of the prior day
    d3 = d1.assign(date=pd.Timestamp("2024-04-01"), close=d1.close * 1.01)
    out = drop_stale_days(pd.concat([d1, holiday, d3]))
    assert sorted(out["date"].unique()) == [pd.Timestamp("2024-03-28"), pd.Timestamp("2024-04-01")]
