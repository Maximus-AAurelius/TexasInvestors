"""Browser smoke test with real source data and isolated writable user state."""
import json
import sys
import threading
import csv
import io
from datetime import date, timedelta
from pathlib import Path
from http.server import ThreadingHTTPServer
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app
import intelligence_db
from playwright.sync_api import sync_playwright, expect


def main():
    qa = app.ROOT / "output" / ("dashboard-qa-" + uuid4().hex[:8])
    qa.mkdir(parents=True)
    intelligence_db.DB_PATH = qa / "intelligence.db"
    app.STATUS_PATH = qa / "status.json"
    server = ThreadingHTTPServer(("127.0.0.1", 0), app.AppHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1050})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}")
            page.locator(".lead").first.wait_for(timeout=60000)
            page.locator(".lead").first.click()
            page.get_by_role("button", name="Help & tour", exact=True).click()
            page.get_by_role("button", name="Start guided tour", exact=True).click()
            for _ in range(11):
                page.get_by_role("button", name="Next", exact=True).click()
            page.get_by_role("button", name="Finish", exact=True).click()
            assert not page.locator('#help-dialog').is_visible()
            from PIL import Image
            fixture_photo = qa / "test-photo.png"
            Image.new("RGB", (800, 400), "#183c31").save(fixture_photo)
            page.get_by_text("Attach a property photo", exact=True).click()
            page.locator('#photo-form input[name="photo"]').set_input_files(str(fixture_photo))
            page.locator('#photo-form input[name="caption"]').fill("QA fixture - not a property photograph")
            page.get_by_role("button", name="Save photo", exact=True).click()
            page.locator('.property-photo img').wait_for()
            page.get_by_text("Set satellite / Street View location", exact=True).click()
            page.locator('#location-form input[name="latitude"]').fill("29.76")
            page.locator('#location-form input[name="longitude"]').fill("-95.36")
            page.get_by_role("button", name="Save location", exact=True).click()
            page.get_by_role("link", name="Satellite view", exact=False).wait_for()
            assert "basemap=satellite" in page.get_by_role("link", name="Satellite view", exact=False).get_attribute("href")
            assert "map_action=pano" in page.get_by_role("link", name="Street View", exact=False).get_attribute("href")
            rows=[]
            for days in (15, 10, 5, 1):
                rows.append({"address":f"{days} QA COMPARABLE ST","county":"Harris","sale_date":(date.today()-timedelta(days=days)).isoformat(),
                             "sale_price":250000,"building_sqft":2311,"property_class":"A1","latitude":29.7601,"longitude":-95.36,
                             "source_url":"https://example.test/qa-only","source_reference":"QA fixture, not real sold data","sale_status":"closed","reviewed":"true"})
            comp_csv=io.StringIO();writer=csv.DictWriter(comp_csv,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            page.get_by_text("Import closed sales CSV", exact=True).click()
            page.locator('#comp-import input[name="csv"]').set_input_files({"name":"qa-comps.csv","mimeType":"text/csv","buffer":comp_csv.getvalue().encode()})
            page.get_by_role("button",name="Import sales",exact=True).click()
            expect(page.locator('.comp-card')).to_have_count(3)
            assert page.locator('.comp-card strong').all_text_contents()==['1 QA COMPARABLE ST','5 QA COMPARABLE ST','10 QA COMPARABLE ST']
            assert page.locator('#pursuit-detail').get_by_text('More evidence needed',exact=True).is_visible()
            page.locator('[name="transaction_costs"]').fill("12000")
            page.locator('[name="buyer_price"]').fill("220000")
            page.locator('[name="contract_price"]').fill("200000")
            page.locator('[name="assignment_costs"]').fill("1500")
            page.locator('[name="assumptions"]').fill('<script>alert("x")</script> QA note')
            page.get_by_role("button", name="Save & calculate").click()
            expect(page.locator("#save-status")).to_contain_text("Saved locally")
            assert "$18,500" in page.locator("#deal-results").inner_text()
            page.reload()
            page.locator(".lead").first.click()
            assert page.locator('[name="transaction_costs"]').input_value() == "12000"
            page.locator('.property-photo img').wait_for()
            expect(page.locator(".property-photo img")).to_have_js_property("complete", True)
            assert page.locator(".property-photo img").evaluate("image => image.naturalWidth > 0")
            page.screenshot(path=str(qa / "desktop.png"), full_page=True)
            page.get_by_role("button", name="Buyer criteria", exact=True).click()
            page.locator('#buyer-form [name="name"]').fill("QA Buyer")
            page.locator('#buyer-form [name="county"]').select_option("Harris")
            page.locator('#buyer-form [name="max_price"]').fill("250000")
            page.get_by_role("button", name="Save buyer", exact=True).click()
            page.locator('#buyer-list strong').filter(has_text="QA Buyer").wait_for()
            page.locator('[data-edit]').first.click()
            page.locator('#buyer-form [name="max_price"]').fill("260000")
            page.get_by_role("button", name="Save buyer", exact=True).click()
            page.get_by_text("Acquisition limit $260,000", exact=False).wait_for()
            page.get_by_role("button", name="Property explorer", exact=True).click()
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            page.screenshot(path=str(qa / "mobile.png"), full_page=True)
            assert not errors, errors
            browser.close()
        print(json.dumps({"result": "PASS", "checks": ["12-step guided tour", "CSV comps import and newest-three order", "visible pursuit explanation", "photo upload and reload", "satellite and Street View links", "real leads", "save and reload costs", "net assignment calculation", "escaped notes", "buyer create and edit", "mobile overflow", "no JavaScript errors"], "artifacts": str(qa)}))
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
