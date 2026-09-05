"""Manual buyer criteria; a criteria match is never proof of funding."""
import math
import uuid
from datetime import date
from markets import normalize_county


def validate_buyer(payload):
    result = {}
    for key, limit in (("name", 160), ("county", 80), ("property_class", 20), ("notes", 3000), ("contact", 250), ("confirmed_on", 10)):
        value = payload.get(key, "")
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f"{key} must be text up to {limit} characters")
        result[key] = value.strip()
    if not result["name"] or not result["county"]:
        raise ValueError("Buyer name and county are required")
    result["county"] = normalize_county(result["county"])
    if result["confirmed_on"]:
        try:
            confirmed = date.fromisoformat(result["confirmed_on"])
        except ValueError:
            raise ValueError("Confirmation date must be YYYY-MM-DD") from None
        if confirmed > date.today():
            raise ValueError("Confirmation date cannot be in the future")
    for key in ("max_price", "max_repairs"):
        raw = payload.get(key)
        if raw in (None, ""):
            result[key] = None
        else:
            try:
                value = float(raw)
            except (ValueError, TypeError):
                raise ValueError(f"{key} must be numeric") from None
            if isinstance(raw, bool) or not math.isfinite(value) or not 0 <= value <= 1_000_000_000:
                raise ValueError(f"{key} must be between 0 and 1 billion")
            result[key] = value
    result["id"] = str(uuid.uuid4())
    return result


def match_buyers(lead, buyers):
    matches = []
    for buyer in buyers:
        if buyer["county"].casefold() != lead["county"].casefold():
            continue
        reasons, gaps = ["County matches"], []
        property_class = lead.get("hcad", {}).get("property_type")
        if buyer["property_class"]:
            if not property_class:
                gaps.append("Property class unknown")
            elif property_class.upper() != buyer["property_class"].upper():
                continue
            else:
                reasons.append("Property class matches")
        for limit, field, label in (("max_price", "buyer_price", "Buyer price"), ("max_repairs", "repairs_high", "Conservative repairs")):
            value = lead.get("underwriting", {}).get(field)
            if value is None or buyer[limit] is None:
                gaps.append(f"{label} or buyer limit unknown")
            elif value > buyer[limit]:
                break
            else:
                reasons.append(f"{label} within stated limit")
        else:
            gaps.append("Reconfirm current interest, funds and assignment acceptance")
            matches.append({"buyer": buyer, "reasons": reasons, "gaps": gaps})
    return matches
