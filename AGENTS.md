# Contributor and agent guide

## Purpose and architecture

- Achievement x Economic Disadvantage compares actual school proficiency with proficiency predicted from economic disadvantage. Results describe associations, not causal school effectiveness or overall quality.
- Keep the site static: HTML, CSS, vanilla JavaScript, vendored D3. No frontend build system or runtime backend.
- Python + Polars prepare data; SQLite is the local canonical store; committed JSON serves the browser. Do not calculate regressions in the browser.
- Use relative asset URLs so GitHub Pages works under `/FRPL-RMA/`.

## Where to work

- `index.html`, `styles.css`, `app.js`: interface, charts, filters, and shareable URL state.
- `scripts/database.py`, `scripts/schema.sql`, `scripts/build_database.py`: canonical data, import validation, and provenance.
- `scripts/prepare_data.py`: statistical calculations and Chicago exports.
- `scripts/prepare_illinois.py`, `scripts/import_illinois*.py`: statewide models and history.
- `scripts/prepare_nyc.py`, [NYC data guide](docs/nyc-data.md): NYC extraction, separate NY definitions, models and coverage limits.
- `scripts/prepare_wisconsin.py`, [Wisconsin data guide](docs/wisconsin-data.md): WISEdash extraction, two DPI standards eras, tested-only Forward/ACT models, redaction exclusions.
- `scripts/prepare_locations.py`: authoritative school-ID crosswalk and map coordinates.
- `scripts/export_catalog.py`: dataset catalog and import audit.
- `data/source/`: reproducible extracts; `data/*.json` and `data/illinois/`: website output.
- `data/raw/` and `data/build/`: ignored downloads and local database; do not commit them.
- [README.md](README.md): statistical specification, coverage limitations, rebuild instructions.
- [Source README](data/source/README.md): source formats and extraction guidance.

## Data and statistical rules

- Use externally studentized residuals. Do not replace them with raw proficiency or residuals divided by one overall standard deviation.
- Fit separate models by population, year, assessment, level, and subject. UI filters never refit a model.
- Match proficiency and income by authoritative school ID and the same school year. Never backfill income from another year or infer identity from a name.
- Preserve suppression and missingness; neither means zero. Retain source URLs, checksums, definitions, and raw values needed to audit transformations.
- Tested counts must be verified valid-score denominators. Enrollment, participation, and federal 95%-rule counts are not interchangeable substitutes.
- Do not average grade-level proficiency percentages without valid aggregation weights.
- Combined is the equally weighted mean of math and ELA proficiency, not the percentage proficient in both.
- Published, unsuppressed SAT rates with matching income can support residuals without tested counts. Label sampling intervals unavailable; never manufacture counts.
- Our interval propagation uses every member of the model. If any eligible member lacks counts, omit intervals for that entire model. Studentization does not provide enrollment adjustment or shrinkage.
- Keep importers repeatable. A second run must not duplicate observations or fail on existing provenance records.
- Preserve Chicago results when changing statewide adapters unless a methodological change is intentional and explained.

## Interface behavior to preserve

- Use ELA in visible text; `reading` remains an internal compatibility field.
- Default to Combined and selected-school comparison. Grade-school filters must exclude high schools.
- History shows residuals against same-year predictions. Preserve missing-year and assessment-change gaps.
- Shared URLs restore region, filters, selected schools, comparison scope, and history focus. An explicit empty selection must remain empty; reject invalid IDs and filter values safely.
- Search covers every school, including those outside the displayed list page. Keep the list paginated and chart updates off the synchronous keystroke path.
- Check the first search after a reload, not just subsequent searches. Avoid rendering thousands of school-list controls at once.
- Keep the header simple. Comparison caveats and detailed explanations belong in the expandable methodology sections.
- Preserve keyboard access, focus, and chart/table alternatives. Bump asset query versions in `index.html` when changing cached CSS or JavaScript.

## Commands and verification

Preview with `python3 -m http.server 8000`; use HTTP rather than opening the HTML file directly.
Use the existing `.venv`, or create one and install `requirements.txt` as described in the README.

```sh
node --check app.js
node --test tests/url-state.test.cjs
.venv/bin/python -m unittest discover -s tests -v
git diff --check
```

Run checks appropriate to the change. Verify interactive changes in a browser; numerical tests alone do not establish that charts or controls work.
For data changes, regenerate affected exports and inspect coverage/exclusions, same-year joins, and model output. Run the importer twice to check repeatability.

Full site rebuild, with the official Illinois workbook already downloaded:

```sh
.venv/bin/python scripts/build_database.py --illinois data/raw/24-RC-Pub-Data-Set.xlsx
.venv/bin/python scripts/prepare_data.py
.venv/bin/python scripts/prepare_illinois.py
.venv/bin/python scripts/prepare_nyc.py
.venv/bin/python scripts/prepare_wisconsin.py
.venv/bin/python scripts/export_catalog.py
```

Omitting `--illinois` rebuilds a Chicago-only database; exporting its catalog removes statewide availability. Run `prepare_nyc.py` to restore NYC before exporting the full catalog. Do not accidentally publish a reduced catalog. Source download and extraction steps are in the README and NYC data guide.

## Expansion and delivery

- Before adding a state/year, audit income definitions, assessment standards, tested grades, valid denominators, suppression, stable IDs, and the intended regression population.
- State proficiency thresholds are often incompatible. Studentization does not make them a common scale; keep state models separate rather than pooling them into a national ranking.
- Treat test or definition changes as explicit model metadata. Do not silently connect incompatible histories or invent missing data to complete coverage.
- Use the README for current source gaps and coverage; avoid duplicating changing counts here.
- Inspect Git status and the current branch before editing. Preserve unrelated work and newer edits when merging; follow the user's requested branch and publishing scope.
- GitHub Pages serves the repository root from `master`. A push is not proof that deployment has completed. Report what changed, what was verified, and any remaining limitation.
