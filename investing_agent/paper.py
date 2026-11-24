"""Paper-trading journal (SQLite). No broker connection; nothing here places real orders.

`open_positions` records the latest watchlist at the last close (a stand-in for tomorrow's
open, so real fills will differ). `update` closes positions whose stop was touched or that
have been held `hold_days` sessions, using daily data from the price panel.
"""
import sqlite3

import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL, entry_date TEXT NOT NULL, entry_price REAL NOT NULL,
    qty INTEGER NOT NULL, stop REAL NOT NULL, status TEXT NOT NULL DEFAULT 'open',
    exit_date TEXT, exit_price REAL, exit_reason TEXT
)"""


def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute(SCHEMA)
    return con


def open_positions(con, wl: pd.DataFrame, max_positions: int):
    held = {r[0] for r in con.execute("SELECT symbol FROM positions WHERE status='open'")}
    slots = max_positions - len(held)
    added = []
    for _, r in wl.iterrows():
        if slots <= 0:
            break
        if r["symbol"] in held or r["qty"] < 1:
            continue
        con.execute(
            "INSERT INTO positions(symbol, entry_date, entry_price, qty, stop) VALUES (?,?,?,?,?)",
            (r["symbol"], str(wl.attrs["as_of"].date()), r["close"], int(r["qty"]), r["stop"]),
        )
        added.append(r["symbol"]); slots -= 1
    con.commit()
    return added


def update(con, panel: pd.DataFrame, hold_days: int):
    """Close stopped-out / expired positions using days after each entry. Returns closed rows."""
    closed = []
    dates = sorted(panel["date"].unique())
    for pid, sym, entry_date, entry, stop in con.execute(
        "SELECT id, symbol, entry_date, entry_price, stop FROM positions WHERE status='open'"
    ).fetchall():
        d = panel[(panel["symbol"] == sym) & (panel["date"] > pd.Timestamp(entry_date))].sort_values("date")
        reason = px = when = None
        for k, (_, row) in enumerate(d.iterrows(), 1):
            if row["low"] <= stop:
                px, when, reason = min(row["open"], stop), row["date"], "stop"
                break
            if k >= hold_days:
                px, when, reason = row["close"], row["date"], "time"
                break
        if reason:
            con.execute("UPDATE positions SET status='closed', exit_date=?, exit_price=?, exit_reason=? WHERE id=?",
                        (str(when.date()), float(px), reason, pid))
            closed.append((sym, reason, round((px / entry - 1) * 100, 2)))
    con.commit()
    return closed


def status(con, last_close: pd.Series) -> pd.DataFrame:
    df = pd.read_sql("SELECT * FROM positions ORDER BY id", con)
    if df.empty:
        return df
    price = df["symbol"].map(last_close)
    ref = df["exit_price"].fillna(price)
    df["last"] = price
    df["pnl_pct"] = ((ref / df["entry_price"] - 1) * 100).round(2)
    df["pnl_inr"] = ((ref - df["entry_price"]) * df["qty"]).round(0)
    return df
