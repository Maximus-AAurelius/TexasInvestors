# Texas Investors Software Specification

## Purpose

Texas Investors is an evidence-first property intelligence and underwriting
workspace for a solo wholesaler operating primarily in Harris County, Texas.
It helps answer: **which properties deserve my next research or contact hour?**

## Source hierarchy

1. Verified public records and approved data sources
2. Normalized property and source records
3. Derived features and transparent rules
4. Manual underwriting assumptions
5. Explainable ranking and recommended next action

The application must never turn an estimate into a verified fact. Missing data
is `UNKNOWN`; conflicting data is preserved and flagged. HCAD appraisal value
is an appraisal-source fact, not an independent current-market value or ARV.

## Current implementation boundary

The current application connects HCAD bulk data to lead records by normalized
situs address and preserves parcel, property-class, improvement-year, size,
acreage, appraisal values, market area, and ownership-change facts. It also
stores local profiles, source provenance, score snapshots, and user statuses.

Manual underwriting stores the following separately from source facts:

- Current value or value range
- ARV low/base/high
- Repairs low/expected/high
- Estimated debt
- Buyer price
- Contract price
- Assumptions and notes

These values are decision inputs, not guarantees. Every calculation must show
its assumptions and should support conservative, base, and optimistic review.

## Scoring rules

Scores are configurable and explainable. Motivation signals do not prove seller
intent, and distress does not prove profitability. Opportunity scoring must not
be calculated until enough valuation, repair, buyer, and deal inputs exist.
Risk and data confidence remain separate from opportunity.

## Safety and compliance

Do not use protected characteristics in ranking or matching. Do not bypass
CAPTCHA, authentication, robots.txt, rate limits, or access controls. Texas
equitable-interest and disclosure requirements must be reviewed with qualified
legal counsel before production use; the application must not present legal
advice or call the wholesaler an agent or broker unless applicable.

The full reasoning framework is maintained in `knowledge/REAL_ESTATE_INTELLIGENCE.md`.