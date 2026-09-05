import copy
import json
from datetime import date, timedelta
import pytest
from comps import validate_sale, select_comps, save_sales, get_sales, import_csv, distance_miles
from pursuit import rate_pursuit
from deal_analysis import calculate_deal
from underwriting import CHECK_FIELDS
from tests.test_product_boundaries import local_server, request


def sale(days=10, address="200 Example St", **changes):
    values = {"address":address,"county":"Harris","sale_price":300000,"sale_date":(date.today()-timedelta(days=days)).isoformat(),
              "building_sqft":2000,"property_class":"A1","latitude":29.7601,"longitude":-95.36,
              "source_url":"https://example.test/closed-sale","source_reference":"TEST FIXTURE ONLY","sale_status":"closed","reviewed":True}
    return validate_sale({**values,**changes})


def subject():
    return {"id":"Harris|1 MAIN","address":"1 Main","county":"Harris","hcad":{"property_type":"A1","building_sqft":2000}}


LOCATION={"latitude":29.76,"longitude":-95.36}


def test_newest_three_with_strict_filters_and_self_exclusion():
    rows=[sale(days=d,address=f"{200+d} Example St") for d in (20,5,10,1)]
    rows += [sale(address="1 Main"),sale(days=181,address="Old"),sale(address="Far",latitude=30.76),
             sale(address="Wrong county",county="Montgomery"),sale(address="Oversize",building_sqft=2500),sale(address="Wrong class",property_class="A2")]
    result=select_comps(subject(),rows,LOCATION)
    assert [row["address"] for row in result["sales"]]==["201 Example St","205 Example St","210 Example St"]
    assert result["sales"][0]["price_per_sqft"]==150
    assert all(row["source_url"] for row in result["sales"])
    assert select_comps(subject(),rows,{})["sales"]==[]


def test_policy_boundaries_and_missing_subject_facts():
    rows=[sale(days=180,building_sqft=2400)]
    assert len(select_comps(subject(),rows,LOCATION)["sales"])==1
    assert select_comps({**subject(),"hcad":{}},rows,LOCATION)["sales"]==[]
    assert len(select_comps({**subject(),"hcad":{},"raw":{"building_sqft":"2000","property_class":"A1"}},rows,LOCATION)["sales"])==1
    assert distance_miles(0,0,0,0)==0
    assert distance_miles(0,0,0,1)==pytest.approx(69.09,abs=.02)


@pytest.mark.parametrize("changes",[{"sale_price":float('nan')},{"sale_price":0},{"sale_price":True},{"latitude":91},
    {"sale_status":"active"},{"sale_date":(date.today()+timedelta(days=1)).isoformat()},
    {"source_url":"javascript:alert(1)"},{"source_reference":""},{"reviewed":"yes"}])
def test_invalid_sales_are_rejected(changes):
    with pytest.raises(ValueError):
        sale(**changes)


def test_import_atomic_deduplicated_and_http_roundtrip(local_server):
    row=sale()
    assert request(local_server,"/api/sales",row)[0]==200
    assert request(local_server,"/api/sales",{**row,"sale_price":310000})[0]==200
    assert len(get_sales())==1 and get_sales()[0]["sale_price"]==310000
    with pytest.raises(ValueError):
        save_sales([sale(address="Other"),{**row,"sale_status":"pending"}])
    assert len(get_sales())==1
    assert request(local_server,"/api/sales/import",{"csv":"address\ninvalid\n"})[0]==400
    assert len(get_sales())==1
    assert request(local_server,"/api/sales/delete",{"id":row['id']})[0]==200
    assert not get_sales()


def green_lead():
    uw={"arv_low":350000,"arv_base":370000,"arv_high":400000,"repairs_low":20000,"repairs_expected":30000,"repairs_high":40000,
        "transaction_costs":20000,"buyer_margin":40000,"risk_adjustment":10000,"buyer_price":220000,"contract_price":200000,
        "assignment_costs":2000,"target_assignment_fee":15000,"current_value":280000,"estimated_debt":150000,
        **{key:True for key in CHECK_FIELDS}}
    return {**subject(),"underwriting":uw,"intelligence":{"deal":calculate_deal(uw)},"comps":{"sales":[sale(address=f'{n} Example') for n in (2,3,4)]}}


def test_rating_gray_amber_green_red_and_explanations():
    assert rate_pursuit(subject())["color"]=="gray"
    lead=green_lead()
    rating=rate_pursuit(lead)
    assert rating["color"]=="green" and len(rating["reasons"])>=3
    missing=copy.deepcopy(lead);missing['comps']['sales']=[]
    assert rate_pursuit(missing)["color"]=="amber"
    conflict={**lead,"identity_conflict":True}
    assert rate_pursuit(conflict)["color"]=="amber"
    negative=copy.deepcopy(lead);negative['underwriting']['contract_price']=230000
    negative['intelligence']['deal']=calculate_deal(negative['underwriting'])
    assert rate_pursuit(negative)["color"]=="red"
    lead['underwriting']['payoff_reviewed']=False
    assert rate_pursuit(lead)["color"]=="amber"
