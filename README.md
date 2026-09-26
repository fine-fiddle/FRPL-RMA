# Achievement x Economic Disadvantage — public school comparator

New York → New York City includes grade-school NYSTP results through 2026 and separately labeled Regents ELA/Algebra I results through 2023, with same-year NYCPS Poverty data, residual histories and sampling intervals. Charter coverage, suppressed poverty values and historical closed-school coverage have explicit limitations. See the [NYC data guide](docs/nyc-data.md) for sources, definitions and rebuild commands.

A build-free static website: HTML5, CSS, vanilla JavaScript and vendored D3 7.9.0. Python + Polars prepare the committed JSON. No server API, npm, tracking, map service or runtime CDN is required.

## Preview

```sh
python3 -m http.server 8000
```

Open http://localhost:8000. Use HTTP rather than opening index.html directly because the site fetches local JSON files.

## Sharing comparisons

Copy the browser address to share the current comparison. URL parameters preserve state/region, school level, subject, program, search, up to six selected school IDs, history focus, and selected/all-filtered comparison scope. Updates replace the current address without reloading or adding a browser-history entry per keystroke. Opening or reloading a link restores its settings after the matching dataset loads. Invalid filter values and school IDs are ignored; an explicit `schools=` preserves an empty selection. Map zoom and list pagination are local viewing details.

Run `node --test tests/url-state.test.cjs` to check URL round-trips, empty selections and invalid-link handling.

## Refresh modeled data

Python 3.14 was used for the pinned requirements.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/build_database.py
.venv/bin/python scripts/prepare_data.py
.venv/bin/python scripts/export_catalog.py
.venv/bin/python -m unittest discover -s tests -v
node --check app.js
```

The checked-in CSV inputs reproduce data/schools.json without downloading anything. To import revised official workbooks, see data/source/README.md. Choose a matched year and update the import logic explicitly; do not mix different proficiency standards.

## Hosting

Publish the repository root from the `master` branch in GitHub **Settings → Pages → Deploy from a branch → master → / (root)**. `.nojekyll` disables Jekyll. All asset paths are relative, so project-site hosting at `/FRPL-RMA/` works. No build step is needed on the hosting service.

## Illinois pilot and SQLite

The local canonical database is `data/build/schools.sqlite` (ignored by Git). Raw sources remain immutable inputs; SQLite holds school identities, annual economic observations, assessment observations and definitions, provenance, model runs and results. The browser downloads only generated JSON. SQLite is rebuilt transactionally to a temporary file before replacing the prior database.

To include the official statewide 2024 extract:

```sh
mkdir -p data/raw
curl -L --fail 'https://www.isbe.net/Documents/24-RC-Pub-Data-Set.xlsx' -o data/raw/24-RC-Pub-Data-Set.xlsx
.venv/bin/python scripts/build_database.py --illinois data/raw/24-RC-Pub-Data-Set.xlsx
.venv/bin/python scripts/prepare_data.py
.venv/bin/python scripts/prepare_illinois.py
.venv/bin/python scripts/prepare_nyc.py
.venv/bin/python scripts/export_catalog.py
.venv/bin/python -m unittest discover -s tests -v
```

The 53 MB original XLSX is ignored by Git; its URL and SHA-256 are recorded in `data/manifest.json`. The reduced statewide import is `data/illinois/import-2024.json`. It retains raw suppression markers and source worksheet row numbers. SQLite keeps the original extracted demographic fields as well. The importer uses explicit column names and rejects duplicate identities, invalid numeric ranges and missing required fields. District and state summary rows are excluded.

The pilot contains 3,835 school identities and separate IAR/SAT observations. Illinois → Statewide enables 2024 IAR rankings: 2,497 math, 2,475 ELA, and 2,405 Combined schools, with externally studentized residuals and approximate conditional sampling intervals. Chicago's existing 51 models remain separate and unchanged. Search can match school, district, city or county; filtering never refits the statewide model.

Tested counts come from Education Data Center v3.1, whose technical documentation identifies ISBE as the source of 2023–24 denominators. The committed compact extract retains all-student regular IAR school/grade records; `data/source/illinois-counts-sources.json` records provenance. To regenerate it, download `https://eddatacenter.org/api/data/3.1?state=IL&year=2024` to `data/raw/edc-il-2024.csv` and run `.venv/bin/python scripts/prepare_illinois.py --extract data/raw/edc-il-2024.csv`.

The committed `data/source/illinois-history-2023.json` contains the original 2023 demographic values, grade-level proficiency components, tested counts and source checksums. `prepare_illinois.py` imports it into SQLite before fitting both years. To refresh that extract, download the linked 2023 ISBE workbook and EDC 2023 CSV and run `.venv/bin/python scripts/import_illinois_history.py --workbook data/raw/23-RC-Pub-Data-Set.xlsx --counts data/raw/edc-il-2023.csv`, then prepare and export as above. Historical schools use RCDTS joins, never name matching or later-year income substitution.

