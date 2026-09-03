"""Simple audit table so drift in source counts / matched-lead counts is
visible over time without manual re-checking (mandatory testing
requirement #4).
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict

DB_PATH = Path(__file__).parent / "audit_logs" / "audit.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    source_counts_json TEXT NOT NULL,
    matched_lead_count INTEGER NOT NULL
);
"""


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    return conn


def log_run(source_counts: Dict[str, int], matched_lead_count: int):
    import json
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO audit_runs (timestamp, source_counts_json, matched_lead_count) "
            "VALUES (?, ?, ?)",
            (datetime.now().isoformat(), json.dumps(source_counts), matched_lead_count),
        )
    conn.close()


def recent_runs(limit: int = 10):
    conn = _connect()
    rows = conn.execute(
        "SELECT run_id, timestamp, source_counts_json, matched_lead_count "
        "FROM audit_runs ORDER BY run_id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return rows
