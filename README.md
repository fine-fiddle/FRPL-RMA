# FRPL × RMA — Chicago school comparator

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
.venv/bin/python scripts/prepare_data.py
.venv/bin/python -m unittest discover -s tests -v
node --check app.js
```

The checked-in CSV inputs reproduce data/schools.json without downloading anything. To import revised official workbooks, see data/source/README.md. Choose a matched year and update the import logic explicitly; do not mix different proficiency standards.

## Hosting

Publish the repository root from the `live-site` branch in GitHub **Settings → Pages → Deploy from a branch → live-site → / (root)**. `.nojekyll` disables Jekyll. All asset paths are relative, so project-site hosting at `/FRPL-RMA/` works. No build step is needed.

## Statistical specification

- Snapshot: SY2023–24 demographics and spring 2024 assessments. Historical, not current admissions data.
- Historical view: the official IAR/PARCC workbook provides 2015–2019 and 2021–2024 school aggregates; 2020 is absent because testing was canceled. SAT history is available in the supplied workbook only for 2024, so high-school charts label the older 2015–2016 IAR/PARCC observations separately.
- Predictor: CPS `Student_Count_Low_Income / Student_Count_Total × 100`. This is explicitly a low-income proxy, **not a verified FRPL eligibility rate**.
- Outcomes: IAR grades 3–8 percent meeting/exceeding expectations; SAT grade 11 percent meeting/exceeding Illinois state standards. Reading represents ELA/EBRW. Combined is the simple mean of subject percentages, not joint proficiency.
- Six independent OLS models: ES/HS × math/reading/combined. Schools have equal fitting weight. Search/type filters never refit. Each school is assigned its profile's primary level; combined-level institutions are not duplicated across cohorts.
- Raw residual: `e = y - Xβ`; leverage `hᵢ = xᵢ′(X′X)⁻¹xᵢ`; deleted residual variance `s²₍₋ᵢ₎ = (SSE − eᵢ²/(1−hᵢ))/(N−3)`; externally studentized residual `tᵢ = eᵢ / sqrt(s²₍₋ᵢ₎(1−hᵢ))`. The tests independently verify against explicit leave-one-out fits.
- Sampling variance: Jeffreys-smoothed `p̃ = (np+0.5)/(n+1)`, `v = 10000 p̃(1−p̃)/n`, using **tested counts**, not total enrollment. For combined outcomes, `v = (sqrt(v_math)+sqrt(v_reading))²/4`, a conservative maximum positive covariance assumption. The displayed combined count is the smaller subject count, not a deduplicated total.
- Approximate intervals: diagonal of `(I−H) diag(v) (I−H)′`, divided by the squared studentizing denominator; `t ± 1.96 SE`. These are conditional sampling intervals, not full confidence intervals for school effectiveness. The denominator is held fixed. They exclude model-choice uncertainty, demographic error, cohort variation and student dependence. Assessment percentages are rounded at source.
- No empirical-Bayes/multilevel shrinkage in v1. Studentization alone does not account for enrollment; intervals address tested-sample size under the stated assumptions.
- Missing/suppressed/invalid outcomes and demographics, or fewer than ten tested students, are omitted from models. They are never coerced to zero. Schools without eligible metrics remain in the directory; PK and other primary categories are excluded.
- The single-school history chart uses the selected school’s annual aggregate proficiency and tested count. It is a trend display, not a longitudinal student cohort and not a cross-assessment equivalence claim; scores should be read within their assessment label.
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
