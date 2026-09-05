"""Explainable workflow priority, not an appraisal or profitability prediction."""
from underwriting import CHECK_FIELDS


def rate_pursuit(lead):
    deal = lead.get("intelligence", {}).get("deal", {})
    uw = lead.get("underwriting", {})
    comps = lead.get("comps", {}).get("sales", [])
    result = {"color": "gray", "label": "More evidence needed", "reasons": [],
              "model_version": "pursuit-v1", "basis": "Manual inputs and user reviews; not independently verified or a profit guarantee"}
    net = deal.get("estimated_net_spread")
    if net is not None and net <= 0:
        result.update(color="red", label="Economics fail", reasons=["Entered buyer price minus contract price and your costs leaves zero or negative net proceeds"])
        return result
    if deal.get("status") != "calculated" or net is None:
        result["reasons"] = ["Complete ARV/repair ranges, buyer costs, target margin, buyer price, contract price and your costs"]
        if not comps:
            result["reasons"].append("No qualifying recent sold comparisons available")
        return result
    reasons = []
    if lead.get("identity_conflict"):
        reasons.append("Source records disagree on owner identity")
    buyer = uw.get("buyer_price")
    ceiling = deal["scenarios"]["conservative"]["maximum_acquisition"]
    if buyer is None or buyer > ceiling:
        reasons.append("Buyer acquisition price exceeds the conservative scenario ceiling")
    if deal.get("estimated_equity") is None:
        reasons.append("Current value or outstanding debt is unknown")
    elif deal["estimated_equity"] <= 0:
        reasons.append("Entered value minus debt shows no positive equity; resolve payoff feasibility")
    if len(comps) < 3 or not all(sale.get("reviewed") for sale in comps):
        reasons.append("Three qualifying recent sales with user-reviewed evidence are required")
    missing = [field.replace("_", " ") for field in CHECK_FIELDS if uw.get(field) is not True]
    if missing:
        reasons.append("Review outstanding: " + ", ".join(missing))
    target = uw.get("target_assignment_fee")
    if target is None:
        reasons.append("Set your target assignment fee")
    elif deal.get("estimated_assignment_fee", 0) < target:
        reasons.append("Estimated gross assignment fee is below your target")
    if reasons:
        result.update(color="amber", label="Resolve concerns", reasons=reasons)
    else:
        result.update(color="green", label="Ready for final review", reasons=[
            "Positive estimated net proceeds and target gross fee met",
            "Buyer price fits the conservative acquisition ceiling",
            "Three qualifying sales and all due-diligence checks are marked reviewed by you",
            "Entered value exceeds entered debt; confirm current payoff with title company"])
    return result
