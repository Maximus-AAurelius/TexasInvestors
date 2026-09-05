"""Loopback-only property research, buyer criteria and underwriting workspace."""
import csv
import json
import mimetypes
import os
import socket
import ssl
import ipaddress
import threading
import urllib.parse
from io import StringIO
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from intelligence import build_profile
from hcad_profile import enrich_leads
from intelligence_db import get_underwritings, record_action, save_profiles, save_underwriting
from underwriting import validate_underwriting
from deal_analysis import calculate_deal
from buyers import validate_buyer, match_buyers
from intelligence_db import get_buyers, save_buyer, delete_buyer
from markets import market_catalog, normalize_county
from property_visuals import get_visual, get_photo, save_visual
from property_visuals import get_locations
from comps import get_sales, save_sales, import_csv, select_comps, delete_sale
from pursuit import rate_pursuit
from phone_access import authorized, start_phone
from intelligence_db import get_property_lookup
from lookup import run_lookup

ROOT = Path(__file__).parent
WEB_DIR = ROOT / "web"
OUTPUT_DIR = ROOT / "output"
GEOCODE_CACHE = OUTPUT_DIR / "geocode_cache.json"
STATUS_PATH = OUTPUT_DIR / "lead_status.json"
HOST = os.environ.get("TX_APP_HOST", "127.0.0.1")
PORT = int(os.environ.get("TX_APP_PORT", "8765"))
_cache_lock = threading.Lock()


def _read_cache():
    try:
        return json.loads(GEOCODE_CACHE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _read_statuses():
    try:
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def load_leads():
    leads = {}
    statuses = _read_statuses()
    paths = set(ROOT.glob("*.csv")) | set(OUTPUT_DIR.glob("*.csv"))
    imports = ROOT / "data" / "imports"
    paths.update(imports.glob("*.csv"))
    for path in sorted(paths):
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        try:
            with path.open(newline="", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    address = (row.get("address") or "").strip()
                    if not address or address.startswith("(address unknown"):
                        continue
                    try:
                        county = normalize_county(row.get("county", ""))
                    except ValueError:
                        continue
                    row["county"] = county
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
                        "source_evidence": [],
                                    "status": statuses.get(key, "new"),
                    })
                    # Adapter/manual CSVs carry one source_type per row;
                    # the pipeline's own leads_*.csv sidecar carries the
                    # whole cluster in sources_hit. Read either.
                    joined = (row.get("sources_hit") or "").strip()
                    if joined:
                        for source in joined.replace(",", ";").split(";"):
                            if source.strip():
                                lead["sources"].add(source.strip())
                    else:
                        lead["sources"].add((row.get("source_type") or path.stem).strip())
                    lead["source_files"].add(str(path.relative_to(ROOT)))
                    row_sources = [s.strip() for s in joined.replace(",", ";").split(";") if s.strip()] if joined else [(row.get("source_type") or path.stem).strip()]
                    for row_source in row_sources:
                        lead["source_evidence"].append({"source_type": row_source, "source_file": str(path.relative_to(ROOT)),
                            "source_url": row.get("source_url") or row.get("source_urls") or "",
                            "recorded_date": row.get("date_recorded") or "", "retrieved_at": row.get("retrieved_at") or "",
                            "owner_name": row.get("owner_name") or "", "case_no": row.get("case_no") or row.get("case_numbers") or "",
                            "address_source": row.get("address_source") or "reported", "verification_status": "unreviewed"})
                    lead["raw"].update({k: v for k, v in row.items() if v})
        except (OSError, UnicodeError, csv.Error, AttributeError):
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
    underwritings = get_underwritings()
    buyers = get_buyers()
    sales = get_sales()
    locations = get_locations()
    for lead in result:
        lead["hcad"] = hcad_profiles.get(lead["id"], {})
        lead["identity_conflict"] = len({e["owner_name"].strip().upper() for e in lead["source_evidence"] if e["owner_name"].strip()}) > 1
        lead["underwriting"] = underwritings.get(lead["id"], {})
        lead["intelligence"] = build_profile(lead).to_dict()
        lead["buyer_matches"] = match_buyers(lead, buyers)
        lead["comps"] = select_comps(lead, sales, locations.get(lead["id"]))
        lead["pursuit"] = rate_pursuit(lead)
        lead["market_lookup"] = get_property_lookup(lead["address"], lead["county"])
    save_profiles(result)
    return sorted(result, key=lambda item: (-item["evidence_score"], item["address"]))


def valid_lead_id(value):
    return isinstance(value, str) and len(value) <= 500 and any(lead["id"] == value for lead in load_leads())


def csv_safe(value):
    text = str(value) if value is not None else ""
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")) or text.startswith(("\t", "\r", "\n")) else text


