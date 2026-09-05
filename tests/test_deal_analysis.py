from deal_analysis import calculate_deal


def test_deal_scenarios_and_spread():
    result = calculate_deal({
        "arv_low": 300000, "arv_base": 340000, "arv_high": 370000,
        "repairs_low": 35000, "repairs_expected": 50000, "repairs_high": 75000,
        "transaction_costs": 5000, "buyer_margin": 40000, "risk_adjustment": 10000,
        "buyer_price": 240000, "contract_price": 195000,
    })

    assert result["scenarios"]["conservative"]["maximum_acquisition"] == 170000
    assert result["scenarios"]["base"]["maximum_acquisition"] == 235000
    assert result["scenarios"]["optimistic"]["maximum_acquisition"] == 280000
    assert result["gross_spread"] == 45000
    assert result["estimated_assignment_fee"] == 45000
    assert result["estimated_net_spread"] is None
    assert result["deal_gap"] == 5000


def test_incomplete_deal_does_not_invent_economics():
    result = calculate_deal({})

    assert result["status"] == "incomplete"
    assert result["scenarios"] == {}
    assert result["gross_spread"] is None
    assert result["recommendation"] == "RESEARCH FIRST"
