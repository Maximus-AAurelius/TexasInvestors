from site_adapters.manual_import import load_manual_csv


def test_loads_valid_rows(tmp_path):
    csv_path = tmp_path / "leads.csv"
    csv_path.write_text(
        "address,owner_name,source_type,county,date_recorded,amount_owed,case_no,sale_date,mailing_address\n"
        "123 Main St,John Smith,tax_delinquent,Nacogdoches,01/15/2026,542.10,,,999 Oak Ave\n"
    )
    records = load_manual_csv(str(csv_path))
    assert len(records) == 1
    assert records[0].amount_owed == 542.10
    assert records[0].county == "Nacogdoches"


def test_skips_bad_rows_without_crashing(tmp_path):
    csv_path = tmp_path / "leads.csv"
    csv_path.write_text(
        "address,owner_name,source_type,county\n"
        ",John Smith,tax_delinquent,Nacogdoches\n"  # missing required address
        "123 Main St,Jane Doe,tax_delinquent,Nacogdoches\n"
    )
    records = load_manual_csv(str(csv_path))
    assert len(records) == 1
    assert records[0].owner_name == "Jane Doe"
