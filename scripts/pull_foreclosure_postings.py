"""Pull Harris County foreclosure (Notice of Trustee's Sale) postings
for one year/month and save them as a CSV for manual review.

Not part of run.py / the LeadRecord pipeline — see
site_adapters/harris_trustee_sale.py's module docstring for why (no
address/owner in the index, so no join key for match.py).

Usage (PowerShell, from the project root):
    python scripts\\pull_foreclosure_postings.py 2026 10

KNOWN LIMITATION: currently only returns page 1 of results (~38 rows)
even when more exist — pagination on this specific grid isn't working
yet (see the adapter's docstring for what's been tried).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from site_adapters.harris_trustee_sale import HarrisForeclosurePostingsAdapter, save_postings_csv

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def main():
    if len(sys.argv) != 3:
        print("Usage: python pull_foreclosure_postings.py <year> <month>")
        sys.exit(1)
    year, month = int(sys.argv[1]), int(sys.argv[2])

    adapter = HarrisForeclosurePostingsAdapter(year=year, month=month, headless=True)
    postings = adapter.fetch_postings()
    print(f"{len(postings)} postings found")

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"harris_foreclosure_postings_{year}_{month:02d}.csv"
    save_postings_csv(postings, str(out_path))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
