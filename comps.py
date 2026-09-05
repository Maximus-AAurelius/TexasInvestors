"""Source-backed local sale imports; select recent comparable candidates honestly."""
import csv
import hashlib
import io
import json
import math
from datetime import date, datetime, timezone
from urllib.parse import urlparse

import intelligence_db
from markets import normalize_county
from normalize import normalize_address

POLICY = {"radius_miles": 1.0, "max_age_days": 180, "size_tolerance": 0.20, "limit": 3}


def _connect():
    connection = intelligence_db._connect()
    connection.execute("CREATE TABLE IF NOT EXISTS comp_sales (sale_id TEXT PRIMARY KEY, sale_json TEXT NOT NULL, updated_at TEXT NOT NULL)")
    return connection


def validate_sale(payload):
    if not isinstance(payload, dict):
        raise ValueError("Each sale must be an object")
    result = {}
    for key, limit in (("address", 250), ("county", 80), ("property_class", 30), ("source_url", 2000), ("source_reference", 500)):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"{key} is required (up to {limit} characters)")
        result[key] = value.strip()
    result["county"] = normalize_county(result["county"])
    result["property_class"] = result["property_class"].upper()
    parsed = urlparse(result["source_url"])
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Source URL must be an HTTP(S) reference without credentials")
    try:
        sold = date.fromisoformat(payload.get("sale_date", ""))
    except (TypeError, ValueError):
        raise ValueError("Sale date must be YYYY-MM-DD") from None
    if sold > date.today():
        raise ValueError("A closed sale cannot have a future sale date")
    result["sale_date"] = sold.isoformat()
    for key, low, high in (("sale_price", 1, 1_000_000_000), ("building_sqft", 1, 10_000_000),
                           ("latitude", -90, 90), ("longitude", -180, 180)):
        try:
            value = float(payload.get(key))
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be numeric") from None
        if isinstance(payload.get(key), bool) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"Invalid {key}")
        result[key] = value
    if payload.get("sale_status") != "closed":
        raise ValueError("Only closed sales are accepted, not asking/list prices")
    result["sale_status"] = "closed"
    reviewed = payload.get("reviewed", False)
    if not isinstance(reviewed, bool):
        raise ValueError("Reviewed must be true or false")
    result["reviewed"] = reviewed
    key = f"{result['county']}|{normalize_address(result['address'])}|{sold.isoformat()}"
    result["id"] = hashlib.sha256(key.encode()).hexdigest()
    result["recorded_at"] = datetime.now(timezone.utc).isoformat()
    return result


def save_sales(payloads):
    if not isinstance(payloads, list) or not 1 <= len(payloads) <= 1000:
        raise ValueError("Import 1 to 1,000 sales at a time")
    rows = [validate_sale(payload) for payload in payloads]
    connection = _connect()
    try:
        with connection:
            for row in rows:
                connection.execute("INSERT INTO comp_sales VALUES (?, ?, ?) ON CONFLICT(sale_id) DO UPDATE SET sale_json=excluded.sale_json,updated_at=excluded.updated_at",
                                   (row["id"], json.dumps(row), row["recorded_at"]))
    finally:
        connection.close()
    return len({row["id"] for row in rows})


def import_csv(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > 500_000:
        raise ValueError("CSV must be under 500 KB")
    rows = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
    for row in rows:
        reviewed = str(row.get("reviewed", "false")).strip().lower()
        if reviewed not in {"true", "false", "1", "0", ""}:
            raise ValueError("Reviewed CSV values must be true/false or 1/0")
        row["reviewed"] = reviewed in {"true", "1"}
    return save_sales(rows)


def get_sales():
    connection = _connect()
    try:
        return [json.loads(row[0]) for row in connection.execute("SELECT sale_json FROM comp_sales ORDER BY sale_id")]
    finally:
        connection.close()


def delete_sale(sale_id):
    if not isinstance(sale_id, str) or len(sale_id) != 64:
        raise ValueError("Invalid sale id")
    connection = _connect()
    try:
        with connection:
            connection.execute("DELETE FROM comp_sales WHERE sale_id=?", (sale_id,))
    finally:
        connection.close()


def distance_miles(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    angle = math.sin((b-a)/2)**2 + math.cos(a)*math.cos(b)*math.sin(math.radians(lon2-lon1)/2)**2
    return 3958.7613 * 2 * math.asin(math.sqrt(min(1, max(0, angle))))


def select_comps(lead, sales, location=None, today=None):
    today = today or date.today()
    location = location or {}
    facts = dict(lead.get("hcad", {}))
    raw = lead.get("raw", {})
    if not facts.get("property_type"):
        facts["property_type"] = str(raw.get("property_type") or raw.get("property_class") or "").strip().upper()
    if not facts.get("building_sqft"):
        try:
            size = float(raw.get("building_sqft", 0))
            facts["building_sqft"] = size if math.isfinite(size) and size > 0 else None
        except (ValueError, TypeError):
            facts["building_sqft"] = None
    result = {"sales": [], "policy": POLICY.copy(), "dataset_size": len(sales),
              "coverage": "Imported sales only; not a complete market feed", "gaps": []}
    if location.get("latitude") is None or location.get("longitude") is None:
        result["gaps"].append("Save the subject property's coordinates to measure distance")
    if not facts.get("building_sqft") or not facts.get("property_type"):
        result["gaps"].append("Subject building size and property class are needed for comparability")
    if result["gaps"]:
        return result
    subject_size = facts["building_sqft"]
    candidates = []
    for sale in sales:
        if sale["county"] != lead["county"] or sale["property_class"] != facts["property_type"]:
            continue
        if normalize_address(sale["address"]) == normalize_address(lead["address"]):
            continue
        age = (today-date.fromisoformat(sale["sale_date"])).days
        if not 0 <= age <= POLICY["max_age_days"]:
            continue
        if abs(sale["building_sqft"]-subject_size)/subject_size > POLICY["size_tolerance"]:
            continue
        distance = distance_miles(location["latitude"], location["longitude"], sale["latitude"], sale["longitude"])
        if distance > POLICY["radius_miles"]:
            continue
        candidates.append({**sale, "distance_miles": round(distance, 3), "price_per_sqft": round(sale["sale_price"]/sale["building_sqft"], 2)})
    candidates.sort(key=lambda row: (-date.fromisoformat(row["sale_date"]).toordinal(), row["distance_miles"], row["id"]))
    result["sales"] = candidates[:POLICY["limit"]]
    if len(result["sales"]) < 3:
        result["gaps"].append(f"Only {len(result['sales'])} qualifying sales in your imported records; no substitutes added")
    result["gaps"].append("Condition, concessions, lot and neighborhood differences require human review")
    return result
