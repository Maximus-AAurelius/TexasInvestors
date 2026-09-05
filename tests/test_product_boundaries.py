import json
import threading
import http.client
from http.server import ThreadingHTTPServer

import pytest
import app
import intelligence_db
from buyers import validate_buyer, match_buyers
from deal_analysis import calculate_deal
from intelligence import build_profile
from underwriting import validate_underwriting


@pytest.fixture
def local_server(tmp_path, monkeypatch):
    monkeypatch.setattr(intelligence_db, "DB_PATH", tmp_path / "db.sqlite")
    monkeypatch.setattr(app, "STATUS_PATH", tmp_path / "status.json")
    monkeypatch.setattr(app, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(app, "load_leads", lambda: [{"id": "Harris|1 MAIN", "address": "1 MAIN"}])
    server = ThreadingHTTPServer(("127.0.0.1", 0), app.AppHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield server
    server.shutdown()
    server.server_close()
    worker.join()


def request(server, path, data=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    defaults = {"Content-Type": "application/json", "X-TX-Request": "1"}
    defaults.update(headers or {})
    connection.request("GET" if data is None else "POST", path,
                       None if data is None else json.dumps(data), defaults)
    response = connection.getresponse()
    result = response.status, response.read(), dict(response.getheaders())
    connection.close()
    return result


@pytest.mark.parametrize("path", ["/../app.py", "/%2e%2e/app.py", "/..%5capp.py", "/C:/Windows/win.ini"])
def test_static_traversal_blocked(local_server, path):
    assert request(local_server, path)[0] == 404


def test_host_and_origin_boundaries(local_server):
    assert request(local_server, "/", headers={"Host": "attacker.example"})[0] == 403
    assert request(local_server, "/api/status", {"id": "Harris|1 MAIN", "status": "saved"},
                   {"Origin": "https://attacker.example"})[0] == 403
    status, body, headers = request(local_server, "/")
    assert status == 200
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


def test_write_round_trip_and_bad_payloads(local_server):
    payload = {"id": "Harris|1 MAIN", "underwriting": {"transaction_costs": 5000, "assignment_costs": 1000}}
    status, body, _ = request(local_server, "/api/underwriting", payload)
    assert status == 200
    assert json.loads(body)["underwriting"]["transaction_costs"] == 5000
    assert intelligence_db.get_underwritings()[payload["id"]]["assignment_costs"] == 1000
    for values in ({"arv_base": "NaN"}, {"arv_base": True}, {"arv_low": 200, "arv_high": 100}):
        assert request(local_server, "/api/underwriting", {**payload, "underwriting": values})[0] == 400
    assert request(local_server, "/api/status", {"id": [], "status": "saved"})[0] == 400
    assert request(local_server, "/api/status", {"id": "Harris|1 MAIN", "status": []})[0] == 400
    assert request(local_server, "/api/status", {"id": "missing", "status": "saved"})[0] == 400
    assert request(local_server, "/api/status", {"id": "Harris|1 MAIN", "status": "saved"})[0] == 200
    assert request(local_server, "/api/status", {"id": "Harris|1 MAIN", "status": "new"}, {"X-TX-Request": ""})[0] == 403


@pytest.mark.parametrize("value", [float('nan'), float('inf'), -1, True, [], 1e99])
def test_invalid_money_rejected(value):
    with pytest.raises(ValueError):
        validate_underwriting({"buyer_price": value})
    assert calculate_deal({"buyer_price": value})["status"] == "invalid"


def test_assignment_costs_and_missing_debt():
    deal = calculate_deal({"buyer_price": 200000, "contract_price": 180000, "assignment_costs": 1500, "transaction_costs": 25000})
    assert deal["gross_spread"] == 20000
    assert deal["estimated_net_spread"] == 18500
    assert deal["estimated_equity"] is None


def test_no_invented_absentee_or_verified_identity():
    profile = build_profile({"id": "1", "address": "1 MAIN", "county": "Harris", "owner_name": "A", "sources": []})
    assert profile.signals == []
    assert profile.data_states["identity"] == "REPORTED"
    assert profile.scores["motivation"] == 0


def test_buyer_lifecycle_and_matching(local_server):
    status, raw, _ = request(local_server, "/api/buyers", {"name": "Test buyer", "county": "Harris", "max_price": 200000})
    assert status == 200
    buyer = json.loads(raw)["buyer"]
    assert len(intelligence_db.get_buyers()) == 1
    assert match_buyers({"county": "Harris", "underwriting": {"buyer_price": 210000}}, [buyer]) == []
    matches = match_buyers({"county": "Harris", "underwriting": {}}, [buyer])
    assert "Buyer price or buyer limit unknown" in matches[0]["gaps"]
    assert request(local_server, "/api/buyers", {**buyer, "name": "Updated"})[0] == 200
    assert intelligence_db.get_buyers()[0]["name"] == "Updated"
    assert request(local_server, "/api/buyers/delete", {"id": buyer["id"]})[0] == 200
    assert intelligence_db.get_buyers() == []


def test_export_formula_escaped():
    assert app.csv_safe(' =HYPERLINK("x")').startswith("'")
    assert app.csv_safe("123 Main") == "123 Main"
