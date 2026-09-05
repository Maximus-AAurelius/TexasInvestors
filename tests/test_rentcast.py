import io
import json
import urllib.error

import pytest

import rentcast


class _FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_requires_an_api_key(monkeypatch):
    monkeypatch.delenv("RENTCAST_API_KEY", raising=False)
    with pytest.raises(rentcast.RentCastError, match="API key"):
        rentcast.get_comps("123 Main St, Houston, TX 77002")


def test_requires_a_nonempty_address():
    with pytest.raises(rentcast.RentCastError, match="address"):
        rentcast.get_comps("", api_key="test-key")


def test_rejects_out_of_range_comp_count():
    with pytest.raises(rentcast.RentCastError, match="comp_count"):
        rentcast.get_comps("123 Main St", api_key="test-key", comp_count=100)


def test_sends_the_api_key_header_and_returns_parsed_json(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.headers.items()}
        return _FakeResponse({"price": 250000, "comparables": [{"formattedAddress": "1 Pine Ln", "price": 240000}]})

    monkeypatch.setattr(rentcast.urllib.request, "urlopen", fake_urlopen)
    result = rentcast.get_comps("123 Main St, Houston, TX 77002", api_key="test-key")

    assert captured["headers"]["x-api-key"] == "test-key"
    assert "avm/value" in captured["url"]
    assert result["price"] == 250000
    assert result["comparables"][0]["formattedAddress"] == "1 Pine Ln"


def test_reads_the_api_key_from_the_environment(monkeypatch):
    monkeypatch.setenv("RENTCAST_API_KEY", "env-key")
    captured = {}

    def fake_urlopen(request, timeout):
        captured["headers"] = {k.lower(): v for k, v in request.headers.items()}
        return _FakeResponse({"price": 100})

    monkeypatch.setattr(rentcast.urllib.request, "urlopen", fake_urlopen)
    rentcast.get_comps("123 Main St")

    assert captured["headers"]["x-api-key"] == "env-key"


@pytest.mark.parametrize("code,fragment", [(401, "API key"), (404, "no property record"), (429, "quota")])
def test_translates_http_errors_into_clear_messages(monkeypatch, code, fragment):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, code, "error", {}, io.BytesIO(b"detail"))

    monkeypatch.setattr(rentcast.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(rentcast.RentCastError, match=fragment):
        rentcast.get_comps("123 Main St", api_key="test-key")
