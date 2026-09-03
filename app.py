"""Read-only local web app for browsing the pipeline's CSV lead data."""
import csv
import json
import mimetypes
import os
import threading
import urllib.parse
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from intelligence import build_profile
from hcad_profile import enrich_leads

ROOT = Path(__file__).parent
WEB_DIR = ROOT / "web"
OUTPUT_DIR = ROOT / "output"
GEOCODE_CACHE = OUTPUT_DIR / "geocode_cache.json"
HOST = os.environ.get("TX_APP_HOST", "0.0.0.0")
PORT = int(os.environ.get("TX_APP_PORT", "8765"))
_cache_lock = threading.Lock()


def _read_cache():
    try:
        return json.loads(GEOCODE_CACHE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_leads():
    leads = {}
    for path in sorted(ROOT.glob("**/*.csv")):
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        try:
            with path.open(newline="", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    address = (row.get("address") or "").strip()
                    if not address:
                        continue
                    key = f"{row.get('county', '')}|{address.upper()}"
                    lead = leads.setdefault(key, {
                        "id": key,
                        "address": address,
                        "owner_name": (row.get("owner_name") or "Unknown").strip(),
                        "county": (row.get("county") or "Unknown").strip(),
                        "mailing_address": (row.get("mailing_address") or "Unknown").strip(),
                        "sources": set(),
                        "source_files": set(),
                        "raw": {},
                    })
                    source = (row.get("source_type") or path.stem).strip()
                    lead["sources"].add(source)
                    lead["source_files"].add(str(path.relative_to(ROOT)))
                    lead["raw"].update({k: v for k, v in row.items() if v})
        except (OSError, UnicodeError):
            continue
    result = []
    for lead in leads.values():
        mailing = lead["mailing_address"]
        out_of_state = bool(mailing and mailing != "Unknown" and " TX " not in f" {mailing.upper()} ")
        signals = ["Absentee owner"] if "absentee_owner" in lead["sources"] else []
        if out_of_state:
            signals.append("Out-of-state mailing address")
        evidence_score = min(100, 35 + (25 if out_of_state else 0)) if signals else 0
        result.append({
            **lead,
            "sources": sorted(lead["sources"]),
            "source_files": sorted(lead["source_files"]),
            "signals": signals,
            "evidence_score": evidence_score,
            "priority_label": "Evidence priority only",
            "out_of_state": out_of_state,
            "unknowns": ["Property value", "Outstanding debt", "Repairs", "Comparable sales", "Buyer demand"],
        })
    hcad_profiles = enrich_leads(result)
    for lead in result:
        lead["hcad"] = hcad_profiles.get(lead["id"], {})
        lead["intelligence"] = build_profile(lead).to_dict()
    return sorted(result, key=lambda item: (-item["evidence_score"], item["address"]))


def json_response(handler, payload, status=200):
    body = json.dumps(payload, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/leads":
            leads = load_leads()
            query = urllib.parse.parse_qs(parsed.query).get("q", [""])[0].lower().strip()
            if query:
                leads = [lead for lead in leads if query in json.dumps(lead).lower()]
            return json_response(self, {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "count": len(leads),
                "leads": leads,
            })
        if parsed.path == "/api/geocode":
            address = urllib.parse.parse_qs(parsed.query).get("address", [""])[0].strip()
            if not address:
                return json_response(self, {"error": "address is required"}, 400)
            with _cache_lock:
                cache = _read_cache()
                if address in cache:
                    return json_response(self, cache[address])
            query = urllib.parse.urlencode({"q": f"{address}, Harris County, Texas", "format": "jsonv2", "limit": 1})
            request = urllib.request.Request(
                f"https://nominatim.openstreetmap.org/search?{query}",
                headers={"User-Agent": "TexasInvestorsLocalApp/1.0"},
            )
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    matches = json.loads(response.read().decode("utf-8"))
                point = {"lat": float(matches[0]["lat"]), "lon": float(matches[0]["lon"])} if matches else None
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                point = None
            with _cache_lock:
                cache = _read_cache()
                cache[address] = point
                OUTPUT_DIR.mkdir(exist_ok=True)
                GEOCODE_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
            return json_response(self, point or {"error": "location not found"}, 200 if point else 404)
        if parsed.path == "/" or parsed.path == "/index.html":
            return self.serve_file(WEB_DIR / "index.html")
        return self.serve_file(WEB_DIR / parsed.path.lstrip("/"))

    def serve_file(self, path):
        try:
            body = path.read_bytes()
        except (FileNotFoundError, IsADirectoryError):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Texas Investors app: http://localhost:{PORT}")
    print(f"Phone on the same Wi-Fi: http://<this-computer-ip>:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()