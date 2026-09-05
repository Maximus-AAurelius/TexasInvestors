import base64
import io
import json
import pytest
from PIL import Image
from property_visuals import clean_photo, save_visual, get_visual, get_photo
from tests.test_product_boundaries import local_server, request
from app import LocalAppServer, AppHandler


def encoded_photo():
    buffer = io.BytesIO()
    Image.new("RGB", (1800, 900), "green").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def test_second_server_cannot_share_port():
    server = LocalAppServer(("127.0.0.1", 0), AppHandler)
    try:
        with pytest.raises(OSError):
            LocalAppServer(("127.0.0.1", server.server_port), AppHandler)
    finally:
        server.server_close()


def test_photo_is_validated_and_resized():
    with Image.open(io.BytesIO(clean_photo(encoded_photo()))) as image:
        assert image.format == "JPEG"
        assert image.size == (1600, 800)
        assert not image.getexif()
    for invalid in ("not base64", base64.b64encode(b'<svg onload="alert(1)">').decode(), "a" * 2_700_001):
        with pytest.raises(ValueError):
            clean_photo(invalid)


def test_photo_location_round_trip_and_remove(local_server):
    payload = {"id": "Harris|1 MAIN", "action": "photo", "image": encoded_photo(), "caption": "Own visit"}
    status, body, _ = request(local_server, "/api/visuals", payload)
    assert status == 200 and json.loads(body)["has_photo"]
    status, body, headers = request(local_server, "/api/photo?id=Harris%7C1%20MAIN")
    assert status == 200 and headers["Content-Type"] == "image/jpeg"
    with Image.open(io.BytesIO(body)) as image:
        assert image.size == (1600, 800)
    status, body, _ = request(local_server, "/api/visuals", {"id":payload["id"],"action":"location","latitude":29.76,"longitude":-95.36})
    visual=json.loads(body)
    assert status == 200 and "basemap=satellite" in visual["satellite_url"]
    assert visual["has_photo"]
    assert "map_action=pano" in visual["street_view_url"]
    assert request(local_server, "/api/visuals", {"id":payload["id"],"action":"location","latitude":"NaN","longitude":0})[0] == 400
    assert request(local_server, "/api/visuals", {"id":"unknown","action":"photo","image":encoded_photo()})[0] == 400
    assert request(local_server, "/api/visuals", {"id":payload["id"],"action":"remove_photo"})[0] == 200
    assert not get_visual(payload["id"])["has_photo"]
    assert get_visual(payload["id"])["latitude"] == 29.76
    assert get_photo(payload["id"]) is None
    assert request(local_server, "/api/photo?id=Harris%7C1%20MAIN")[0] == 404