Validation requires unique grade records, exact positive integer counts for every expected IAR grade in the Report Card grades-served range, and weighted grade proficiency within 0.11 percentage points of the published school rate. This conservative gate accepts 5,085 school/subject denominators and rejects 820; income availability and the minimum of ten tested further restrict model eligibility. Suppressed or ranged values are never imputed. SQLite stores validated denominators; model input hashes include the count extract. Published statewide income percentages are used directly, preserving rounded/suppressed demographic numerators separately.

Statewide SAT rankings now include 696 eligible schools per subject model, with externally studentized residuals but **no sampling intervals**. Verified SAT tested counts are unavailable. Published, unsuppressed SAT proficiency and same-year income are sufficient for the residual calculation; counts are required for sampling intervals. If any member of a model lacks a tested count, the entire model's propagated sampling intervals are unavailable. No enrollment-based substitute is used. The directory includes 686 of those SAT schools under ISBE's High School classification; model cohorts also include eligible mixed-grade schools.

SAT history covers 2017–2019 and 2021–2024. The 2017 school-wide percentages come directly from the documented Report Card archive; 2018 uses levels 3 + 4 from its annual workbook. The committed `data/source/illinois-sat-history.json` preserves original level 3 + 4 percentages, demographic fields, official workbook URLs and checksums. To refresh, download the workbooks listed in `scripts/import_illinois_sat_history.py` and run `.venv/bin/python scripts/import_illinois_sat_history.py --extract`, then prepare and export. Suppressed components remain unavailable. Each year gets its own regression and same-year income join.

Statewide grade-school history includes 2017 PARCC and 2023–2024 IAR. The 2017 school-wide rates need no grade aggregation and produce point-only residuals, using 2017 income. Extract with `.venv/bin/python scripts/import_illinois_2017.py --extract` after downloading the three official files listed in that script. The importer checks field numbers against the official layout and requires matching school IDs in both archives. The 2023 aggregate uses ISBE grade-level percentages at levels 4 + 5 weighted by exact EDC tested counts, with every expected grade required. Grade rates must reconcile to EDC within 0.16 percentage points (two rounded ISBE levels plus rounded EDC percentage). Earlier workbooks provide grade-level percentages without verified aggregation weights; these are not averaged or mixed with alternate-assessment aggregates. Models use all eligible annual source schools, independent of current directory membership. Elementary/middle and high-school directories follow ISBE School Type. Statewide program filtering has partial coverage: CPS 2023–24 classifications are transferred only through verified ID matches. All other schools remain Unclassified.

The statewide map locates 3,547 of 3,550 directory schools using NCES 2023–24 coordinates and the exact EDC state-ID/NCES-ID crosswalk. Three schools without matched coordinates remain available in the list. `data/source/illinois-locations.json` records IDs, coordinates and source checksums. The simplified Illinois boundary comes from the Illinois State Geological Survey. `scripts/prepare_locations.py` rebuilds these compact files from the paginated NCES directory, EDC 2024 CSV and boundary export; it rejects ambiguous IDs and incomplete pagination.

State standards, assessment year, tested grades and source population are part of a model's identity. IAR and SAT observations from a mixed-grade school remain separate. Region filtering must not silently refit a model. Cross-state proficiency and residual values are not a common scale. CPS IDs and statewide RCDTS IDs remain separate namespaces, linked only through the verified crosswalk below; school names are not used to infer matches.

Remaining source limitations: verified SAT and 2017 PARCC denominators, 2018 PARCC and 2019–22 IAR aggregates, admissions classifications outside verified CPS matches, and unmatched or ambiguous CPS/state IDs. These are documented gaps; Chicago and statewide cohorts remain separate.

