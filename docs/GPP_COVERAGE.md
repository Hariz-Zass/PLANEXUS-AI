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
| perak_housing_2023 | PLANMalaysia Perak / Kerajaan Negeri Perak, Garis Panduan Piawaian Perumahan Negeri Perak 2023 | PR1-PR6 minimum floor area, maximum 3 storeys and 60-ft roof height, minimum 3 bedrooms; 10 PR1 road/lane/setback references remain unchecked | CURATED |
| gpp_commercial_gp003a | PLANMalaysia, GP003-A Kawasan Perdagangan (Addendum 2017) | None: commercial/shoplot lot-size rules NOT entered | CATALOG ONLY |
| gpp_parking_gp011a | PLANMalaysia, GP011-A Tempat Letak Kenderaan | None: parking ratios NOT entered | CATALOG ONLY |
| gpp_hills_gp007a11 | PLANMalaysia, GP007-A(11) Pembangunan Kawasan Bukit dan Tanah Tinggi | None: no numerical slope statutory thresholds entered | CATALOG ONLY |
| gpp_facilities_2022 | PLANMalaysia, GPP Kemudahan Masyarakat (Semakan Semula) 2022 | None: facility-area ratios NOT entered | CATALOG ONLY |

This is **not all Malaysian GPP**. The wider official catalog covers many other development categories; any missing category remains unknown until independently researched and verified.

Official references:
- National housing PDF: https://mytownnet.planmalaysia.gov.my/ver2/gp/GPP_PERUMAHAN.pdf — **GP001-A (2016), Jadual 2, printed pp.44–45**.
- Perak 2023 PDF (LPHP official mirror, PR1 p5, PR2 p7, PR3 p9, PR4 p11, PR5 p13, PR6 p15): https://lphp.gov.my/index.php/pekeliling-lphp/35-gp-piawaian-perumahan-negeri-perak-2023-1/file — **PR1, printed p.5**. Alternate PLANMalaysia Perak copy: https://planmalaysia.perak.gov.my/index.php/icon-media/muat-turun-borang/2-garis-panduan-perancangan?download=109%3Agaris-panduan-piawan-perumahan-negeri-perak-2023 .
- PLANMalaysia full GPP portal: https://www.planmalaysia.gov.my/main/garis-panduan-perancangan .
- PLANMalaysia facilities guideline publication: https://www.planmalaysia.gov.my/main/latest-news-details?id=999087c8-ffc9-11ef-bf69-fa163eda1aa9 .

### National housing minimum lot frontage × depth (metres)

| Housing type | Floors | Minimum (m) |
|---|---:|---:|
| Terrace, low-cost | 1 | 6.1 × 16.8 |
| Terrace, low-cost | 2 | 4.3 × 16.8 |
| Terrace, lower-middle cost | 1 | 6.1 × 18.3 |
| Terrace, lower-middle cost | 2 | 5.5 × 16.8 |
| Terrace, middle cost | 1–1½ (selector supports whole storeys only) | 6.1 × 19.8 |
| Terrace, middle cost | 2–3 | 5.5 × 19.8 |
| Cluster | 1 | 12.2 × 15.2 |
| Cluster | 2–3 | 9.1 × 16.8 |
| Semi-detached | 1–3 | 12.2 × 19.8 |
| Detached | 1–3 | 15.2 × 22.9 |
| Detached, zero lot boundary | 1–3 | 13.7 × 21.3 |

These are **lot measurements** only, not the floor area of the house, an allowance for roads or a permitted site density. Selected 1-storey floor-area minima (low-cost terrace 65 m²; lower-middle terrace 69.7 m²; middle terrace 79 m²; cluster 83.6 m²; semi-detached 97.5 m²; detached 125.4 m²; zero-lot 92.9 m²) are stored where Jadual 2 explicitly provides them. These values must **not** be propagated to 2–3-storey classifications where a numeric floor minimum is not printed.

