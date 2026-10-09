"""Writes the static data files the online dashboard reads.

site/data/latest.json  full scout-2.0 report of the latest successful run
site/data/history.json one small summary per run (last 52), for trends
site/data/status.json  what happened on the last attempt (ok / no_sources / error), never stale-silent
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HISTORY_LIMIT = 52


def _write(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_status(data_dir: str | Path, state: str, message: str, now_iso: str, extra: dict[str, Any] | None = None) -> None:
    d = Path(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    _write(d / "status.json", {"state": state, "message": message, "attempted_at_utc": now_iso, **(extra or {})})


def export_run(report: dict[str, Any], data_dir: str | Path) -> None:
    d = Path(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    run = report["run"]
    _write(d / "latest.json", report)
    history = _read(d / "history.json", [])
    history = [h for h in history if h.get("run_id") != run["run_id"]]
    history.append({
        "run_id": run["run_id"],
        "generated_at_utc": run["generated_at_utc"],
        "data_mode": run["data_mode"],
        "sources_used": run["sources_used"],
        "opportunities": {o["subcategory"]: {"score": o["score"]["total"], "decision": o["decision"],
                                              "confidence": o["evidence_confidence"]} for o in report["opportunities"]},
    })
    _write(d / "history.json", history[-HISTORY_LIMIT:])
    write_status(d, "ok", f"Run {run['run_id']} completed ({run['data_mode']}).", run["generated_at_utc"],
                 {"data_mode": run["data_mode"], "source_failures": run["source_failures"]})
