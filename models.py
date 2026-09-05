"""Common record schema every site adapter must emit."""
from dataclasses import dataclass
from datetime import date
from typing import Optional
from markets import COUNTIES, normalize_county

SOURCE_TAX_DELINQUENT = "tax_delinquent"
SOURCE_PROBATE = "probate"
SOURCE_TRUSTEE_SALE = "trustee_sale"
SOURCE_ABSENTEE_OWNER = "absentee_owner"

VALID_SOURCE_TYPES = {
    SOURCE_TAX_DELINQUENT,
    SOURCE_PROBATE,
    SOURCE_TRUSTEE_SALE,
    SOURCE_ABSENTEE_OWNER,
}

VALID_COUNTIES = set(COUNTIES)


@dataclass
class LeadRecord:
    address: str
    owner_name: str
    source_type: str
    county: str
    date_recorded: Optional[date] = None

    # source-specific fields, populated only by the adapters that produce them
    amount_owed: Optional[float] = None
    case_no: Optional[str] = None
    sale_date: Optional[date] = None
    mailing_address: Optional[str] = None

    source_url: Optional[str] = None

    def __post_init__(self):
        self.county = normalize_county(self.county)
        if self.source_type not in VALID_SOURCE_TYPES:
            raise ValueError(f"Unknown source_type: {self.source_type!r}")
        if self.county not in VALID_COUNTIES:
            raise ValueError(f"Unknown county: {self.county!r}")
        # Probate filings identify a deceased owner, not a specific property —
        # match.py joins them onto a property by owner-name after the fact.
        # Every other source type must carry a real property address.
        if self.source_type != SOURCE_PROBATE and (not self.address or not self.address.strip()):
            raise ValueError(f"LeadRecord.address cannot be empty for source_type={self.source_type!r}")
        if not self.owner_name or not self.owner_name.strip():
            raise ValueError("LeadRecord.owner_name cannot be empty")
