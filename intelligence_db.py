"""Small local SQLite persistence layer for intelligence history."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from normalize import normalize_address

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
CREATE TABLE IF NOT EXISTS buyers (
    buyer_id TEXT PRIMARY KEY,
    buyer_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS property_lookups (
    lookup_id TEXT PRIMARY KEY,
    address TEXT NOT NULL,
    county TEXT NOT NULL,
    hcad_json TEXT,
    rentcast_json TEXT,
    updated_at TEXT NOT NULL
);
"""


def _lookup_id(address, county):
    return f"{county.strip().casefold()}|{normalize_address(address)}"


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
            evidence = lead.get("source_evidence")
            if evidence is None:
                evidence = [{"source_file": file, "source_type": "unspecified"} for file in lead.get("source_files", [])]
            for record in evidence:
                connection.execute(
                    "INSERT OR IGNORE INTO source_records(property_id, source_file, source_type) VALUES (?, ?, ?)",
                    (lead["id"], record["source_file"], record["source_type"]),
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


def save_buyer(buyer):
    connection = _connect()
    try:
        with connection:
            connection.execute("INSERT OR REPLACE INTO buyers VALUES (?, ?, ?)",
                               (buyer["id"], json.dumps(buyer), datetime.now().isoformat(timespec="seconds")))
    finally:
        connection.close()


def get_buyers():
    connection = _connect()
    try:
        return [json.loads(row[0]) for row in connection.execute("SELECT buyer_json FROM buyers ORDER BY updated_at DESC, buyer_id")]
    finally:
        connection.close()


def delete_buyer(buyer_id):
    connection = _connect()
    try:
        with connection:
            connection.execute("DELETE FROM buyers WHERE buyer_id = ?", (buyer_id,))
    finally:
        connection.close()


def save_property_lookup(address, county, hcad_data=None, rentcast_data=None):
    """Insert or update the one row for this address+county with whatever
    HCAD and/or RentCast data was just fetched. Called every time a lookup
    runs (see lookup.py) so the database fills in incrementally, one
    property at a time, instead of needing a bulk import.

    Passing hcad_data=None or rentcast_data=None leaves that column as it
    was (a RentCast-only re-run doesn't erase a previously saved HCAD
    profile, and vice versa).
    """
    if not isinstance(address, str) or not address.strip():
        raise ValueError("address is required")
    if not isinstance(county, str) or not county.strip():
        raise ValueError("county is required")
    lookup_id = _lookup_id(address, county)
    now = datetime.now().isoformat(timespec="seconds")
    connection = _connect()
    try:
        with connection:
            existing = connection.execute(
                "SELECT hcad_json, rentcast_json FROM property_lookups WHERE lookup_id = ?", (lookup_id,)
            ).fetchone()
            hcad_json = json.dumps(hcad_data) if hcad_data is not None else (existing[0] if existing else None)
            rentcast_json = json.dumps(rentcast_data) if rentcast_data is not None else (existing[1] if existing else None)
            connection.execute(
                "INSERT INTO property_lookups(lookup_id, address, county, hcad_json, rentcast_json, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(lookup_id) DO UPDATE SET "
                "address=excluded.address, county=excluded.county, hcad_json=excluded.hcad_json, "
                "rentcast_json=excluded.rentcast_json, updated_at=excluded.updated_at",
                (lookup_id, address.strip(), county.strip(), hcad_json, rentcast_json, now),
            )
    finally:
        connection.close()
    return lookup_id


def get_property_lookup(address, county):
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT address, county, hcad_json, rentcast_json, updated_at FROM property_lookups WHERE lookup_id = ?",
            (_lookup_id(address, county),),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    address_, county_, hcad_json, rentcast_json, updated_at = row
    return {
        "address": address_,
        "county": county_,
        "hcad": json.loads(hcad_json) if hcad_json else None,
        "rentcast": json.loads(rentcast_json) if rentcast_json else None,
        "updated_at": updated_at,
    }


def list_property_lookups():
    connection = _connect()
    try:
        rows = connection.execute(
            "SELECT address, county, hcad_json, rentcast_json, updated_at FROM property_lookups ORDER BY updated_at DESC"
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "address": address_,
            "county": county_,
            "hcad": json.loads(hcad_json) if hcad_json else None,
            "rentcast": json.loads(rentcast_json) if rentcast_json else None,
            "updated_at": updated_at,
        }
        for address_, county_, hcad_json, rentcast_json, updated_at in rows
    ]
