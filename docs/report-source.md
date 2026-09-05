# Texas Investors: free local product and property-sourcing strategy

Audience: Travis, owner/operator. Prepared September 4, 2026.

## The recommended approach

Build a buyer-first property research workspace around HCAD's public bulk data, narrow the shortlist by property fit, and verify the economics before pursuing an assignment. Start locally without paid APIs. The practical objective is to identify which property deserves your next research hour; a public-record distress score cannot establish a profitable transaction.

Confirmed scope: assignment of purchase contracts in Harris (primary), Fort Bend, Montgomery, Brazoria, Galveston, Waller, Liberty, Chambers, and Nacogdoches. The app supports county filtering and imports for all nine markets; HCAD enrichment stays Harris-only and the other counties currently require manual records. Existing buyer access and the precise scraper name remain unconfirmed.

## Where free data helps, and where it stops

HCAD explicitly provides downloadable data for import into applications. Use the official bulk files as the property backbone and retain parcel identifiers, source dates and address context. Reuse local files and avoid repeated full downloads. Import permission was verified; unrestricted commercial redistribution rights were not established. [HCAD Public Data](https://hcad.org/hcad-online-services/pdata/)

HCAD's property download catalog describes owner, mailing, legal-description and building datasets. The download page's dynamic rendering limited direct inspection of the current file list during research. The repository already contains HCAD download/index tooling and local data, but this work did not redownload or independently certify the entire current county roll. [HCAD Property Downloads](https://hcad.org/pdata/pdata-property-downloads.html/)

Texas lacks mandatory sales-price disclosure, according to HCAD's 2024 mass appraisal report. Consequently, a complete, free sold-comparables feed cannot be assumed from public county data. Obtain supported comparable sales from permitted sources or a local professional and record adjustments and dates. This structural limitation is supported by a historical official report, not a claim about a newly tested feed. [HCAD 2024 Mass Appraisal Report](https://hcad.org/assets/uploads/pdf/Reports/MAR-2024-Final.pdf)

HCAD describes appraisal methods including replacement cost less depreciation plus land value. Treat its appraisal as a tax-source observation; do not automatically use it as after-repair value. Current debt, repairs, condition and buyer demand require separate evidence. [HCAD Cost Approach](https://hcad.org/hcad-resources/hcad-residential-property/cost-approach-to-value-for-single-family-property)

The Harris County Clerk provides free unofficial watermarked document viewing to registered users, while bulk index/image files and daily FTP are separate paid offerings. This supports manual document verification in the free edition; it does not establish a free unrestricted automated bulk feed. A login requirement does not necessarily mean individual viewing is paid. [Clerk Public Records](https://cclerk.hctx.net/Applications/WebSearch/PublicRecords.aspx)

The dedicated foreclosure portal exposes trustee-notice records. A posting is an event to investigate, not proof that a sale occurred or that a default remains unresolved. The repository's foreclosure adapter documents incomplete pagination and is not a comprehensive live lead source. This limitation remains open. [Clerk Foreclosure Search](https://cclerk.hctx.net/Applications/websearch/FRCL_R.aspx)

Harris County tax-sale guidance warns that listings can be incomplete, sales canceled, title unwarranted and full payment required immediately. My recommendation is to use auction-related information as a research signal rather than making auction purchases the initial no-capital assignment strategy. [Harris County Tax Sales](https://www.hctax.net/Property/TaxSales)

No free countywide delinquency export was verified. The Tax Office accepts existing-record requests, but charges can apply and the agency need not create a new report. Start with reviewed imports; ask about an existing machine-readable dataset if tax delinquency becomes a core lane. [Tax Office Public Information](https://www.hctax.net/About/PublicInfoAct)

## How to find a workable assignment candidate

The following workflow is a product recommendation derived from the evidence, not a prediction model validated against completed deals.

1. Record actual buyer criteria first: county, property class, acquisition budget, repair tolerance and confirmation date. Choose a small area and property type with buyers you can reach.
2. Filter parcels by property fit, then investigate mailing differences, long ownership and current filing evidence. These are possible research signals; they do not prove willingness to sell or high equity.
3. Resolve parcel and owner identity. Same-name probate records and shared situs addresses can be ambiguous. Leave ties unresolved instead of choosing the most valuable parcel.
4. Verify comparable sales and repair ranges. Keep unknowns blank and document the source and date of each material assumption.
5. Verify current payoff, liens, ownership authority and title with appropriate professionals. An old recorded loan amount is not a current payoff; no visible mortgage is not proof of debt-free ownership.
6. Compare conservative, base and optimistic economics, then confirm a buyer's actual interest, funds and acceptance of an assignment.

Historical deed purchasers can help prospect for buyers, but the Clerk's grantee search also includes mortgagees, creditors and other roles. Inspect instrument type and the actual deed before labeling a party a purchaser. Historical purchases do not establish current funds or willingness to buy. [Clerk Search Help](https://cclerk.hctx.net/applications/websearch/help.aspx)

The app uses these transparent calculations: buyer acquisition ceiling = ARV minus repairs, buyer closing/holding/financing costs, target profit and contingency. Seller price ceiling = buyer ceiling minus target gross assignment fee. Gross assignment fee = total buyer price minus seller contract price. Your estimated net = gross fee minus your assignment costs. Estimated equity = entered current value minus entered debt, before selling costs or omitted liens. Missing inputs stay unknown.

## Texas transaction and product boundaries

TREC section 535.6 distinguishes selling a contractual interest from brokerage. Qualifying assignments require written disclosure of the nature of the equitable interest to sellers and potential buyers and must not be used to engage in brokerage. The app records separate review checkboxes and notes; these do not create the required documents or certify compliance. Sections 535.4 and 535.20 also matter to compensated property-finding and referral activities. Obtain review of the actual contracts and business model before transaction marketing. [TREC Rules](https://www.trec.texas.gov/agency-information/rules-and-laws/trec-rules)

The seller-disclosure obligation is not merely a proposed rule: SB1577 amended the statutory framework effective January 1, 2024. Older summaries that discuss only a buyer disclosure are incomplete. The enacted text and current TREC page corroborate this conclusion; direct current statute pages were not fully accessible in this research. [SB1577 Enrolled Text](https://capitol.texas.gov/tlodocs/88R/billtext/html/SB01577F.htm)

The first edition should record contact activity rather than automatically send cold texts or emails. Texas SOS currently states that prior-consent consumer texts do not require Chapter 302 registration under the referenced litigation agreement; that narrow statement is not blanket permission for unsolicited outreach. Federal outreach rules and the specifics of property-acquisition solicitations were not fully analyzed here. [Texas SOS Solicitation FAQ](https://www.sos.state.tx.us/statdoc/faqs3400.shtml)

A future business reselling enriched contact data may raise privacy and data-broker questions. OAG describes data-broker registration, notice and security duties along with exemptions. Classification depends on the eventual data and revenue model. Keep sensitive personal profiling out of property ranking and separate software subscriptions from any later data-resale proposal. [Texas OAG Data Broker Act](https://www.texasattorneygeneral.gov/consumer-protection/file-consumer-complaint/consumer-privacy-rights/texas-data-broker-act)

## Scrapling and the implementation delivered

Scrapling and Scrapely are different projects. Scrapling was selected provisionally because the requested name was ambiguous. Its official repository supports a lightweight parser installation, with fetchers available separately. Version 0.4.15 was installed and an optional requirements file pins it. The integration converts saved HTML tables into CSV with source references; it makes no requests and disables adaptive relocation so layout ambiguity fails explicitly. Existing browser adapters remain separate. [Scrapling Repository](https://github.com/D4Vinci/Scrapling/blob/main/README.md) [Scrapely Repository](https://github.com/scrapy/scrapely)

Scrapling's BSD-3-Clause license permits redistribution and modification subject to notices and non-endorsement conditions. That software license does not grant rights to redistribute scraped property or contact datasets. Keep third-party notices with packaged releases and review dependencies and source terms before selling. [Scrapling License](https://github.com/D4Vinci/Scrapling/blob/main/LICENSE)

The implementation adds a local dashboard with property filters, visible-list CSV export, buyer criteria create/edit/delete, scenario calculations, durable assumptions and due-diligence notes. Security changes restrict the server to loopback, validate Host and Origin, require a custom JSON write header, bound request sizes, reject non-finite numbers and prevent static-file traversal. The dashboard uses local assets and individual external map links. It does not require API keys, subscriptions or hosted services.

Accuracy fixes remove the unconditional absentee signal and unsupported “verified” identity labels, flag conflicting owner names, preserve row-level provenance, reject ambiguous parcel/name ties, and invalidate HCAD profile caches when the lead set changes. Existing saved CSVs are not rewritten; older inferred matches still require review or regeneration.

## Expand into a sellable product deliberately

Sell a useful research workflow first. Suggested sequence: prove that a small group of users can import, shortlist, underwrite and track buyers locally; measure verified shortlist usefulness; then add one permitted automated source at a time. Do not promise verified equity or a comprehensive county feed from the current data.

Before hosted multi-user release, replace the development HTTP server with a maintained production application service and add authentication, workspace authorization, migrations, tested backup/restore, audit retention, dependency scanning, monitoring and operational support. Keep the underwriting and matching modules independent from the storage and transport layers so those changes do not rewrite the economics. Review data redistribution, privacy and transaction-related pricing with counsel. A subscription label alone does not settle brokerage classification.

The local edition is not a completed commercial SaaS or an independently audited security product. Open work includes complete foreclosure pagination, verified automated source permissions, stronger parcel-level deduplication across historic imports, structured evidence attachments, broader buyer criteria, robust installation packaging and commercial/legal review. No current properties were independently certified as profitable and no outreach was sent.

## Research limits and verification

Discovery covered official county/appraisal sources, current Texas agency rules and enacted legislation, scraper repositories and licenses. Follow-up resolved the seller-disclosure timing, free document viewing versus paid bulk access, and the distinction between tax appraisal and deal economics. Research stopped once the material design decisions had primary support; further broad searches were unlikely to remove the identified data-access and transaction-specific gaps.

Source retrieval occurred September 4, 2026. Most web pages do not expose a clear publication date; retrieval date is not publication date. Repository documentation and existing data are not substitutes for live completeness testing. The report was structurally checked as a Word document; page rendering was unavailable in this environment.
