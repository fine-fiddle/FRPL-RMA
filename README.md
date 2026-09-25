# Achievement x Economic Disadvantage — Chicago school comparator

A build-free static website: HTML5, CSS, vanilla JavaScript and vendored D3 7.9.0. Python + Polars prepare the committed JSON. No server API, npm, tracking, map service or runtime CDN is required.

## Preview

```sh
python3 -m http.server 8000
```

Open http://localhost:8000. Use HTTP rather than opening index.html directly because the site fetches local JSON files.

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
.venv/bin/python scripts/export_catalog.py
.venv/bin/python -m unittest discover -s tests -v
```

The 53 MB original XLSX is ignored by Git; its URL and SHA-256 are recorded in `data/manifest.json`. The reduced statewide import is `data/illinois/import-2024.json`. It retains raw suppression markers and source worksheet row numbers. SQLite keeps the original extracted demographic fields as well. The importer uses explicit column names and rejects duplicate identities, invalid numeric ranges and missing required fields. District and state summary rows are excluded.

The pilot contains 3,835 school identities and separate IAR/SAT observations. The public workbook has no tested-student counts for these rates. Statewide comparisons remain `awaiting_tested_counts`; no enrollment-based substitute, uncertainty interval, or residual ranking is generated. Chicago's existing 51 models and website JSON are reproduced exactly through SQLite. The displayed selector exposes Illinois → Chicago and marks Statewide as in preparation.

State standards, assessment year, tested grades and source population are part of a model's identity. IAR and SAT observations from a mixed-grade school remain separate. Region filtering must not silently refit a model. Cross-state proficiency and residual values are not a common scale. CPS IDs and statewide RCDTS IDs remain separate namespaces until an authoritative crosswalk is available; school names are not used to infer matches.

Next: acquire matching tested counts and school coordinates, verify the CPS-to-RCDTS crosswalk, then enable statewide models and region filtering. Historical statewide importers need year-specific schema and standards checks before additional years are exposed.

## Statistical specification

- Snapshot: SY2023–24 demographics and spring 2024 assessments. Historical, not current admissions data.
- Historical view: matched annual income and assessments, 2015–2019 and 2021–2024. Grade schools use IAR/PARCC; high schools use 2015–2016 PARCC and 2018–2019 / 2021–2024 SAT. The source workbook has no 2017 SAT records, and 2020 testing was canceled. No missing year is interpolated.
- Predictor: each year's CPS demographic report `low_income / enrollment × 100`. Source labels are Free/Reduced Lunch or Economically Disadvantaged. The percentage measures economic disadvantage; FRPL is historical source terminology.
- Outcomes: IAR grades 3–8 percent meeting/exceeding expectations; SAT grade 11 percent meeting/exceeding Illinois state standards. Reading represents ELA/EBRW. Combined is the simple mean of subject percentages, not joint proficiency.
- Separate OLS models for each year × assessment × ES/HS × math/reading/combined (51 models). Schools have equal fitting weight. Annual assessment cohorts include all eligible source schools, even if absent from the current directory. A school serving both levels can enter both separate cohorts. Search/type filters never refit. The current directory uses its profile's primary level; the 2024 snapshot and history share identical metrics and models.
- Raw residual: `e = y - Xβ`; leverage `hᵢ = xᵢ′(X′X)⁻¹xᵢ`; deleted residual variance `s²₍₋ᵢ₎ = (SSE − eᵢ²/(1−hᵢ))/(N−3)`; externally studentized residual `tᵢ = eᵢ / sqrt(s²₍₋ᵢ₎(1−hᵢ))`. The tests independently verify against explicit leave-one-out fits.
- Sampling variance: Jeffreys-smoothed `p̃ = (np+0.5)/(n+1)`, `v = 10000 p̃(1−p̃)/n`, using **tested counts**, not total enrollment. For combined outcomes, `v = (sqrt(v_math)+sqrt(v_reading))²/4`, a conservative maximum positive covariance assumption. The displayed combined count is the smaller subject count, not a deduplicated total.
- Approximate intervals: diagonal of `(I−H) diag(v) (I−H)′`, divided by the squared studentizing denominator; `t ± 1.96 SE`. These are conditional sampling intervals, not full confidence intervals for school effectiveness. The denominator is held fixed. They exclude model-choice uncertainty, demographic error, cohort variation and student dependence. Assessment percentages are rounded at source.
- No empirical-Bayes/multilevel shrinkage in v1. Studentization alone does not account for enrollment; intervals address tested-sample size under the stated assumptions.
- Missing/suppressed/invalid outcomes and demographics, or fewer than ten tested students, are omitted from models. They are never coerced to zero. Schools without eligible metrics remain in the directory; PK and other primary categories are excluded.
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
