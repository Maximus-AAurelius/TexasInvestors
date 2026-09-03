"""Download HCAD's free public bulk property-data export and extract the
two files this project uses (real_acct.txt, owners.txt) into data/hcad/.

Source: https://download.hcad.org/data/CAMA/<year>/Real_acct_owner.zip
Confirmed 2026-09-02: download.hcad.org has no robots.txt (404 — treated
as unrestricted per convention), and the parent hcad.org page explicitly
describes this as a public download meant to be "imported into user
databases." ~200MB zipped, ~1.28GB unzipped — this is the whole Harris
County appraisal roll (~1.6M parcels), not a per-request lookup, so this
script caches it to disk rather than re-downloading on every run. HCAD
updates this periodically (observed "Last Updated" date on their page);
re-run this script every month or so, not more.

Usage (PowerShell, from the project root):
    python scripts\\fetch_hcad_bulk_data.py 2026
"""
import sys
import urllib.request
import zipfile
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "hcad"
USER_AGENT = (
    "TXLeadResearchBot/1.0 (+contact: travispeters226@gmail.com; "
    "public-record lead research; respects robots.txt)"
)
NEEDED_MEMBERS = ["real_acct.txt", "owners.txt"]


def main():
    year = sys.argv[1] if len(sys.argv) > 1 else "2026"
    url = f"https://download.hcad.org/data/CAMA/{year}/Real_acct_owner.zip"

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DATA_DIR / "Real_acct_owner.zip"

    print(f"Downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp, open(zip_path, "wb") as f:
        total = int(resp.headers.get("Content-Length", 0))
        written = 0
        while chunk := resp.read(1024 * 1024):
            f.write(chunk)
            written += len(chunk)
            if total:
                print(f"\r  {written / total:.0%}", end="", flush=True)
    print(f"\nDownloaded {written / 1024 / 1024:.0f} MB")

    print("Extracting real_acct.txt and owners.txt ...")
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(DATA_DIR, members=NEEDED_MEMBERS)

    print(f"Done — files in {DATA_DIR}")


if __name__ == "__main__":
    main()
