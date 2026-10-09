# Data provenance

The [50-state expansion ledger](../../docs/state-expansion.md) records source discovery separately from releases. `state-expansion.json` retains official state/FIPS identities, assessment-source leads and audited CCD raw flags; reported availability does not approve a predictor or a denominator. [Audited obstacles](../../docs/expansion-blockers.md) identify sources that currently cannot support the comparison.

New state extracts retain raw source values, authoritative IDs, same-year income, suppression, definitions, worksheet/API row references, URLs and SHA-256 checksums. Native totals are preferred; grade aggregation requires complete coverage and verified score denominators. State-specific guides linked from the [expansion ledger](../../docs/state-expansion.md) specify different populations and rebuild paths. The [national audit](../../docs/national-source-audit.md) records discovery and source limitations; the [direct-certification adapter](../../docs/ccd-state-data.md) explicitly leaves tested counts and intervals unavailable. `scripts/prepare_states.py` rebuilds all audited state descriptors from committed extracts; raw downloads remain under ignored `data/raw/`. Extracts marked `release_status: audit_pending` retain their canonical hold on every rebuild and stay outside the browser catalog until the documented source issue is resolved.

`michigan.json` preserves the official 2024–25 bulk-file rows for separate M-STEP grades 3–7 and PSAT grade 8 comparisons, individual MSDS economic-disadvantage enrollment, protected cells and native-file/document checksums. The [Michigan guide](../../docs/michigan-data.md) documents the public email-delivery download flow and complete valid-score grade aggregation. Personal delivery addresses and temporary links are not retained as source provenance.

`new-hampshire-directory-crosswalk.json` retains native same-year income and CCD directory records linked only by exact published district/school IDs, including unlinked records and offered-grade fields. It is a source-only audit with no assessment joins or modeling approval. The [New Hampshire guide](../../docs/new-hampshire-data.md) documents validation and the remaining assessment-ID hold.

`los-angeles-district-audit.json` retains the official CCD district roster and exact same-year California school joins, with native grade/charter/type flags, source-row references and subject-specific coverage/exclusions. Its [district guide](../../docs/los-angeles-district.md) documents the reproducible audit and remaining model-validation gates. This source-only record grants no district modeling approval and does not alter the statewide California comparison.

`los-angeles-model-audit.json` retains separately fitted pure Los Angeles district models and per-school numerical diagnostics, with the pinned roster audit, population policy, verified subject counts and interval propagation. The district guide documents the fit and integration checks; this audit does not change the published statewide model.

`los-angeles.json` freezes the reviewed district population and normalized same-year inputs for the canonical `ca-lausd-2025` dataset. It links both immutable audits, native source records and the chosen charter/alternative and pure-grade policies. Rebuild with `scripts/prepare_los_angeles.py` against the existing populated database before exporting the catalog; the district guide documents repeatability and release verification.

`miami-dade-district-audit.json` retains the exact operational CCD district roster and linked same-year Florida grade-membership, individual lunch eligibility and native achievement records. Its [district guide](../../docs/miami-dade-district.md) separates native enrolled-grade usability from the proposed pure offered-grade cohort, preserves unmatched and excluded records, and documents missing score counts. This is a source-only audit: no district fits, canonical import or browser comparison are approved.

`miami-dade-model-audit.json` freezes the reviewed pure grade-school population and retains separate Math, ELA and Combined district fits, exact per-school inputs, externally studentized residuals, independent full-fit/deletion verification and influence diagnostics. Native valid-score counts, sampling variances and model-wide interval endpoints remain unavailable. The pinned source audit is immutable; this numerical audit does not approve canonical import or a browser release.

`miami-dade.json` freezes the separately reviewed normalized population and native same-year inputs for canonical dataset `fl-miami-dade-2025`. It retains all 370 pure grade-school profiles, explicit applicability and exclusions, exact attached district/charter/type evidence and both immutable audits. Rebuild with `scripts/prepare_miami_dade.py` against the existing populated database before exporting the catalog; all three district models have null valid-score counts and sampling intervals. The district guide documents numerical equivalence, repeatability and browser checks.

`clark-county-district-audit.json` retains the exact operational CCD roster for Nevada LEA `3200060` / `NV-02`, same-year native grades 3–8 assessment rows, school direct-certification and membership records, and explicit exclusions. Its [district guide](../../docs/clark-county-district.md) documents the Nevada grade-scope rules, including reported-zero ungraded enrollment, and the difference between planning counts and usable subject populations. This source-only audit keeps modeling approval false; tested counts remain unverified and no district model or browser comparison is released.

`clark-county-model-audit.json` freezes the native grade-only district population and retains separate Math, ELA and Combined fits, per-school externally studentized residuals, every explicit deleted-school refit and influence diagnostics. Each model uses 286 exact same-year members; the audit retains source exclusions and the broader 299-configuration/289-source-profile coverage. Counts, sampling variances and interval endpoints remain null. The immutable source audit keeps its false approval flags, and this numerical record does not approve canonical import or browser release.

`clark-county.json` freezes the separately reviewed native grade-school population and same-year inputs for canonical dataset `nv-clark-county-2025`. Its 289 profiles retain exact NCES/native identities, reported-zero ungraded enrollment, full CCD membership/direct-certification records and native SBAC G38 outcomes. Coverage preserves all 299 native lower-grade configurations, missing/suppressed cells and the wider operational roster. Rebuild with `scripts/prepare_clark_county.py` against the existing populated database before exporting the catalog; each independent 286-school district model has null valid-score counts and sampling intervals. The district guide records integration and browser verification, while both historical audits retain false approval flags.

