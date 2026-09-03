"""Small local SQLite persistence layer for intelligence history."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "audit_logs" / "intelligence.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS properties (
    property_id TEXT PRIMARY KEY,
    address TEXT NOT NULL,
    county TEXT NOT NULL,
    owner_name TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_type TEXT NOT NULL,
    UNIQUE(property_id, source_file, source_type)
);
CREATE TABLE IF NOT EXISTS property_profiles (
    property_id TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL,
    calculated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS score_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    calculated_at TEXT NOT NULL,
    scores_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lead_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id TEXT NOT NULL,
    status TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS underwritings (
    property_id TEXT PRIMARY KEY,
    underwriting_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.executescript(SCHEMA)
    return connection


def save_profiles(leads):
    now = datetime.now().isoformat(timespec="seconds")
    connection = _connect()
    with connection:
        for lead in leads:
            profile = lead["intelligence"]
            connection.execute(
                "INSERT INTO properties VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(property_id) DO UPDATE SET address=excluded.address, "
                "county=excluded.county, owner_name=excluded.owner_name, updated_at=excluded.updated_at",
                (lead["id"], lead["address"], lead["county"], lead["owner_name"], now),
            )
            for source_file in lead.get("source_files", []):
                for source_type in lead.get("sources", []):
                    connection.execute(
                        "INSERT OR IGNORE INTO source_records(property_id, source_file, source_type) VALUES (?, ?, ?)",
                        (lead["id"], source_file, source_type),
                    )
            connection.execute(
                "INSERT OR REPLACE INTO property_profiles(property_id, profile_json, calculated_at) VALUES (?, ?, ?)",
                (lead["id"], json.dumps(profile), now),
            )
            scores_json = json.dumps(profile["scores"], sort_keys=True)
            previous = connection.execute(
                "SELECT model_version, scores_json FROM score_snapshots "
                "WHERE property_id = ? ORDER BY id DESC LIMIT 1",
                (lead["id"],),
            ).fetchone()
            if previous is None or previous != (profile["model_version"], scores_json):
                connection.execute(
                    "INSERT INTO score_snapshots(property_id, model_version, calculated_at, scores_json) VALUES (?, ?, ?, ?)",
                    (lead["id"], profile["model_version"], now, scores_json),
                )
    connection.close()


def record_action(property_id, status):
    connection = _connect()
    with connection:
        connection.execute(
            "INSERT INTO lead_actions(property_id, status, recorded_at) VALUES (?, ?, ?)",
            (property_id, status, datetime.now().isoformat(timespec="seconds")),
        )
    connection.close()


def save_underwriting(property_id, underwriting):
    connection = _connect()
    with connection:
        connection.execute(
            "INSERT OR REPLACE INTO underwritings(property_id, underwriting_json, updated_at) VALUES (?, ?, ?)",
            (property_id, json.dumps(underwriting), datetime.now().isoformat(timespec="seconds")),
        )
    connection.close()


def get_underwritings():
    connection = _connect()
    rows = connection.execute("SELECT property_id, underwriting_json FROM underwritings").fetchall()
    connection.close()
    return {property_id: json.loads(payload) for property_id, payload in rows}


def history_counts():
    connection = _connect()
    counts = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("properties", "source_records", "property_profiles", "score_snapshots", "lead_actions", "underwritings")
    }
    connection.close()
    return counts