def json_response(handler, payload, status=200):
    body = json.dumps(payload, default=str, allow_nan=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except ConnectionError:
        pass  # Browser navigation may cancel a response already being generated.


class AppHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        super().end_headers()

    def _trusted_request(self, write=False):
        allowed = getattr(self.server, "allowed_hosts", {f"localhost:{self.server.server_port}", f"127.0.0.1:{self.server.server_port}"})
        host = self.headers.get("Host", "").lower()
        if host not in allowed:
            json_response(self, {"error": "Use the local application address"}, 403)
            return False
        origin = self.headers.get("Origin")
        scheme = getattr(self.server, "url_scheme", "http")
        if origin and origin != f"{scheme}://{host}":
            json_response(self, {"error": "Cross-origin requests are not allowed"}, 403)
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            json_response(self, {"error": "Cross-site requests are not allowed"}, 403)
            return False
        token = getattr(self.server, "auth_token", None)
        if token and not authorized(self.headers.get("Authorization"), token):
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Texas Investors", charset="UTF-8"')
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return False
        if write and (self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json"
                      or self.headers.get("X-TX-Request") != "1"):
            json_response(self, {"error": "JSON and X-TX-Request headers are required"}, 403)
            return False
        return True

    def _request_body(self, max_bytes=65536):
        try:
            if self.headers.get("Transfer-Encoding"):
                return None
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= max_bytes:
                return None
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeError, json.JSONDecodeError):
            return None

    def do_GET(self):
        if not self._trusted_request():
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/phone":
            if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                return json_response(self, {"error": "View phone setup on the desktop computer"}, 403)
            return json_response(self, getattr(self.server, "phone_details", {"enabled": False}))
        if parsed.path == "/api/health":
            return json_response(self, {"app": "TexasInvestors", "version": "local-v2"})
        if parsed.path == "/api/sales":
            return json_response(self, {"sales": get_sales(), "coverage": "Imported records only; no connected live sold-price feed"})
        if parsed.path in {"/api/visuals", "/api/photo"}:
            property_id = urllib.parse.parse_qs(parsed.query).get("id", [""])[0]
            if not valid_lead_id(property_id):
                return json_response(self, {"error": "Unknown property id"}, 400)
            if parsed.path == "/api/visuals":
                return json_response(self, get_visual(property_id))
            body = get_photo(property_id)
            if body is None:
                return json_response(self, {"error": "No photo attached"}, 404)
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/api/markets":
            return json_response(self, {"strategy": "purchase_contract_assignment", "markets": market_catalog()})
        if parsed.path == "/api/buyers":
            return json_response(self, {"buyers": get_buyers()})
        if parsed.path == "/api/leads":
            leads = load_leads()
            params = urllib.parse.parse_qs(parsed.query)
            county_filter = params.get("county", [""])[0].strip()
            if county_filter:
                try:
                    county_filter = normalize_county(county_filter)
                except ValueError as exc:
                    return json_response(self, {"error": str(exc)}, 400)
                leads = [lead for lead in leads if lead["county"] == county_filter]
            query = params.get("q", [""])[0].lower().strip()
            if query:
                leads = [lead for lead in leads if query in json.dumps(lead).lower()]
            status = params.get("status", [""])[0].lower().strip()
            if status:
                leads = [lead for lead in leads if lead["status"] == status]
            out_of_state = params.get("out_of_state", [""])[0].lower().strip()
            if out_of_state == "true":
                leads = [lead for lead in leads if lead["out_of_state"]]
            property_class = params.get("property_class", [""])[0].upper().strip()
            if property_class:
                leads = [lead for lead in leads if lead.get("hcad", {}).get("property_type") == property_class]
            min_value = params.get("min_value", [""])[0].strip()
            if min_value:
                try:
                    floor = float(min_value)
                    leads = [lead for lead in leads if (lead.get("hcad", {}).get("hcad_market_value") or 0) >= floor]
                except ValueError:
                    pass
            return json_response(self, {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "count": len(leads),
                "leads": leads,
            })
        if parsed.path == "/api/export":
            output = StringIO()
            fields = ["address", "owner_name", "county", "status", "sources", "mailing_address", "parcel_id", "property_type", "building_sqft", "year_improved", "lot_acres", "hcad_market_value", "ownership_duration_years"]
            writer = csv.DictWriter(output, fieldnames=fields)
            writer.writeheader()
            for lead in load_leads():
                facts = lead.get("hcad", {})
                row = {field: ", ".join(lead[field]) if field == "sources" else facts.get(field, lead.get(field, "")) for field in fields}
                writer.writerow({key: csv_safe(value) for key, value in row.items()})
            body = output.getvalue().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", "attachment; filename=texas_investors_leads.csv")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if parsed.path == "/" or parsed.path == "/index.html":
            return self.serve_file(WEB_DIR / "index.html")
        return self.serve_file(WEB_DIR / urllib.parse.unquote(parsed.path).lstrip("/"))

    def do_POST(self):
        if not self._trusted_request(write=True):
            return
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in {"/api/sales", "/api/sales/import", "/api/sales/delete"}:
            payload = self._request_body(max_bytes=600_000)
            if not isinstance(payload, dict):
                return json_response(self, {"error": "A JSON object under 600 KB is required"}, 400)
            try:
                if parsed.path.endswith("/import"):
                    count = import_csv(payload.get("csv"))
                elif parsed.path.endswith("/delete"):
                    delete_sale(payload.get("id"))
                    count = 0
                else:
                    count = save_sales([payload])
            except (ValueError, csv.Error) as exc:
                return json_response(self, {"error": str(exc)}, 400)
            return json_response(self, {"saved": count})
        if parsed.path == "/api/visuals":
            payload = self._request_body(max_bytes=2_800_000)
            if not isinstance(payload, dict) or not valid_lead_id(payload.get("id")):
                return json_response(self, {"error": "A known property id and payload under 2.8 MB are required"}, 400)
            try:
                save_visual(payload["id"], payload)
            except ValueError as exc:
                return json_response(self, {"error": str(exc)}, 400)
            return json_response(self, get_visual(payload["id"]))
        if parsed.path in {"/api/buyers", "/api/buyers/delete"}:
            payload = self._request_body()
            if not isinstance(payload, dict):
                return json_response(self, {"error": "An object is required"}, 400)
            if parsed.path.endswith("/delete"):
                if not isinstance(payload.get("id"), str):
                    return json_response(self, {"error": "Buyer id is required"}, 400)
                delete_buyer(payload["id"])
                return json_response(self, {"ok": True})
            try:
                buyer = validate_buyer(payload)
            except ValueError as exc:
                return json_response(self, {"error": str(exc)}, 400)
            if payload.get("id"):
                if not isinstance(payload["id"], str) or not any(b["id"] == payload["id"] for b in get_buyers()):
                    return json_response(self, {"error": "Unknown buyer id"}, 400)
                buyer["id"] = payload["id"]
            save_buyer(buyer)
            return json_response(self, {"buyer": buyer})
        if parsed.path == "/api/underwriting":
            payload = self._request_body()
            if not isinstance(payload, dict) or not payload.get("id") or not isinstance(payload.get("underwriting"), dict):
                return json_response(self, {"error": "id and underwriting object are required"}, 400)
            if not valid_lead_id(payload.get("id")):
                return json_response(self, {"error": "Unknown property id"}, 400)
            try:
                underwriting = validate_underwriting(payload["underwriting"])
            except ValueError as exc:
                return json_response(self, {"error": str(exc)}, 400)
            save_underwriting(payload["id"], underwriting)
            return json_response(self, {"id": payload["id"], "underwriting": underwriting, "deal": calculate_deal(underwriting)})
        if parsed.path == "/api/lookup":
            payload = self._request_body()
            if not isinstance(payload, dict) or not isinstance(payload.get("id"), str) or len(payload["id"]) > 500:
                return json_response(self, {"error": "A known property id is required"}, 400)
            lead = next((lead for lead in load_leads() if lead["id"] == payload["id"]), None)
            if lead is None:
                return json_response(self, {"error": "Unknown property id"}, 400)
            try:
                result = run_lookup(lead["address"], county=lead["county"])
            except ValueError as exc:
                return json_response(self, {"error": str(exc)}, 400)
            return json_response(self, result)
        if parsed.path != "/api/status":
            self.send_error(404)
            return
        payload = self._request_body()
        if not isinstance(payload, dict) or not isinstance(payload.get("status"), str) or payload.get("status") not in {"new", "researching", "saved", "contacted", "skipped"} or not valid_lead_id(payload.get("id")):
            return json_response(self, {"error": "id and a valid status are required"}, 400)
        with _cache_lock:
            statuses = _read_statuses()
            statuses[payload["id"]] = payload["status"]
            OUTPUT_DIR.mkdir(exist_ok=True)
            temporary = STATUS_PATH.with_suffix(".tmp")
            temporary.write_text(json.dumps(statuses, indent=2), encoding="utf-8")
            temporary.replace(STATUS_PATH)
            record_action(payload["id"], payload["status"])
        return json_response(self, {"id": payload["id"], "status": payload["status"]})

    def serve_file(self, path):
        try:
            path = path.resolve()
            path.relative_to(WEB_DIR.resolve())
            body = path.read_bytes()
        except (OSError, ValueError):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


class LocalAppServer(ThreadingHTTPServer):
    """Reserve the port exclusively on Windows; never share it with stale servers."""
    allow_reuse_address = False

    def get_request(self):
        connection, address = super().get_request()
        if getattr(self, "tls_context", None):
            connection.settimeout(5)
            try:
                connection = self.tls_context.wrap_socket(connection, server_side=True)
            except (ssl.SSLError, OSError):
                connection.close()
                raise
        return connection, address

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


if __name__ == "__main__":
    if HOST not in {"127.0.0.1", "localhost"}:
        raise SystemExit("This local edition supports TX_APP_HOST=127.0.0.1 or localhost only.")
    server = LocalAppServer((HOST, PORT), AppHandler)
    phone_server = None
    try:
        phone_server, server.phone_details = start_phone(ROOT, LocalAppServer, AppHandler)
    except (OSError, ValueError, KeyError) as exc:
        server.phone_details = {"enabled": False, "error": str(exc)}
    print(f"Texas Investors app: http://localhost:{PORT}")
    print("Local edition: access from this computer. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if phone_server:
            phone_server.shutdown()
            phone_server.server_close()
        server.server_close()
