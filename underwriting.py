"""Validated manual assumptions shared by HTTP and scenario calculations."""
import math

MONEY_FIELDS = (
    "current_value", "arv_low", "arv_base", "arv_high", "repairs_low",
    "repairs_expected", "repairs_high", "estimated_debt", "transaction_costs",
    "buyer_margin", "risk_adjustment", "buyer_price", "contract_price",
    "assignment_costs", "target_assignment_fee",
)
CHECK_FIELDS = (
    "comps_reviewed", "repairs_reviewed", "payoff_reviewed", "title_reviewed",
    "buyer_confirmed", "contract_reviewed", "seller_disclosure", "buyer_disclosure",
)


def validate_underwriting(values):
    if not isinstance(values, dict):
        raise ValueError("Underwriting must be an object")
    result = {}
    for key in MONEY_FIELDS:
        raw = values.get(key)
        if raw is None or raw == "":
            result[key] = None
            continue
        if isinstance(raw, bool):
            raise ValueError(f"{key} must be a finite nonnegative number")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{key} must be numeric") from None
        if not math.isfinite(value) or not 0 <= value <= 1_000_000_000:
            raise ValueError(f"{key} must be between 0 and 1 billion")
        result[key] = value
    for keys in (("arv_low", "arv_base", "arv_high"), ("repairs_low", "repairs_expected", "repairs_high")):
        present = [result[key] for key in keys if result[key] is not None]
        if present != sorted(present):
            raise ValueError(f"{', '.join(keys)} must be in ascending order")
    notes = values.get("assumptions", "")
    if not isinstance(notes, str) or len(notes) > 10000:
        raise ValueError("Notes must be text up to 10,000 characters")
    result["assumptions"] = notes.strip()
    for key in CHECK_FIELDS:
        value = values.get(key, False)
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false")
        result[key] = value
    return result
