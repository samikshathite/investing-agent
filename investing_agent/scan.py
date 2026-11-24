"""Latest-day watchlist: ranked candidates with entry, stop and position size."""
import math

import pandas as pd


def watchlist(w: dict, feats: dict, cfg: dict, top: int = 20) -> pd.DataFrame:
    score = feats["score"]
    last = score.index[-1]
    s = score.iloc[-1].dropna().sort_values(ascending=False).head(top)
    risk, capital = cfg["risk"], cfg["capital"]
    rows = []
    for sym, sc in s.items():
        px = float(w["close"][sym].iloc[-1])          # raw (unadjusted) price, what you would pay
        atr_adj = float(feats["atr"][sym].iloc[-1])
        atr_raw = atr_adj * px / float(w["adj_close"][sym].iloc[-1])
        stop = px - cfg["strategy"]["stop_atr_mult"] * atr_raw
        per_share_risk = px - stop
        qty = math.floor(min(
            capital * risk["risk_per_trade_pct"] / 100 / per_share_risk,
            capital / risk["max_positions"] / px,
        ))
        rows.append({
            "symbol": sym, "score": round(sc, 3), "close": round(px, 2), "stop": round(stop, 2),
            "risk_pct": round(per_share_risk / px * 100, 1), "qty": qty,
            "rsi": round(float(feats["rsi"][sym].iloc[-1]), 1),
            "ret_3m_pct": round(float(feats["ret63"][sym].iloc[-1]) * 100, 1),
            "pct_of_52w_high": round(float(feats["near_high"][sym].iloc[-1]) * 100, 1),
            "vol_surge_x": round(float(feats["vsurge"][sym].iloc[-1]), 2),
            "avg_turnover_cr": round(float(feats["liq"][sym].iloc[-1]) / 100, 1),
        })
    out = pd.DataFrame(rows)
    out.attrs["as_of"] = last
    return out
