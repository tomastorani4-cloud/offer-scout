"""SQLite store shared by the four agents and the future management dashboard.

Layers (medallion pattern): raw_records = bronze, records = silver, opportunities = gold.
`events` is a tiny transactional outbox: agents publish events, downstream agents poll them.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, agent TEXT, started_at TEXT, finished_at TEXT,
  data_mode TEXT, status TEXT, config_json TEXT);
CREATE TABLE IF NOT EXISTS raw_records(
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, source_platform TEXT, source_id TEXT,
  captured_at TEXT, query TEXT, country TEXT, simulated INTEGER, payload_json TEXT);
CREATE TABLE IF NOT EXISTS records(
  run_id TEXT, record_id TEXT, subcategory TEXT, signal_type TEXT, rejected INTEGER,
  reject_reasons TEXT, data_json TEXT, PRIMARY KEY(run_id, record_id));
CREATE TABLE IF NOT EXISTS opportunities(
  run_id TEXT, opportunity_id TEXT, category TEXT, subcategory TEXT, decision TEXT,
  score INTEGER, confidence TEXT, handoff INTEGER, data_json TEXT,
  PRIMARY KEY(run_id, opportunity_id));
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, producer TEXT, event_type TEXT,
  run_id TEXT, payload_json TEXT, consumed_by TEXT DEFAULT '');
CREATE VIEW IF NOT EXISTS v_latest_opportunities AS
  SELECT o.* FROM opportunities o
  WHERE o.run_id = (SELECT run_id FROM runs WHERE agent='scout' AND status='completed'
                    ORDER BY started_at DESC LIMIT 1);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def start_run(self, run_id: str, started_at: str, data_mode: str, config: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO runs VALUES(?,?,?,?,?,?,?)",
            (run_id, "scout", started_at, None, data_mode, "running", json.dumps(config, default=str)),
        )
        self.conn.commit()

    def finish_run(self, run_id: str, finished_at: str, status: str, data_mode: str) -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at=?, status=?, data_mode=? WHERE run_id=?",
            (finished_at, status, data_mode, run_id),
        )
        self.conn.commit()

    def add_raw(self, run_id: str, raws: Iterable[Any]) -> None:
        rows = [
            (run_id, r.source_platform, r.source_id, r.captured_at, r.query, r.country,
             int(r.simulated), json.dumps(r.payload, default=str))
            for r in raws
        ]
        self.conn.executemany(
            "INSERT INTO raw_records(run_id,source_platform,source_id,captured_at,query,country,simulated,payload_json)"
            " VALUES(?,?,?,?,?,?,?,?)", rows)
        self.conn.commit()

    def add_records(self, run_id: str, records: Iterable[Any]) -> None:
        rows = [
            (run_id, r.record_id, r.subcategory, r.signal_type, int(r.rejected),
             json.dumps(r.reject_reasons), json.dumps(r.to_dict(), default=str))
            for r in records
        ]
        self.conn.executemany("INSERT OR REPLACE INTO records VALUES(?,?,?,?,?,?,?)", rows)
        self.conn.commit()

    def add_opportunities(self, run_id: str, opps: Iterable[dict[str, Any]]) -> None:
        rows = [
            (run_id, o["opportunity_id"], o["category"], o["subcategory"], o["decision"],
             o["score"]["total"], o["evidence_confidence"], int(o["handoff_to_modeler"]),
             json.dumps(o, default=str))
            for o in opps
        ]
        self.conn.executemany("INSERT OR REPLACE INTO opportunities VALUES(?,?,?,?,?,?,?,?,?)", rows)
        self.conn.commit()

    def emit_event(self, created_at: str, producer: str, event_type: str, run_id: str, payload: dict[str, Any]) -> int:
        cur = self.conn.execute(
            "INSERT INTO events(created_at,producer,event_type,run_id,payload_json) VALUES(?,?,?,?,?)",
            (created_at, producer, event_type, run_id, json.dumps(payload, default=str)))
        self.conn.commit()
        return int(cur.lastrowid)

    def pending_events(self, consumer: str, event_type: str | None = None) -> list[dict[str, Any]]:
        q = "SELECT * FROM events WHERE (',' || consumed_by || ',') NOT LIKE ?"
        args: list[Any] = [f"%,{consumer},%"]
        if event_type:
            q += " AND event_type=?"
            args.append(event_type)
        with closing(self.conn.execute(q + " ORDER BY id", args)) as cur:
            return [dict(r) | {"payload": json.loads(r["payload_json"])} for r in cur.fetchall()]

    def mark_consumed(self, event_id: int, consumer: str) -> None:
        self.conn.execute(
            "UPDATE events SET consumed_by = CASE WHEN consumed_by='' THEN ? ELSE consumed_by||','||? END WHERE id=?",
            (consumer, consumer, event_id))
        self.conn.commit()

    def opportunities(self, run_id: str) -> list[dict[str, Any]]:
        with closing(self.conn.execute(
                "SELECT data_json FROM opportunities WHERE run_id=? ORDER BY score DESC", (run_id,))) as cur:
            return [json.loads(r["data_json"]) for r in cur.fetchall()]