The official [CPS identifier dataset for 2013–14](https://data.cityofchicago.org/d/c7jj-qjvh) provides a partial crosswalk. `scripts/prepare_cps_crosswalk.py` accepts only unique CPS/state ID pairs present in current CPS profiles whose NCES ID also agrees with the 2024 EDC/NCES crosswalk. It accepts 481 mappings and records excluded IDs/reasons in `data/source/cps-illinois-crosswalk.json`. Historical charter-network IDs shared by multiple campuses and changed NCES IDs are not merged. Download the JSON URL recorded in that file to `data/raw/cps-identifiers-2014.json`, then run the script to refresh. This establishes a checked directory link, not uninterrupted historical continuity or a shared regression population.

See [Illinois source-gap audit](docs/illinois-data-gaps.md) for evidence, rejected substitutes, and next steps.

## Statistical specification

The snapshot and history dates in this section describe the Illinois/Chicago release. NYC uses the same regression and interval formulas with the distinct measures and years in the [NYC data guide](docs/nyc-data.md).

- Snapshot: SY2023–24 demographics and spring 2024 assessments. Historical, not current admissions data.
- Historical view: matched annual income and assessments, 2015–2019 and 2021–2024. Grade schools use IAR/PARCC; high schools use 2015–2016 PARCC and 2018–2019 / 2021–2024 SAT. The source workbook has no 2017 SAT records, and 2020 testing was canceled. No missing year is interpolated.
- Predictor: each year's CPS demographic report `low_income / enrollment × 100`. Source labels are Free/Reduced Lunch or Economically Disadvantaged. The percentage measures economic disadvantage; FRPL is historical source terminology.
- Outcomes: IAR grades 3–8 percent meeting/exceeding expectations; SAT grade 11 percent meeting/exceeding Illinois state standards. Reading represents ELA/EBRW. Combined is the simple mean of subject percentages, not joint proficiency.
- Separate OLS models for each year × assessment × ES/HS × math/reading/combined (51 models). Schools have equal fitting weight. Annual assessment cohorts include all eligible source schools, even if absent from the current directory. A school serving both levels can enter both separate cohorts. Search/type filters never refit. The current directory uses its profile's primary level; the 2024 snapshot and history share identical metrics and models.
- Raw residual: `e = y - Xβ`; leverage `hᵢ = xᵢ′(X′X)⁻¹xᵢ`; deleted residual variance `s²₍₋ᵢ₎ = (SSE − eᵢ²/(1−hᵢ))/(N−3)`; externally studentized residual `tᵢ = eᵢ / sqrt(s²₍₋ᵢ₎(1−hᵢ))`. The tests independently verify against explicit leave-one-out fits.
- Sampling variance: Jeffreys-smoothed `p̃ = (np+0.5)/(n+1)`, `v = 10000 p̃(1−p̃)/n`, using **tested counts**, not total enrollment. For combined outcomes, `v = (sqrt(v_math)+sqrt(v_reading))²/4`, a conservative maximum positive covariance assumption. The displayed combined count is the smaller subject count, not a deduplicated total.
- Approximate intervals: diagonal of `(I−H) diag(v) (I−H)′`, divided by the squared studentizing denominator; `t ± 1.96 SE`. These are conditional sampling intervals, not full confidence intervals for school effectiveness. The denominator is held fixed. They exclude model-choice uncertainty, demographic error, cohort variation and student dependence. Assessment percentages are rounded at source.
- No empirical-Bayes/multilevel shrinkage in v1. Studentization alone does not account for enrollment; intervals address tested-sample size under the stated assumptions.
- Missing/suppressed/invalid outcomes and demographics, or known counts below ten tested students, are omitted from models. They are never coerced to zero. CPS and statewide IAR additionally require verified tested counts. Statewide SAT and 2017 PARCC accept published unsuppressed school-wide rates without counts and mark intervals unavailable. Schools without eligible metrics remain in the directory; PK and other primary categories are excluded.
- The single-school history chart shows externally studentized actual-minus-predicted residuals with approximate 95% conditional sampling intervals and a zero prediction reference. Each assessment uses income counts from the same school year, keyed by CPS ID; no backfilling from later years. Hover/focus or expand the annual table for actual, predicted, raw gap, studentized residual, income, tested count and model size. Lines break across missing years or assessment changes. Trends describe relative position within each year's cohort, not causal improvement or cross-test equivalence.

## Annual income and residual data

`data/source/income-history.csv` contains 6,578 school/year observations for 2014–15 through 2023–24, including the no-assessment year 2019–20. `data/source/income-sources.json` records official URLs, workbook checksums, labels and row counts. Extract downloaded workbooks using `.venv/bin/python scripts/import_income.py /path/to/manifest.json`; each manifest entry needs `year` (ending year), `file` (local workbook) and `url`. Then regenerate assessments and run `scripts/prepare_data.py` as above.

`data/history.json` contains all historical school/assessment records, explicit exclusion reasons and model metadata, including schools outside the displayed directory. `data/schools.json` embeds history for the current directory. Suppressed outcomes, insufficient tested counts and missing same-year income remain unmodeled; an unavailable residual is never zero. Unit tests independently refit every annual regression, verify source-year joins and ensure the 2024 snapshot matches history.
- Program labels use CPS school-level Classification_Description, not a verified inventory of every program. In particular, mixed-program schools may have neighborhood and selective offerings.
- This descriptive association is not causal value added. Prior attainment, admissions selection, grade mix, language, disability, resources and other important variables are omitted. OLS can predict outside 0–100%; predictions remain unclipped.

## Files

- index.html, styles.css, app.js: site, interaction and D3 visualizations.
- data/source/*.csv: reproducible source snapshots.
- scripts/import_assessments.py: workbook → current and historical source CSV conversion.
- scripts/prepare_data.py: Polars ingestion, validation, fitting and JSON output.
- tests/test_models.py: independent statistical correctness checks.
- data/chicago-areas.geojson: official City community boundaries.
- assets/d3.v7.min.js: vendored D3; license in assets/D3-LICENSE.

The repository's existing license applies to original code; public-source data and D3 retain their respective terms.
