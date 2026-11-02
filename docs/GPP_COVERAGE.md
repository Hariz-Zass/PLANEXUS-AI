# PLANEXUS AI — GPP Knowledge Registry

**Module:** Policy Intelligence v0.6 (local-only)  
**Checked:** 2026-11-02  
**Implementation:** \`backend/app/policy_registry.py\` → \`GET /api/policy/catalog\`, \`POST /api/policy/assess\`  
**Scope:** Verified source-indexed planning references, **not a live RT/GPP compliance certificate**.

## Current coverage

The user can select a GPP jurisdiction in Development Studio. The interface displays each number's source title, official URL, printed table/page and whether that number is a national *supplementary reference* or an indexed state clause. A result such as **numeric reference met** does **not** mean a plan has PBT approval, uses the currently adopted RT, or is feasible given building setbacks, drainage or access.

| ID | Source, responsible agency, year | Indexed numerical clauses | Status |
|---|---|---|---|
| gp001a_2016 | PLANMalaysia, GP001-A GPP Perumahan, 2016 | Jadual 2 lot minima by house/storey, selected one-storey floor minima, pp.44–45 | CURATED |
| perak_housing_2023 | PLANMalaysia Perak / Kerajaan Negeri Perak, Garis Panduan Piawaian Perumahan Negeri Perak 2023 | PR1 min floor, 3-storey max, 60-ft max height, min 3 bedrooms; 10 unchecked road/lane/setback design references | CURATED |
| gpp_commercial_gp003a | PLANMalaysia, GP003-A Kawasan Perdagangan (Addendum 2017) | None: commercial/shoplot lot-size rules NOT entered | CATALOG ONLY |
| gpp_parking_gp011a | PLANMalaysia, GP011-A Tempat Letak Kenderaan | None: parking ratios NOT entered | CATALOG ONLY |
| gpp_hills_gp007a11 | PLANMalaysia, GP007-A(11) Pembangunan Kawasan Bukit dan Tanah Tinggi | None: no numerical slope statutory thresholds entered | CATALOG ONLY |
| gpp_facilities_2022 | PLANMalaysia, GPP Kemudahan Masyarakat (Semakan Semula) 2022 | None: facility-area ratios NOT entered | CATALOG ONLY |

This is **not all Malaysian GPP**. The wider official catalog covers many other development categories; any missing category remains unknown until independently researched and verified.

Official references:
- National housing PDF: https://www.planmalaysia.gov.my/uploads/content-downloads/file_20251114202120.pdf — **GP001-A (2016), Jadual 2, printed pp.44–45**.
- Perak 2023 PDF (LPHP official mirror): https://lphp.gov.my/index.php/pekeliling-lphp/35-gp-piawaian-perumahan-negeri-perak-2023-1/file — **PR1, printed p.5**. Alternate PLANMalaysia Perak copy: https://planmalaysia.perak.gov.my/index.php/icon-media/muat-turun-borang/2-garis-panduan-perancangan?download=109%3Agaris-panduan-piawan-perumahan-negeri-perak-2023 .
- PLANMalaysia full GPP portal: https://www.planmalaysia.gov.my/main/garis-panduan-perancangan .
- PLANMalaysia facilities guideline publication: https://www.planmalaysia.gov.my/main/latest-news-details?id=999087c8-ffc9-11ef-bf69-fa163eda1aa9 .

### National housing minimum lot frontage × depth (metres)

| Housing type | Floors | Minimum (m) |
|---|---:|---:|
| Terrace, low-cost | 1 | 6.1 × 16.8 |
| Terrace, low-cost | 2 | 4.3 × 16.8 |
| Terrace, lower-middle cost | 1 | 6.1 × 18.3 |
| Terrace, lower-middle cost | 2 | 5.5 × 16.8 |
| Terrace, middle cost | 1 | 6.1 × 19.8 |
| Terrace, middle cost | 2–3 | 5.5 × 19.8 |
| Cluster | 1 | 12.2 × 15.2 |
| Cluster | 2–3 | 9.1 × 16.8 |
| Semi-detached | 1–3 | 12.2 × 19.8 |
| Detached | 1–3 | 15.2 × 22.9 |
| Detached, zero lot boundary | 1–3 | 13.7 × 21.3 |

These are **lot measurements** only, not the floor area of the house, an allowance for roads or a permitted site density. Selected 1-storey floor-area minima (low-cost terrace 65 m²; lower-middle terrace 69.7 m²; middle terrace 79 m²; cluster 83.6 m²; semi-detached 97.5 m²; detached 125.4 m²; zero-lot 92.9 m²) are stored where Jadual 2 explicitly provides them. These values must **not** be propagated to 2–3-storey classifications where a numeric floor minimum is not printed.

**Maximum lot size:** No maximum lot width or depth is recorded in Jadual 2. Fields \`max_lot_width_m\` and \`max_lot_depth_m\` must remain \`null\`. Developer-only numeric input guardrails such as width \`<=150 m\` are technical validation ranges, **not a GPP maximum**.

### Perak PR1 minimum floor area

| State housing cost band | Minimum floor space |
|---|---:|
| Low cost / Rumah Perakku I | 900 sq ft |
| Medium cost / Rumah Perakku II | 950 sq ft |
| Affordable / Rumah Perakku III | 1,000 sq ft |
| Open market | 1,001 sq ft and above |

The indexed Perak PR1 also sets a **three-storey maximum**, a maximum **60-ft ground-to-roof building height**, and at least **three bedrooms** for the covered terrace housing category. The registry also lists **10 additional PR1 design references**, including a minimum 50-ft service road, 15-ft rear lane, 20-ft firebreak/side lane, 15-ft front setback for low-cost terrace and 20-ft for other terrace categories, 20-ft corner and 5-ft end-lot side setbacks, and a 320-ft cul-de-sac maximum for applicable non-low-cost categories. The original wording is preserved as 'minimum', 'maximum' or merely 'stated' as appropriate. These dimensions are **NOT yet automatically checked against map geometry**, so no layout compliance result is issued.

**Crucially:** The Perak PR1 table supplies floor-space criteria rather than the national lot frontage/depth columns. The program labels national GP001-A lot minima as \`supplementary_national_reference\` when profile \`perak_2023\` is selected. This is **not a claim that Perak/PBT adopted those numeric lot minima**.

## How the system uses a policy

1. The planner selects a **jurisdiction**; no coordinate-based PBT/legal-status guess is performed.
2. The planner chooses **housing class, floors**, optionally Perak cost segment, building floor area, bedroom count and height.
3. Backend validates the data and compares only those fields for which the chosen policy has a manually checked number.
4. Each \`checks[]\` record includes **number, unit, observation, min/max direction, result, document title, URL, printed page and role**.
5. Saved scenarios retain \`policy_registry_version_at_save\`. When the registry changes, older policy result checks are **suppressed** and status is \`registry_version_changed_review\` until the user explicitly reviews and resaves.
6. Copilot answers direct GPP questions from deterministic curated content and returns exact \`policy_sources[]\` links; it must not use an LLM to make up unknown statutory requirements.

**A “meets_number” result proves only a numeric inequality, not overall compliance.** A “below_min” or “above_max” result flags a difference against the selected source, not a final development rejection by a PBT.

## Adding more GPP rules correctly

Before adding commercial lots, parking ratios, open space, community facilities, roads, slopes, setbacks, industrial or other Malaysian GPP content:

1. Locate the original issuing authority's official PDF and confirm its **current revision**, jurisdiction and whether the local state/PBT has adopted it.
2. Render/visually inspect the relevant table and record **title, year, issuing authority, exact printed page, item category, conditions/footnotes, source URL and document version**.
3. Include **minimum vs maximum semantics**, units (metres, m², feet, sqft), storey/house class and exceptions separately; never replace missing maximums with arbitrary values.
4. Insert vetted numbers as new entries in \`policy_registry.py\`, with clearly marked \`source_id\`, \`role\` and applicability. If only discovered but not verified, leave \`status=catalog_only\` and expose no numeric comparison.
5. Update \`REGISTRY_VERSION\`, add exact threshold tests and add a browser regression when a new form type is introduced. Existing saved proposals must request explicit re-evaluation.
6. Add locality-specific RT/PBT applicability only with official jurisdiction geometry + verified legislation/plan adoption information. Even then, the tool provides *screening assistance*, not a KM approval.

Do **not** add a random pile of PDFs to a generative model and equate retrieval with authoritative legal compliance. Original documents change, contain tables and footnotes, and can be superseded by local statutory plans.

## Local test and limitations

- Start PLANEXUS locally with \`START-PLANEXUS.bat\`.
- In **GPP Knowledge Registry** inspect source coverage and open official references.
- In **Development Studio**, set your site and proposal, choose GPP scope, then select housing type/storeys and run **Semak GPP**.
- Enter a smaller-than-minimum frontage and verify an explicit **below-minimum reference** result, alongside citation and applicability warning.
- For Perak, enter floor space below 1,000 sq ft for the relevant state cost category and verify the result is flagged (input uses m²).
- Keep a copy of the official source PDF and any current PBT/RT policy if using outputs in a professional planning submission.

**Not implemented yet:** automated official GPP downloads/sync, full-document retrieval, project-to-PBT spatial jurisdiction resolution, validity of RT/zoning, lot layout/setbacks, GPP coverage for all Malaysia, apartments/GFA, approved density, or legally binding approval determination.

The source is local-only; API is unauthenticated. **No Vercel deployment has been performed.**
