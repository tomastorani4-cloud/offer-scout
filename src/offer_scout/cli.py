from __future__ import annotations

import argparse
import json
import sys

from .collectors import CollectorError
from .config import ConfigError, load_settings
from .pipeline import build_collectors, run_pipeline
from .store import Store


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="offer-scout", description="Agent 1: scan, score and hand off opportunities")
    ap.add_argument("--config", default="config", help="config directory")
    sub = ap.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="execute one scan")
    run.add_argument("--simulate", action="store_true", help="use SIMULATED data only (never for decisions)")
    run.add_argument("--out", default=None, help="output directory for the JSON report")
    run.add_argument("--auto", action="store_true", help="scheduled mode: use every source whose credentials/files exist")
    run.add_argument("--dashboard-dir", default=None, help="write dashboard data files (latest/history/status.json) here")

    ev = sub.add_parser("events", help="show pending events for a consumer (e.g. modeler, dashboard)")
    ev.add_argument("consumer")

    top = sub.add_parser("top", help="show latest run opportunities from the database")
    top.add_argument("--limit", type=int, default=10)

    args = ap.parse_args(argv)
    try:
        settings = load_settings(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2
    store = Store(settings.raw["storage"]["db_path"])

    if args.cmd == "run":
        from .dashboard_export import export_run, write_status
        from .normalize import now_iso
        dash = args.dashboard_dir
        try:
            collectors = build_collectors(settings, args.simulate, args.auto)
        except CollectorError as exc:
            if dash:
                write_status(dash, "error", f"Source setup failed: {exc}", now_iso())
            print(f"source setup error: {exc}", file=sys.stderr)
            return 2
        if not collectors:
            msg = ("No sources available: set ETSY_API_KEY / META_AD_LIBRARY_TOKEN secrets or add CSV exports to data/inbox/."
                   if args.auto else "No sources enabled. Enable one in config/settings.yaml or pass --simulate.")
            if dash:
                write_status(dash, "no_sources", msg, now_iso())
            print(msg, file=sys.stderr)
            return 0 if args.auto else 2   # scheduled run is not a failure; the dashboard shows the state
        try:
            report = run_pipeline(settings, collectors, store, args.out or settings.raw["storage"]["out_dir"])
        except Exception as exc:  # noqa: BLE001 - surface any failure on the dashboard, then fail the job
            if dash:
                write_status(dash, "error", f"Run failed: {exc}", now_iso())
            raise
        if dash:
            export_run(report, dash)
        r = report["run"]
        print(f"{r['run_id']} [{r['data_mode']}] analyzed={r['records_analyzed']} rejected={r['records_rejected']} finalists={r['finalists']}")
        for f in r["source_failures"]:
            print(f"  ! {f}")
        for o in report["opportunities"]:
            print(f"  {o['score']['total']:>3}  {o['decision']:<8} {o['evidence_confidence']:<6} {o['subcategory']}")
        return 0
    if args.cmd == "events":
        for e in store.pending_events(args.consumer):
            print(json.dumps({"id": e["id"], "type": e["event_type"], "run": e["run_id"]}))
        return 0
    if args.cmd == "top":
        rows = list(store.conn.execute("SELECT subcategory, decision, score, confidence FROM v_latest_opportunities ORDER BY score DESC LIMIT ?", (args.limit,)))
        for r in rows:
            print(f"{r['score']:>3}  {r['decision']:<8} {r['confidence']:<6} {r['subcategory']}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
