"""Scenario estimates; public appraisal and missing debt never imply equity."""
from underwriting import CHECK_FIELDS, validate_underwriting


def calculate_deal(underwriting):
    try:
        values = validate_underwriting(underwriting)
    except ValueError as exc:
        return {"status": "invalid", "scenarios": {}, "gross_spread": None,
                "estimated_assignment_fee": None, "estimated_net_spread": None,
                "deal_gap": None, "risk_warnings": [str(exc)],
                "recommendation": "RESEARCH FIRST", "assumptions": {}}
    required = ("arv_low", "arv_base", "arv_high", "repairs_low", "repairs_expected",
                "repairs_high", "transaction_costs", "buyer_margin", "risk_adjustment")
    missing = [key.replace("_", " ") for key in required if values[key] is None]
    warnings = ["Missing assumptions: " + ", ".join(missing)] if missing else []
    scenarios = {}
    if not missing:
        for name, arv, repairs in (("conservative", "arv_low", "repairs_high"),
                                   ("base", "arv_base", "repairs_expected"),
                                   ("optimistic", "arv_high", "repairs_low")):
            ceiling = round(values[arv] - values[repairs] - values["transaction_costs"]
                            - values["buyer_margin"] - values["risk_adjustment"], 2)
            fee = values["target_assignment_fee"]
            scenarios[name] = {"arv": values[arv], "repairs": values[repairs],
                               "maximum_acquisition": ceiling,
                               "maximum_seller_price": round(ceiling - fee, 2) if fee is not None else None}
    buyer, contract = values["buyer_price"], values["contract_price"]
    gross = round(buyer - contract, 2) if buyer is not None and contract is not None else None
    costs = values["assignment_costs"]
    net = round(gross - costs, 2) if gross is not None and costs is not None else None
    gap = round(buyer - scenarios["base"]["maximum_acquisition"], 2) if buyer is not None and scenarios else None
    current, debt = values["current_value"], values["estimated_debt"]
    equity = round(current - debt, 2) if current is not None and debt is not None else None
    if buyer is None or contract is None:
        warnings.append("Buyer and contract prices are needed to estimate assignment fee")
    if costs is None:
        warnings.append("Your assignment costs are unknown; net proceeds are not calculated")
    if equity is None:
        warnings.append("Equity is unknown until current value and debt are supplied")
    else:
        warnings.append("Equity is a manual estimate before selling costs and any omitted liens")
    if scenarios and scenarios["conservative"]["maximum_acquisition"] < 0:
        warnings.append("Conservative case produces a negative buyer acquisition ceiling")
    if gap is not None and gap > 0:
        warnings.append(f"Buyer price exceeds base acquisition ceiling by ${gap:,.0f}")
    if buyer is not None and scenarios and buyer > scenarios["conservative"]["maximum_acquisition"]:
        warnings.append("Buyer price does not meet the conservative scenario margin")
    unchecked = [key for key in CHECK_FIELDS if not values[key]]
    if unchecked:
        warnings.append("Due diligence remains: " + ", ".join(key.replace("_", " ") for key in unchecked))
    if missing or contract is None:
        action = "RESEARCH FIRST"
    elif (gross is not None and gross <= 0) or (net is not None and net <= 0):
        action = "RENEGOTIATE OR SKIP"
    elif gap is not None and gap > 0:
        action = "RENEGOTIATE"
    elif buyer is None:
        action = "FIND BUYER"
    else:
        action = "VERIFY WITH TITLE COMPANY"
    return {"scenarios": scenarios, "gross_spread": gross, "estimated_assignment_fee": gross,
            "estimated_net_spread": net, "estimated_equity": equity, "deal_gap": gap,
            "risk_warnings": warnings, "recommendation": action,
            "assumptions": {key: values[key] for key in ("transaction_costs", "buyer_margin", "risk_adjustment", "assignment_costs", "target_assignment_fee")},
            "due_diligence_complete": not unchecked, "status": "calculated" if scenarios else "incomplete"}