**Maximum lot size:** No maximum lot width or depth is recorded in Jadual 2. Fields \`max_lot_width_m\` and \`max_lot_depth_m\` must remain \`null\`. Developer-only numeric input guardrails such as width \`<=150 m\` are technical validation ranges, **not a GPP maximum**.

### November 2026 terrace audit: ordinary Low / Mid / High vs official minimum

**Why this correction exists:** the first version assumed 6 × 20 m for 300 terrace units, which is not a documented terrace lot standard. The revised **Development Studio default** is the user's ordinary **Mid cost / 20 × 70 ft** size (exactly 6.096 × 21.336 m, approximately 1,400 sq ft per lot). This is **a selectable scheme dimension, not a national GPP minimum**.

The UI offers three easy-to-understand **design presets**, separate from machine-enforced national/source policy minima:

| Product-facing design selection | Preset lot | Basis | Legal policy meaning |
|---|---|---|---|
| Low terrace | 20 × 55 ft, 1 storey | GP001-A 2016 low-cost 1-storey minimum | A documented national minimum *for this class/storey only* |
| Mid terrace | **20 × 70 ft**, 1 storey | Real KPKT/HIMS mid-cost housing scheme brochures describe 1-storey 20 × 70 ft terraces | **Not** the national minimum. GP001-A 2016 middle-cost 1–1½ storey minimum is **20 × 65 ft**; for 2–3 storeys it is **18 × 65 ft** |
| High / Premium terrace | 22 × 75 ft, 2 storeys | An example terrace dimension appears in KEJORA's project listings | **Not a government-defined high-cost minimum**, and the KEJORA project listing does not itself confer a GPP high-cost category. GP001-A Jadual 2 has NO dedicated high-cost terrace row |

**Other official national band remains preserved:** "Kos sederhana rendah" is a separate category under GP001-A, not silently merged with Mid. It has 1-storey **20 × 60 ft** and 2-storey **18 × 55 ft** minimum. It is available in the detailed GPP selector alongside the three user-facing design starting points.

The minimum national terrace lots in **GP001-A 2016 Jadual 2** as verified from the official PDF (printed pp.44–45) are:
- Kos rendah: 1 tingkat **20 × 55 ft** (6.1 × 16.8 m); 2 tingkat **14 × 55 ft** (4.3 × 16.8 m).
- Kos sederhana rendah: 1 tingkat **20 × 60 ft** (6.1 × 18.3 m); 2 tingkat **18 × 55 ft** (5.5 × 16.8 m).
- Kos sederhana: 1–1½ tingkat **20 × 65 ft** (6.1 × 19.8 m); 2–3 tingkat **18 × 65 ft** (5.5 × 19.8 m).
- **Teres kos tinggi:** no separate category-specific minimum printed in national Jadual 2.

**Other national house types rechecked against the same 2016 edition:** cluster 12.2 × 15.2 m (1 storey), cluster 9.1 × 16.8 m (2–3), semi-detached 12.2 × 19.8 m, detached 15.2 × 22.9 m and detached zero-lot 13.7 × 21.3 m. Do not mix earlier 2014/other editions with the 2016 GP001-A values (for example the cluster 1-storey depth was printed differently in another edition).

### Local authority differences and real project examples

- **Kelantan, MBK planning-review form:** the locally published submission checklist distinguishes *Kos Sederhana* **20 × 65 ft** from *Teres Biasa* **20 × 70 ft**. Other local minima differ (example: low-cost terrace 20 × 50 ft). This document is **not automatically applied** to Perak, other states or all of Kelantan; adoption, amendments and RT must still be checked. Source: https://mbk.gov.my/web/wp-content/uploads/2021/03/template_ulasan_km_perumahan.pdf , printed p.1.
- **KPKT HIMS housing scheme examples:** 20 × 70 ft also appears in sales brochures explicitly labelled *Rumah Teres Kos Sederhana*, showing a legitimate **project size**, not a statutory universal minimum. Source: https://hims.kpkt.gov.my/files/8502/8502-4/IKLAN_BROSUR_01.pdf .
- **KEJORA project listings:** 22 × 75 ft occurs in recorded terrace-house project components, used solely as a flexible example for premium-sized development. Source: https://www.kejora.gov.my/perkhidmatan/hartanah/projek-penswastaan-dan-pembangunan-bercampur-3/ .
- **Perak PR1 (2023) printed p.5:** for terrace housing, **floor area** minima by class are 900/950/1,000/1,001 sq ft; no numerical minimum lot frontage × depth is specified. Never confuse the **floor area of a house** with its **land lot area**.

**Feet/metre precision:** GP001-A pairs rounded metric values with feet: 20 ft = exactly 6.096 m whereas the printed metric is 6.1 m; 18 ft = 5.4864 m whereas the printed metric is 5.5 m. A proposal entered in exact feet should **not fail by 4–36 mm** just because the document uses rounded metric equivalents. The engine accepts both published equivalent units (using the lesser of the two mathematically equivalent printed minima, not an arbitrary slack), retains the document's displayed metric bound and exposes the printed equivalent in checks. It still flags genuinely undersized plots.

**Updated gross-land default example:** 300 mid-cost lots at **20 × 70 ft**, with 20% road, 10% open space, 5% facilities and 5% other reserves (all user assumptions) require about **3.90193 ha of plot rectangles and 6.50321 ha gross**. The former 6.0 ha figure applied only to the earlier arbitrary **6 × 20 m** assumption, not to 20 × 70 ft.

Nothing in these sizes verifies frontage layout, land ownership, legal zoning, availability of contiguous low-slope areas, road widths or setbacks. No maximum lot dimensions are inferred where the local/national source gives only a minimum.

### Perak PR2–PR6 minimum floor area (confirmed published tables)

| Perak category | Printed page | Minimum floor area | Additional indexed numerical bounds |
|---|---:|---:|---|
| PR2 Rumah Berkembar (semi-detached) | 7 | 1,000 sq ft | 3 storeys max; 60-ft ground-to-roof height max; 3 bedrooms min |
| PR3 Rumah Kluster (cluster) | 9 | 1,000 sq ft | Same floors/height/bedrooms; 4 units per cluster is a stated configuration requirement, not yet layout-checked |
| PR4 Rumah Sesebuah (detached) | 11 | 1,000 sq ft | 3 storeys max; 60-ft ground-to-roof height max; 3 bedrooms min |
| PR5 Rumah Sesebuah Zero Lot Boundary | 13 | 1,000 sq ft | 3 storeys max; 60-ft ground-to-roof height max; 3 bedrooms min |
| PR6 Rumah Bandar (townhouse) | 15 | 900 sq ft | 3 storeys max; 60-ft ground-to-roof height max; 3 bedrooms min; two owners per lot is NOT yet checked |

**Lot size != floor space.** PR2–PR6 do not supply new national-style lot width/depth minima for the product to assert. GP001-A dimensions (if a matching national category exists) remain supplementary references until state/PBT adoption is verified.

These PR2–PR6 source rows are now automatically compared to the user's entered floor area (m²), bedroom count, storeys and building height after a Perak jurisdiction + housing type is selected. Road widths, cul-de-sac limits, building setbacks, block length and lot layout are **not** compared yet.

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
