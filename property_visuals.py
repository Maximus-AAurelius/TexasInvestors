"""Local photo storage and user-confirmed map locations; no imagery scraping."""
import base64
import binascii
import io
import math
import warnings
from datetime import date, datetime, timezone
from urllib.parse import urlencode

from PIL import Image, ImageOps, UnidentifiedImageError
import intelligence_db

MAX_PHOTO_BYTES = 2_000_000
Image.MAX_IMAGE_PIXELS = 20_000_000


def _connect():
    connection = intelligence_db._connect()
    connection.execute("CREATE TABLE IF NOT EXISTS property_visuals (property_id TEXT PRIMARY KEY, latitude REAL, longitude REAL, photo BLOB, caption TEXT, photo_date TEXT, updated_at TEXT)")
    return connection


def clean_photo(encoded):
    if not isinstance(encoded, str) or len(encoded) > 2_700_000:
        raise ValueError("Choose a JPEG, PNG or WebP photo under 2 MB")
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_PHOTO_BYTES:
            raise ValueError("Photo must be under 2 MB")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise ValueError("Only JPEG, PNG and WebP photos are supported")
                source.load()
                photo = ImageOps.exif_transpose(source).convert("RGB")
                photo.thumbnail((1600, 1600))
                output = io.BytesIO()
                photo.save(output, format="JPEG", quality=85)
                return output.getvalue()
    except (binascii.Error, UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError("Invalid or excessively large image") from None


def save_visual(property_id, payload):
    action = payload.get("action")
    if action == "location":
        coords = []
        for key, limit in (("latitude", 90), ("longitude", 180)):
            raw = payload.get(key)
            try:
                value = float(raw)
            except (ValueError, TypeError):
                raise ValueError(f"{key} must be a number") from None
            if isinstance(raw, bool) or not math.isfinite(value) or abs(value) > limit:
                raise ValueError(f"{key} is outside the valid range")
            coords.append(value)
        columns, values = "latitude=?, longitude=?", coords
    elif action == "photo":
        caption, photo_date = payload.get("caption", ""), payload.get("photo_date", "")
        if not isinstance(caption, str) or len(caption) > 500 or not isinstance(photo_date, str):
            raise ValueError("Photo caption must be text up to 500 characters")
        if photo_date:
            try:
                taken = date.fromisoformat(photo_date)
            except ValueError:
                raise ValueError("Photo date must be YYYY-MM-DD") from None
            if taken > date.today():
                raise ValueError("Photo date cannot be in the future")
        columns, values = "photo=?, caption=?, photo_date=?", [clean_photo(payload.get("image")), caption.strip(), photo_date]
    elif action == "remove_photo":
        columns, values = "photo=NULL, caption=NULL, photo_date=NULL", []
    elif action == "clear_location":
        columns, values = "latitude=NULL, longitude=NULL", []
    else:
        raise ValueError("Unsupported visual action")
    connection = _connect()
    try:
        with connection:
            connection.execute("INSERT OR IGNORE INTO property_visuals(property_id) VALUES (?)", (property_id,))
            connection.execute(f"UPDATE property_visuals SET {columns}, updated_at=? WHERE property_id=?",
                               [*values, datetime.now(timezone.utc).isoformat(), property_id])
    finally:
        connection.close()


def get_visual(property_id):
    connection = _connect()
    try:
        row = connection.execute("SELECT latitude,longitude,photo IS NOT NULL,caption,photo_date,updated_at FROM property_visuals WHERE property_id=?", (property_id,)).fetchone()
    finally:
        connection.close()
    if not row:
        return {"has_photo": False, "latitude": None, "longitude": None}
    lat, lon, has_photo, caption, photo_date, updated = row
    result = {"latitude": lat, "longitude": lon, "has_photo": bool(has_photo), "caption": caption,
              "photo_date": photo_date, "updated_at": updated}
    if lat is not None and lon is not None:
        point = f"{lat},{lon}"
        result["satellite_url"] = "https://www.google.com/maps/@?" + urlencode({"api": 1, "map_action": "map", "center": point, "zoom": 19, "basemap": "satellite"})
        result["street_view_url"] = "https://www.google.com/maps/@?" + urlencode({"api": 1, "map_action": "pano", "viewpoint": point})
    return result


def get_photo(property_id):
    connection = _connect()
    try:
        row = connection.execute("SELECT photo FROM property_visuals WHERE property_id=?", (property_id,)).fetchone()
        return row[0] if row else None
    finally:
        connection.close()


def get_locations():
    connection = _connect()
    try:
        return {row[0]: {"latitude": row[1], "longitude": row[2]} for row in connection.execute("SELECT property_id,latitude,longitude FROM property_visuals")}
    finally:
        connection.close()