`wisconsin-reportcards.json` retains selected raw cells, row numbers, field definitions, workbook notes and SHA-256 source hashes for the separate 2024–25 Wisconsin school-total comparisons. It uses same-year income and directory coordinates from `wisconsin.json`. See the [Wisconsin data guide](../../docs/wisconsin-data.md) for population differences, point-only models, coverage and rebuild instructions.

NYC inputs and their separate definitions are documented in the [NYC data guide](../../docs/nyc-data.md). `nyc.json` retains raw selected assessment and income values, official workbook notes, source URLs/checksums and verified map coordinates. Wisconsin inputs (`wisconsin.json`) are documented in the [Wisconsin data guide](../../docs/wisconsin-data.md); that extract retains raw grade-level counts, the annual enrollment snapshots, source URLs/checksums and the DPI-derived directory. The sections below describe the Chicago sources.

The Chicago sources below were retrieved September 17, 2026. All inputs are public school aggregates; no individual student records.

## School demographics / directory

`cps-profile-sy2324.csv`: full CSV export of [CPS School Profile Information SY2324](https://data.cityofchicago.org/d/cu4u-b4d9).

Download: https://data.cityofchicago.org/api/views/cu4u-b4d9/rows.csv?accessType=DOWNLOAD

Uses school ID, names, primary category, classification description, address and coordinates for the directory. Income and enrollment now come from the matched annual demographic reports below, rather than the profile's counts. The directory publication is SY2023–24.

## Assessments

`assessments-2024.csv`: extracted **without interpreting suppression strings** from these official CPS workbooks linked on [Assessment Reports](https://www.cps.edu/about/district-data/metrics/assessment-reports/):

`assessments-history.csv` is the same extraction across every available year in the IAR/PARCC workbook (2015–2019 and 2021–2024) plus SAT 2018–2019 and 2021–2024. The SAT workbook has no 2017 records. The missing 2020 row is intentional: statewide assessment administration was canceled. Historical regressions are fitted separately by year, level, assessment and subject; IAR/PARCC and SAT are not interchangeable.

- https://www.cps.edu/globalassets/cps-pages/about-cps/district-data/metrics/assessment-reports/iar-parcc_2015to2024_schoollevel.xlsx
- https://www.cps.edu/globalassets/cps-pages/about-cps/district-data/metrics/assessment-reports/assessment_psatsat_schoollevel_2024.xlsx

IAR: `IAR-PARCC ELA Results` and `IAR-PARCC Math Results`; Year 2024 and Test Name beginning `Combined` (grades 3–8); columns School ID, # Students Tested, % Met or Exceeded (column 12, not subscore columns).

For history, the same `Combined` rows are retained for grades 3–8 across all available years, and grades 9–12 for the two years present in the workbook (2015 and 2016). The site labels these observations IAR/PARCC.

SAT: `All Students Data` (not Metric Data, whose population differs); all available school years, Test SAT; subject-specific # Students with EBRW/Math Score and % Met or Exceeded State EBRW/Math Standards. The College Readiness Benchmark and mean scale scores are **not** substituted for state proficiency.

Download workbooks locally then run:

```sh
.venv/bin/python scripts/import_assessments.py /path/to/iar.xlsx /path/to/sat.xlsx
```

Then run the complete [Refresh modeled data](../../README.md#refresh-modeled-data) sequence to import the changed CSVs into SQLite and restore every comparison before catalog export. `prepare_data.py` reads SQLite; running it alone does not import changed source CSVs.

2024 remains the snapshot endpoint. CPS labels its newer 2025 release as redefined performance levels; those results are outside this release.

## Annual income counts

`income-history.csv` is extracted from the school-level sheets of all ten [CPS annual demographic reports](https://www.cps.edu/about/district-data/demographics/) for 2014–15 through 2023–24. Exact workbook URLs, SHA-256 checksums, sheet names and counts are in `income-sources.json`. Older `.xls` files use `All Schools` or `Schools`; newer `.xlsx` files use `Schools`. We select School ID, School Name, Total, and the count under Free/Reduced Lunch or Economically Disadvantaged. District totals and footnotes are excluded. Counts, rather than rounded published percentages, determine income percentage; blank or suppression tokens are retained.

`year` always means the school-year ending year, so fall 2023 20th-day income data joins spring 2024 assessments. No year is forward-filled or backfilled. CPS notes define economically disadvantaged as family income within 185% of the federal poverty line; naming and collection practices can change over time. School-wide demographics and tested-grade populations differ. The annual source replaces the directory's income values even in the 2024 snapshot, so the current and historical models agree.

Models include every eligible school in each annual assessment source, including schools no longer in the current directory. Schools serving both tested levels can appear in the two separate models. `../history.json` preserves every source school/year/level/assessment record, exclusions, and coefficients/sample sizes for all annual models; directory histories show the school's current primary level only. Suppressed results, fewer than ten tested, and missing/invalid same-year income have no residual. Models require at least four eligible schools and varying income.

## Map

`../chicago-areas.geojson`: https://data.cityofchicago.org/resource/igwz-8jzy.geojson

Official community area polygons. No street basemap or third-party tile requests.
