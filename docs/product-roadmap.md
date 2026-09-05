# Product priorities: smoother contract-assignment workflow

Reviewed September 4, 2026. Comparison sources are vendor descriptions, not independent accuracy tests.

[PropStream](https://www.propstream.com/propstream-features) emphasizes aggregated property data, research/filtering, maps, investor activity and valuation/rehab tools. [BatchLeads](https://batchleads.io/real-estate-investor) describes property/listing search and investor-focused filters. Those platforms have data coverage this local app does not yet provide; adding interface features alone will not close that gap.

## Recommended next work, in order

1. **Contract and follow-up pipeline:** seller conversation, offer, under contract, buyer found, assigned, closed/lost; earnest-money, option/inspection and closing deadlines; next action/date and overdue queue. Keep deadlines manually entered from the actual contract.
2. **Source freshness and import review:** import preview, duplicate/conflict review, visible last-seen date, county coverage, source run errors and retry controls. Never present failed refreshes as no leads.
3. **Comparable-sales worksheet:** attach permitted sale references, sale dates, condition/size adjustments and evidence quality; retain user-entered ranges. Avoid silently treating tax appraisal as resale value.
4. **Saved searches and more buyer criteria:** city/ZIP, property size, repair tolerance, assignment acceptance and recent confirmation. Keep county as a hard match boundary.
5. **Backups and responsiveness:** one-click consistent SQLite backup plus imports, tested restore, paginated results and cached read models invalidated on source changes. The current load path rereads CSVs and persists profiles; replace that with an import step and read queries before scaling to county-sized datasets.
6. **Integrated map and licensed imagery:** confirmed coordinates, parcel boundaries and an embedded street/satellite toggle. Pick a provider with documented commercial terms, attribution, quotas and a swappable adapter; free local use does not guarantee free commercial-scale hosting.

## Visual features implemented now

- One local cover photo per property: JPEG/PNG/WebP, max 2 MB input, resized to a maximum 1600-pixel dimension and re-encoded as JPEG without original metadata. Caption/source and optional date are stored with it.
- Photo/location data live in the existing `audit_logs/intelligence.db` database. They remain available offline. Include that file in backups.
- User-entered coordinates enable external Satellite view and Street View buttons. Address search is available before coordinates are entered. Check that coordinates identify the intended parcel; no automatic geocoding is claimed.
- Maps URLs need no Google API key. Links open the provider, keeping its imagery/attribution in its own viewer. [Google Maps URL documentation](https://developers.google.com/maps/documentation/urls/get-started)
- Embedded Street View Static imagery is a separate service with API/billing requirements; it has not been enabled. [Street View usage and billing](https://developers.google.com/maps/documentation/streetview/usage-and-billing)
- No listing-site photos were scraped, no synthetic home images were created, and imagery age is not proof of current condition. Upload your photos or photos you have permission to use. Actual automatic exterior-photo coverage remains a future licensed data integration.
