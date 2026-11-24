import argparse
from datetime import date, timedelta

import pandas as pd

from . import backtest as bt
from . import paper, scan
from .config import data_path, load_config
from .data import bhavcopy
from .features import compute_features, to_wide


def _load_panel(cfg):
    p = data_path(cfg, "panel_path")
    if not p.exists():
        raise SystemExit("No price panel yet. Run: python -m investing_agent fetch")
    return pd.read_pickle(p)


def cmd_fetch(args, cfg):
    end = date.fromisoformat(args.end) if args.end else date.today()
    start = date.fromisoformat(args.start) if args.start else end - timedelta(days=int(365 * args.years))
    cache = data_path(cfg, "cache_dir")
    ok, failed = bhavcopy.fetch_range(start, end, cache)
    print(f"{ok} trading days downloaded/cached; {len(failed)} failed")
    panel = bhavcopy.build_panel(start, end, cache, tuple(cfg["universe"]["series"]))
    out = data_path(cfg, "panel_path")
    out.parent.mkdir(parents=True, exist_ok=True)
    panel.to_pickle(out)
    print(f"panel: {panel['date'].nunique()} days, {panel['symbol'].nunique()} symbols -> {out}")


def cmd_scan(args, cfg):
    panel = _load_panel(cfg)
    w = to_wide(panel)
    wl = scan.watchlist(w, compute_features(w, cfg), cfg, args.top)
    print(f"Watchlist as of {wl.attrs['as_of'].date()} (paper only, not advice)\n")
    print(wl.to_string(index=False))
    if args.csv:
        wl.to_csv(args.csv, index=False)


def cmd_backtest(args, cfg):
    panel = _load_panel(cfg)
    w = to_wide(panel)
    feats = compute_features(w, cfg)
    periods, trades = bt.run_backtest(w, feats, cfg, start=args.start, top_n=args.top)
    stats = bt.summarize(periods, trades, cfg["strategy"]["hold_days"])
    if not stats:
        raise SystemExit("Not enough history. Fetch at least ~2 years of data.")
    for k, v in stats.items():
        print(f"{k:28s} {v}")
    print("\nPer-period results:")
    print(periods.assign(ret=(periods.ret * 100).round(2), bench=(periods.bench * 100).round(2))
          .to_string(index=False))


def cmd_paper(args, cfg):
    con = paper.connect(data_path(cfg, "paper_db"))
    panel = _load_panel(cfg)
    if args.action == "open":
        w = to_wide(panel)
        wl = scan.watchlist(w, compute_features(w, cfg), cfg, 30)
        added = paper.open_positions(con, wl, cfg["risk"]["max_positions"])
        print("opened paper positions:", added or "none")
    elif args.action == "update":
        print("closed:", paper.update(con, panel, cfg["strategy"]["hold_days"]) or "none")
    last = panel[panel["date"] == panel["date"].max()].set_index("symbol")["close"]
    df = paper.status(con, last)
    print(df.to_string(index=False) if len(df) else "no paper trades yet")


def main():
    ap = argparse.ArgumentParser(prog="investing_agent")
    ap.add_argument("--config")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download NSE bhavcopy and build the price panel")
    f.add_argument("--start"); f.add_argument("--end"); f.add_argument("--years", type=float, default=3)
    s = sub.add_parser("scan", help="rank today's candidates")
    s.add_argument("--top", type=int, default=20); s.add_argument("--csv")
    b = sub.add_parser("backtest", help="walk-forward monthly backtest")
    b.add_argument("--start"); b.add_argument("--top", type=int)
    p = sub.add_parser("paper", help="paper-trading journal")
    p.add_argument("action", choices=["open", "update", "status"])
    args = ap.parse_args()
    cfg = load_config(args.config)
    {"fetch": cmd_fetch, "scan": cmd_scan, "backtest": cmd_backtest, "paper": cmd_paper}[args.cmd](args, cfg)


if __name__ == "__main__":
    main()
