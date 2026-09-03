"""Transparent deal calculations for manual underwriting scenarios."""


def _number(values, key):
    value = values.get(key)
    return float(value) if value not in (None, "") else None


def calculate_deal(underwriting):
    """Calculate scenario economics without filling missing assumptions."""
    arv = {key: _number(underwriting, key) for key in ("arv_low", "arv_base", "arv_high")}
    repairs = {key: _number(underwriting, key) for key in ("repairs_low", "repairs_expected", "repairs_high")}
    transaction_costs = _number(underwriting, "transaction_costs")
    buyer_margin = _number(underwriting, "buyer_margin")
    risk_adjustment = _number(underwriting, "risk_adjustment")
    buyer_price = _number(underwriting, "buyer_price")
    contract_price = _number(underwriting, "contract_price")

    missing = []
    for key, values in (("ARV", arv), ("repairs", repairs)):
        if any(value is None for value in values.values()):
            missing.append(key)
    for key, value in (("transaction costs", transaction_costs), ("buyer margin", buyer_margin), ("risk adjustment", risk_adjustment)):
        if value is None:
            missing.append(key)

    scenarios = {}
    if not missing:
        scenarios = {
            "conservative": {"arv": arv["arv_low"], "repairs": repairs["repairs_high"]},
            "base": {"arv": arv["arv_base"], "repairs": repairs["repairs_expected"]},
            "optimistic": {"arv": arv["arv_high"], "repairs": repairs["repairs_low"]},
        }
        for scenario in scenarios.values():
            scenario["maximum_acquisition"] = round(scenario["arv"] - scenario["repairs"] - transaction_costs - buyer_margin - risk_adjustment, 2)

    gross_spread = None
    deal_gap = None
    if buyer_price is not None and contract_price is not None:
        gross_spread = round(buyer_price - contract_price - (transaction_costs or 0), 2)
    if contract_price is not None and scenarios.get("base"):
        deal_gap = round(contract_price - scenarios["base"]["maximum_acquisition"], 2)

    warnings = []
    if missing:
        warnings.append("Missing assumptions: " + ", ".join(missing))
    if scenarios and scenarios["conservative"]["maximum_acquisition"] < 0:
        warnings.append("Conservative case produces a negative maximum acquisition price")
    if deal_gap is not None and deal_gap > 0:
        warnings.append(f"Contract price is ${deal_gap:,.0f} above the base maximum acquisition")
    if buyer_price is None or contract_price is None:
        warnings.append("Buyer and contract prices are needed to estimate spread")

    if missing:
        recommendation = "RESEARCH FIRST"
    elif gross_spread is not None and gross_spread <= 0:
        recommendation = "SKIP"
    elif deal_gap is not None and deal_gap > 0:
        recommendation = "RESEARCH FIRST"
    elif buyer_price is None:
        recommendation = "FIND BUYER"
    else:
        recommendation = "VERIFY EQUITY"

    return {
        "scenarios": scenarios,
        "gross_spread": gross_spread,
        "estimated_assignment_fee": gross_spread,
        "deal_gap": deal_gap,
        "risk_warnings": warnings,
        "recommendation": recommendation,
        "assumptions": {"transaction_costs": transaction_costs, "buyer_margin": buyer_margin, "risk_adjustment": risk_adjustment},
        "status": "calculated" if scenarios else "incomplete",
    }