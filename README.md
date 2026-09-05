# Texas Investors ? local property research edition

## Confirmed markets and strategy

Purchase-contract assignments in **Harris (primary), Fort Bend, Montgomery,
Brazoria, Galveston, Waller, Liberty, Chambers, and Nacogdoches**. The Houston-area
scope follows [H-GAC's eight-county planning area](https://www.h-gac.com/regional-growth-forecast),
with Nacogdoches additionally requested. Use the County filter in the explorer
and select a county when saving buyer criteria. Imports accept these counties;
HCAD enrichment remains strictly Harris-only. Other counties currently need
manual CSV or saved HTML imports, not a connected feed. The Sources & workflow
tab shows coverage and imported counts per county.

## Start here (updated September 4, 2026)

From this folder in PowerShell:

```powershell
.venv\Scripts\python.exe app.py
```

Open **http://127.0.0.1:8765**. You can also run `./Start-TexasInvestors.ps1`.
The app is restricted to this computer. No API keys, paid subscriptions, external
fonts or hosted scripts are required. Source links need internet access. For a
fresh install, use Python 3.10+, create `.venv`, then install `requirements.txt`.
The Playwright browser download is needed only for the existing live adapters
and browser QA, not to browse the dashboard.

- **Property explorer:** search/filter imported leads, review evidence and source
  conflicts, save research status, and export the visible shortlist.
- **Model the deal:** enter ARV/repair ranges and buyer costs. Gross assignment fee
  is total buyer price minus seller contract price. Your net subtracts your own
  assignment costs. Missing values stay unknown. Old `transaction_costs` inputs
  now explicitly mean buyer closing/holding/financing costs; review old scenarios.
- **Buyer criteria:** create, edit and delete local buyer profiles. Matches are
  based on stated criteria and are not verified funds or purchase commitments.
- **Due diligence:** record review checks and document references/dates in notes.
  These are user assertions, not generated legal disclosures or certification.

### Property photos and satellite / Street View

Select a property, then use **Attach a property photo**. JPEG, PNG and WebP
uploads up to 2 MB are validated and stored locally, with a source/caption and
optional photo date. There is one cover photo per property; replacing it replaces
the old photo. Images are resized and original metadata is removed.

Use **Find address in Google Maps** to locate the property. Right-click the
correct location, copy its latitude and longitude, and enter them under
**Set satellite / Street View location**. The saved location enables external
Satellite view and Street View links. No API key is needed. Imagery is viewed
on Google Maps, not embedded in this app, and may be old or unavailable.

Photo and location records are saved in `audit_logs/intelligence.db`; include it
in backups. See [Product priorities](docs/product-roadmap.md) for the comparison
and recommended next work.

### Add records without a paid service

The app reads CSV files directly in the project root, `output`, and `data/imports`.
It no longer recursively scans test folders or arbitrary nested directories.
Use `address,owner_name,county,source_type` columns. Source types are
`absentee_owner`, `probate`, `trustee_sale`, and `tax_delinquent`; preserve
`source_url`, `date_recorded`, `case_no`, and `retrieved_at` when available.

For the full existing pipeline without network requests:

```powershell
.venv\Scripts\python.exe run.py --offline --manual-csv data\imports\leads.csv
```

### Optional Scrapling integration

?Scrapley? was interpreted provisionally as [D4Vinci/Scrapling](https://github.com/D4Vinci/Scrapling),
not [scrapy/scrapely](https://github.com/scrapy/scrapely). These are different libraries.
The optional parser is pinned to 0.4.15 and was installed in this workspace.

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-scraping.txt
.venv\Scripts\python.exe scripts\import_saved_html.py saved-records.html --county Harris --source-type absentee_owner --source-url https://example.org/record-source --table "#records" --out data\imports\reviewed-records.csv
```

Replace the example URL with the actual source reference. This command parses a
saved HTML table; it never fetches the URL or executes scripts. Recognized headers:
Address / Property Address, Owner / Owner Name, Mailing Address, Case Number.
Use a specific CSS table selector if multiple tables match. Unsupported layouts,
ambiguous tables, empty results and invalid required fields fail explicitly.
Review every imported identity. It does not OCR scanned notices or repair the
existing foreclosure adapter's pagination limitation.

### Market data lookup (RentCast + HCAD, one address at a time)

Every property's detail view has a **Look up market data** button. It calls
two connectors for that one address and saves the result to
`audit_logs/intelligence.db`'s `property_lookups` table (upserted, so
running it again on the same address updates that one row instead of
duplicating it):

- **RentCast** (`rentcast.py`, `get_comps(address)`) — an automated value
  estimate and comparable sales/listings from RentCast's `/avm/value` API.
  Get a free key at https://app.rentcast.io/app/api and set it before
  starting the app:
  ```powershell
  $env:RENTCAST_API_KEY = "your-key-here"        # this PowerShell session only
  setx RENTCAST_API_KEY "your-key-here"           # persists across sessions
  ```
  Without a key, the button still runs the HCAD half and reports the
  missing-key error alongside whatever HCAD found — one connector failing
  never blocks the other.
- **HCAD** (`hcad_lookup.py`, `lookup_hcad(address)`) — Harris County only.
  Checks the already-downloaded bulk roll (`data/hcad/real_acct.txt`) first
  for the full field set (building sqft, year improved, lot acreage,
  ownership-change date); if that file is missing or has no match, it falls
  back to a live, unauthenticated ArcGIS query against HCAD's own public GIS
  map service, which needs no download and stays current. A live Playwright
  script against HCAD's actual account-search page (`search.hcad.org`) was
  investigated first and found to be behind a Cloudflare bot challenge on
  every request — the same category of explicit anti-bot gate this project
  already declines to script around for the tax-delinquent CAPTCHA (see
  `site_adapters/harris_tax.py`). See `hcad_lookup.py`'s module docstring for
  the full investigation.

Command line, for scripting or bulk one-off checks outside the dashboard:
```powershell
.venv\Scripts\python.exe lookup.py "10303 Greencreek Dr" --county Harris
.venv\Scripts\python.exe lookup.py "10303 Greencreek Dr" --no-rentcast   # HCAD only, no API key needed
```

This is an automated estimate, not an appraisal or verified sale — the
dashboard labels it that way and it does not feed into the manually-entered
underwriting numbers automatically.

### Data and release boundaries

User underwriting and buyer profiles: `audit_logs/intelligence.db`.
Statuses: `output/lead_status.json`. HCAD raw data: `data/hcad`.
Back up these files and original CSV imports while the app is stopped. They contain
local personal/business information and are not encrypted by this application.
Existing historical CSVs are preserved; regenerate or review older inferred
matches because the current matcher rejects ties that older versions accepted.

This is a usable local research edition, not a hosted multi-user release. The
foreclosure adapter remains incomplete; tax/Nacogdoches imports remain manual.
No property is automatically certified as high-equity or profitable. Before
commercial hosting, add authentication/authorization, a production HTTP stack,
backup/restore verification, monitoring, dependency audits and data-rights review.

Research: [Property sourcing and product strategy](docs/Texas-Investors-Research.docx).
Implementation notes: [Completion plan](docs/implementation-plan.md).

### Verification

```powershell
.venv\Scripts\python.exe -m pytest -q --basetemp output/test-run-new -p no:cacheprovider
.venv\Scripts\python.exe scripts\verify_dashboard.py
node --check web/app.js
```

Use a new empty basetemp path for each test run. Browser verification uses isolated
user-state storage under `output/dashboard-qa-*`, with real source CSVs. Optional
Scrapling tests skip if its extra requirements are absent.

---

## Existing pipeline documentation

The historical implementation notes below describe the county pipeline. The
local dashboard instructions and boundaries above take precedence.

# TexasInvestors — TX Distress-Lead Pipeline (Harris & Nacogdoches County)

Pulls public-record leads from Texas county government sites, matches
the same property across sources, scores it by how many distress
categories it hits, and outputs a ranked, editable Word document.

Every source here is a public government record (county appraisal
district / county clerk). This project does not scrape Zillow, Redfin,
or Realtor.com anywhere.

## Setup (PowerShell, from this folder)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

## Running it

```powershell
python run.py                                # default 30-day lookback, headless
python run.py --lookback-days 45             # wider window for probate/trustee-sale
python run.py --headed                       # watch the browser instead of headless
python run.py --manual-csv leads.csv         # add manually-collected records (repeatable flag)
python run.py --out output\my_leads.docx

# free bulk absentee-owner data (see "HCAD bulk data" section below)
python scripts\fetch_hcad_bulk_data.py 2026
python scripts\hcad_top_absentee_leads.py
python run.py --manual-csv output\hcad_top_absentee_leads.csv

# one-time: build the owner-name index that fills in missing addresses
python scripts\build_hcad_owner_index.py
python run.py --no-enrich                    # skip that fill-in pass
```

Each run writes two files: `leads_<timestamp>.docx` (the readable report)
and `leads_<timestamp>.csv` beside it, carrying every field including the
ones the .docx table has no room for — parcel id, mailing address, match
confidence, year built, building sqft, source URLs. The dashboard reads
the .csv.

## Local dashboard

Run `python app.py` and open `http://127.0.0.1:8765` on this computer.
The current edition uses individual map lookup links, not bulk geocoding.

The structured profile and initial signal weights live in
`intelligence.py` and `knowledge\scoring_config.json`. Edit the JSON weights
to test a different evidence policy; unsupported economic scores remain
`UNKNOWN` until verified valuation, debt, repair, and buyer data are available.

When `data\hcad\real_acct.txt` is present, the app joins matching lead
addresses to HCAD records and caches the extracted profiles in
`output\hcad_lead_profiles.json`. HCAD market value is displayed as an
appraisal-source fact, not as an independent current-market or ARV estimate.

The app also maintains a local intelligence history database at
`audit_logs\intelligence.db`. It stores canonical properties, source-file
provenance, current profiles, changed score snapshots, and lead status actions.
The database is local-only for now and is safe to replace with Supabase after
the property schema and valuation workflow are settled.

Each property detail view now includes a **Manual underwriting** panel. Enter
current value, ARV low/base/high, repairs low/expected/high, estimated debt,
buyer price, contract price, and assumptions. These values are stored locally
in `audit_logs\intelligence.db` as underwriting inputs and are not presented as
verified public-record facts.

Output lands in `output\leads_<timestamp>.docx` — sorted by distress
score descending, with Address / Owner / County / Case No / Market Value
/ Score / Sources Hit / Addr. Source columns, on a landscape page. It's a
normal Word table: open it and edit freely (add a Notes column, mark
contacted, delete rows). The **Addr. Source** column says whether an
address came off a county filing or was derived from the HCAD roll, and
at what confidence — see "Filling in missing addresses" below.

Every run also logs to `audit_logs\audit.db` (SQLite) — timestamp,
per-source record counts, and matched-lead count — so drift over time
is visible without manual re-checking.

## Current status of each source (verified live, 2026-09-02/03)

| Source | County | Status |
|---|---|---|
| Probate filings | Harris | **Working**, part of `run.py`. `cclerk.hctx.net` CourtSearch.aspx, confirmed field ids, real 199-record pull over 30 days tested live. |
| Foreclosure (trustee-sale) postings | Harris | **Working search, gated pagination.** See below — root cause found (login-only pagination), fix in progress pending a free account. |
| Absentee owner | Harris | **Working, free, full-county.** HCAD's public bulk data export — see "HCAD bulk data" below. This replaced the earlier plan of deriving it from the CAPTCHA-gated tax-delinquent search. |
| Tax delinquent (dollar amounts owed) | Harris | **Not automatable — reCAPTCHA-gated.** `caopay.harriscountytx.gov` has a real Google reCAPTCHA on its search form. This project does not attempt to solve or bypass CAPTCHAs. Use `--manual-csv` instead. |
| Everything | Nacogdoches | **Out of scope for now.** Every Nacogdoches source hits a robots.txt wall — see below. Project is Harris-County-only until that's revisited. |

## HCAD bulk data — free, full-county absentee-owner leads

Harris Central Appraisal District publishes its entire property database
as a free public download (confirmed: `hcad.org`'s own page describes it
as meant to be "imported into user databases"; `download.hcad.org`,
where the actual files live, has no robots.txt at all). No CAPTCHA, no
per-request scraping — one ~200MB zip covering all ~1.6M Harris County
parcels.

```powershell
python scripts\fetch_hcad_bulk_data.py 2026    # downloads + unzips to data\hcad\ (gitignored, ~1.3GB)
python scripts\hcad_top_absentee_leads.py      # ranks down to output\hcad_top_absentee_leads.csv
python run.py --manual-csv output\hcad_top_absentee_leads.csv
```

`hcad_top_absentee_leads.py` filters to residential parcels (state
class A1-A4), flags absentee ownership by fuzzy-comparing the situs
street address against the mailing street address (same logic
`match.py` uses elsewhere), drops sub-$30k parcels (slivers/easements),
then ranks by years since last ownership change (a proxy for "landlord
who's had enough" / "inherited and never dealt with") plus a bonus for
an out-of-state mailing address, and writes the top 100. All of this is
adjustable — see `RESIDENTIAL_CLASSES`, `MIN_MARKET_VALUE`, `TOP_N`, and
`WEIGHTS` at the top of the script.

**Re-run `fetch_hcad_bulk_data.py` every month or so** (HCAD updates the
roll periodically) — don't re-download on every pipeline run, it's a
200MB file covering the whole county, not a per-search lookup.

A real bug was caught and fixed while building this: the first version
compared *full* addresses (street + city + state + zip) with exact
string equality and flagged 72% of all residential parcels as absentee
— city/zip formatting noise (zip+4 vs zip5, etc.) was drowning out the
real signal. Fixed by comparing just the street-address line with fuzzy
matching (same threshold as everywhere else). Verified against the raw
data by hand afterward — see git history / code comments in the script.

### Harris trustee-sale: found the right page, pagination still needs work

Originally this used `RP.aspx` (the general real-property index) and got stuck hunting for an undocumented "Instrument Type" code for trustee-sale notices — six plausible codes were tried live and all came back empty (see git history / earlier README revisions if curious). The real fix: Harris County Clerk runs a **separate, dedicated Foreclosures search module**, `FRCL_R.aspx`, that's pre-scoped to foreclosure postings — no instrument code needed at all. Confirmed live: a search for October 2026 sale dates returned "553 Row(s) Found," with sale dates landing on 10/06/2026 — the first Tuesday of the month, exactly matching Tex. Prop. Code §51.002.

Two real limitations, both documented in `site_adapters/harris_trustee_sale.py`:

1. **No address or owner name in the index** — only Doc ID, Sale Date, File Date, and page count. Opening a Doc ID says "Select Document ID to View Image" — the actual notice is a scanned document image, not searchable text. Getting an address out of it would need OCR (and the site's login prompt suggests image viewing may require a paid account) — real scope beyond "keep it free." Because of this, these postings **do not** feed into `match.py` / the main `.docx` report (there's no address or owner to join on). Pull them separately:
   ```powershell
   python scripts\pull_foreclosure_postings.py 2026 10
   ```
   This writes `output\harris_foreclosure_postings_<year>_<month>.csv` — Doc ID, Sale Date, File Date, page count — for manual review or manual document lookup.
2. **Pagination is gated behind a login.** Root cause confirmed 2026-09-03: `__doPostBack` and the `__EVENTTARGET`/`__EVENTARGUMENT` hidden fields it depends on are completely absent from the page for anonymous visitors — the county's server never sends the pagination JavaScript at all (confirmed in both headless and headed Chromium, so it's not an automation quirk). The page shows a "LOG IN | NEW USER" prompt at the top, which strongly suggests page 1 is free to browse but full pagination requires a registered account. Net effect: you currently only get page 1 (~38 rows) even when the site reports hundreds more. Real, correctly-parsed data, just incomplete. **Next step**: register a free account at `cclerk.hctx.net` and test whether logging in unlocks the pagination JS before writing more code here.

Also worth knowing for later: this data source's Doc ID index has no address at all (unlike RP.aspx's legal-description field), so even once OCR/full-page-count is solved, cross-referencing to other sources will need either the scanned document's contents or a separate parcel lookup — there's no shortcut here.

### Nacogdoches County: out of scope for now, here's why it's hard

Every Nacogdoches source hits a robots.txt wall:

- **`esearch.nacocad.org`** (property/tax search) has its **own**
  robots.txt — separate from, and stricter than, the parent
  `nacocad.org` domain — that disallows both `/Search/` and
  `/Property/`. That blocks the search results page *and* the
  individual property detail pages (which is where mailing address and
  per-year "Amount Due" actually live — the results grid itself has
  neither). This was caught mid-build by this project's own robots.txt
  enforcement in `site_adapters/base.py`, after a handful of
  reconnaissance queries had already run against it — those queries
  happened before that subdomain's own robots.txt had been checked
  (only the parent domain had been, which is narrower). Worth knowing
  if anyone asks about traffic to that site.
- **`nacogdoches.tx.publicsearch.us`** (probate, trustee-sale — same
  vendor platform used for both) disallows `/` entirely.
- No free public delinquent-tax roll exists for Nacogdoches County
  otherwise — the CAD is a pure ownership/appraisal database, and the
  only alternatives found were a paid subscription service (TaxNetUSA)
  or calling the Tax Assessor-Collector directly, (936) 560-7767.

Use `--manual-csv` for anything from Nacogdoches: look records up
yourself in a browser (a human doing that isn't a robots.txt concern —
robots.txt governs automated crawlers) and feed them into the pipeline
via `site_adapters/manual_import.py`'s CSV format. See the header
comment in that file for columns.

### Harris tax-delinquent: reCAPTCHA

`caopay.harriscountytx.gov`'s search form has a hidden Google reCAPTCHA
token field (confirmed via live DOM inspection). This project treats
that the same way as a robots.txt block: it's the site's explicit
anti-bot mechanism, not an incidental obstacle, and isn't something to
script around. Use `--manual-csv` for this source too, or ask the
County Attorney's office about a bulk data-sharing arrangement.

## Mandatory testing (do this before trusting the output)

1. **Per-adapter consistency** — run the same adapter 3x live, counts
   should match within ~5%:
   ```powershell
   python scripts\check_adapter_consistency.py harris_probate
   ```
2. **Hand-verify 3 records** — every time you touch an adapter, open
   the live county site yourself and manually check 3 records the
   adapter returned actually match what's on the site.
3. **Pipeline determinism** — `match.py` has no randomness; running it
   3x on the same input must give identical output:
   ```powershell
   python scripts\check_pipeline_determinism.py path\to\dataset.json
   ```
4. **Unit tests** (fast, no network, run these constantly):
   ```powershell
   pytest
   ```

## Filling in missing addresses (HCAD owner index)

Probate filings name a **deceased owner, never a property** — the county
docket has no address field at all. `match.py` can attach a probate case
to a property only when that same owner also turns up in a source that
does carry an address. Everything else printed `(address unknown — see
case_no)`, which was the overwhelming majority of probate leads, and the
.docx did not even have a `case_no` column to go look up. Both fixed:

```powershell
python scripts\build_hcad_owner_index.py     # a few minutes, ~700MB .db, gitignored
```

That builds `data\hcad\owner_index.db` from the bulk roll you already
downloaded — an owner-name → property index over every Harris County
parcel and **every** owner name line on it, not just the primary, since a
decedent is often the second name on a joint deed. `enrich.py` then runs
after matching: for any lead with no address it looks the owner up and
fills in the address, and for every lead it backfills parcel id, mailing
address, market value, year built and building size.

Guard rails, because this **derives** an address rather than reading one
off a filing:

- Scored by `name_match.py`, not raw `fuzz.ratio` — see the next section.
- Threshold is 93, higher than `match.py`'s 90, and a match must also
  agree on at least two whole name tokens (surname *and* given name).
- An owner resolving to more than 3 equally-good parcels is left unknown
  rather than guessing — that is a portfolio landlord or a common name.
- Harris County only. The HCAD roll does not cover Nacogdoches, so those
  leads pass through untouched instead of matching the wrong county's
  properties.
- Parcels HCAD parks at street number 0 ("0 IN HARRIS COUNTY") are
  excluded — nobody can drive to those.
- Every derived address is labelled in the report's **Addr. Source**
  column as `HCAD owner match (94%)` against `County filing` for a real
  one, so the two are never confused. Verify before you door-knock.

The index is optional — without it the pipeline runs exactly as before
and prints a note telling you what to run.

## A note on owner-name matching precision

`match.py` joins probate records onto a property by fuzzy-matching
owner names (see its module docstring). This deliberately uses plain
`fuzz.ratio` on the pre-sorted normalized name, not `fuzz.WRatio`.
Found live 2026-09-02: WRatio gives a big score boost for *any* shared
word, which works fine for street addresses (names rarely collide) but
is wrong for people — "DAVIS FARRAR M" and "MARGARET ELIZABETH DAVIS
MEYERS" are unrelated people who only share the surname "DAVIS," and
WRatio scored that pair 85.5 (above the threshold at the time).
`fuzz.ratio` scored the same pair 53.3. If you're extending the
owner-matching logic, keep this precision-over-recall bias — a wrong
join here means falsely telling the investor a stranger's estate
belongs to someone else's property, which is worse than a real match
landing in the "address unknown" bucket instead.

**Against the HCAD roll specifically, whole-string `fuzz.ratio` is the
wrong tool**, and `name_match.py` exists to replace it there. The
appraisal district abbreviates middle names to initials, so correct pairs
score far too low to act on: `ROWLAND CLYDE FREEMAN` vs HCAD's `FREEMAN
ROWLAND C` scored 89.5, and `JOSEPH WADE GIACONE` vs `GIACONE JOSEPH W &
BEVERLY` scored 74.4 — while the *wrong* answer `WADE JOSEPH A JR` beat
it at 81.2 purely on two shared whole words. `name_match.py` compares
token to token instead: identical tokens score 100, a single letter
matching a word's first letter scores 90 (and 0 if it does not — `GEAN`
is not a match for `C`), anything else falls back to `fuzz.ratio` on that
pair, and pairing is greedy over all pairs by score rather than in token
order, since token order is meaningless once `normalize_owner_name` has
sorted alphabetically.

**Three bugs found by testing against the real roll rather than
fixtures**, all of which fixtures would have hidden:

1. The index originally deleted any token appearing more than 20,000
   times, to bound candidate lookups. That pruned `MARIA` to zero rows,
   so `CASTILLO MARIA SALOME` shared only one indexed token with
   `CASTILLO MARIA C`, never reached the two-shared-token bar, and
   returned *no candidates at all* despite the owner sitting right there
   in the roll. The index now keeps every token and records counts in
   `owner_token_freq`; lookups bound the work by seeking a name's
   **rarest** tokens first (`SALOME` appears 73 times, `MARIA` tens of
   thousands), which costs nothing in recall.
2. An unpaired whole word in the candidate name only cost 3 points, which
   let `ADELAIDA GOMEZ PEREZ` match `GOMEZ GUSTAVO A PEREZ` at 93.7 — the
   `A` paired with `ADELAIDA` by coincidence while the real given name
   `GUSTAVO` sat unpaired — and `DAVID RODRIGUEZ LOPEZ` match `RODRIGUEZ
   DARWIN DAVID LOPEZ` at 97.0. An unpaired *word* now costs 12; an
   unpaired *initial* costs nothing, since HCAD adds initials the filing
   does not have.
3. That penalty would have broken genuine joint deeds, so
   `build_hcad_owner_index.py` splits them on `&` first: `GIACONE JOSEPH
   W & BEVERLY` is indexed as `GIACONE JOSEPH W` **and** `GIACONE
   BEVERLY` (plus the original line), so each spouse is reachable on
   their own name instead of carrying the other as an unexplained token.

## Anti-detection posture

These are county government sites, not commercial real-estate sites
behind Cloudflare/DataDome — they don't need heavy stealth tooling.
Each adapter:
- uses an identifiable User-Agent string (`TXLeadResearchBot/1.0` with
  a contact email) rather than spoofing a real browser
- waits 2–5s (randomized) between requests, always — not just when
  blocking is detected, since the real risk here is a human county IT
  admin noticing unusual traffic, not bot-detection algorithms
- checks robots.txt via `urllib.robotparser` **per subdomain** before
  every navigation, and fails closed if robots.txt can't be fetched
  (see the Nacogdoches note above for why per-subdomain matters — a
  parent domain's robots.txt doesn't cover its subdomains)

The spec originally called for `pw-stealth-enhanced`. It exists on
PyPI but has a single v0.1.0 release and ~3 GitHub stars — it fails
the "avoid unproven packages" bar. It's intentionally not a dependency
here. If a specific site does start blocking requests, reach for the
more established `playwright-stealth` first before this one.

## Project structure

```
models.py                    common LeadRecord schema
normalize.py                 address/owner-name normalization (deterministic)
match.py                     cross-source fuzzy matching + scoring (deterministic)
name_match.py                initial-aware person-name scoring (deterministic)
hcad_owner_index.py          owner-name -> property lookup over the HCAD roll
enrich.py                    fills missing addresses + HCAD property facts, post-match
docgen.py                    .docx report generator + full-field .csv sidecar
audit_log.py                 SQLite run-history log
run.py                       orchestrator (ties everything together)
site_adapters/
  base.py                    shared UA/robots.txt/rate-limit plumbing
  _grid_helpers.py           text/DOM parsers for the cclerk.hctx.net grids
  harris_probate.py          working, part of run.py
  harris_trustee_sale.py     Foreclosures postings (Doc ID/dates only) — separate script, not run.py; pagination gated behind login
  harris_tax.py              reCAPTCHA-gated, not wired into run.py — reference only
  absentee_owner.py          derivation from live tax_delinquent records (currently only reachable via --manual-csv)
  manual_import.py           CSV import for robots.txt-blocked / CAPTCHA-gated sources
data/hcad/                   HCAD bulk download cache (gitignored, ~1.3GB) — see fetch_hcad_bulk_data.py
scripts/
  fetch_hcad_bulk_data.py
  build_hcad_owner_index.py      builds the owner-name index (gitignored, ~700MB)
  hcad_top_absentee_leads.py
  pull_foreclosure_postings.py
  check_adapter_consistency.py
  check_pipeline_determinism.py
  pull_foreclosure_postings.py   standalone: python pull_foreclosure_postings.py <year> <month>
tests/                       pytest unit tests (normalize, match, name_match, enrich, docgen, manual_import)
audit_logs/audit.db          created on first run
output/                      generated .docx reports, created on first run
```

## Adding a new county adapter

1. Research the county's actual data source first — appraisal district
   site for tax rolls, county clerk for probate/trustee-sale — and
   fetch **that exact subdomain's** `robots.txt` before writing any
   code (a parent domain's robots.txt doesn't cover its subdomains —
   this bit the Nacogdoches build, see above). If it disallows the path
   you need, stop: use `manual_import.py` instead, or get explicit
   written permission before automating it.
2. Open the real site with Playwright once and inspect it directly
   (`page.query_selector_all`, a screenshot, `page.inner_text("body")`)
   rather than guessing field names — several of this project's first-
   draft adapters had wrong selectors purely from guessing, and a live
   look caught it immediately. Watch for CAPTCHAs (hidden `recaptcha`
   token fields, `g-recaptcha-response`) — if you find one, stop, same
   as a robots.txt block.
3. Create `site_adapters/<county>_<source_type>.py`. Subclass
   `BaseAdapter` from `site_adapters/base.py`. Set `source_type` (one
   of the constants in `models.py`), `county`, and `base_url`.
4. Implement `fetch_raw(self, page)` — navigate and return a list of
   raw field dicts. Call `self._jitter_sleep()` between requests and
   `self._require_allowed(url)` before navigating anywhere beyond
   `base_url`. If the site renders a normal `<table>`, use
   `_grid_helpers.scrape_grid()`; if it's a Telerik-style grid that's
   messy in the DOM but clean in `page.inner_text("body")` (check both
   before picking), write a text-based parser like `parse_grid_text()`
   or `parse_rp_records()` instead.
5. Implement `to_record(self, row)` — map the raw dict into a
   `LeadRecord`. Every source type except `probate` must set a real
   `address` (probate filings identify an owner, not a property;
   `match.py` joins them onto a property by owner-name afterward). If
   a row lacks a usable address, `raise ValueError(...)` rather than
   inventing a placeholder — `base.run()` catches it and skips that row
   (a placeholder like `""` or a constant string will falsely
   fuzzy-cluster every such row together, since `match.py`'s blocking
   key treats identical/empty address strings as the same property).
6. Add the adapter to `run.py`'s `adapters` list.
7. Run the mandatory testing steps above before trusting its output.
