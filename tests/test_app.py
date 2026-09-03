from app import load_leads


def test_dashboard_loads_real_property_records():
    leads = load_leads()

    assert leads
    assert all(lead["address"] for lead in leads)
    assert all("Property value" in lead["unknowns"] for lead in leads)
    assert all(lead["priority_label"] == "Evidence priority only" for lead in leads)