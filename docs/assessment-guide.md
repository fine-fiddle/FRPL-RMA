# Assessment guide

The separate [tests and standards page](../assessments.html) begins [GitHub issue #1](https://github.com/robot-assisted-projects/FRPL-RMA/issues/1). It explains the latest assessment data included in each ready comparison, rather than claiming to describe newer statewide testing contracts.

`scripts/export_assessment_guide.py` reads the committed manifest and 50-state source ledger. Only ready region datasets are eligible. The latest year is chosen separately for each dataset and comparison level; New York City's 2026 NYSTP and the state's 2025 snapshot remain separate, as do older high-school series. Assessment labels, tested grades, standards and source URLs are retained exactly. Each row links only the ready regions whose served model metadata matches that definition. Utah's unready definitions are excluded. States without a release remain visible with their source hold.

The map groups directly documented assessment-family names. Different grade cohorts, alternate assessments, state proficiency thresholds and regional model populations are still shown separately in the list. A shared color is not evidence of interchangeable scores or equal target ambition. Multiple families in the chosen population receive stripes. The state filter and list provide an accessible alternative to the geographic map; map states also support keyboard selection.

Provider information is a separate evidence gate. Michigan's grade 8 PSAT owner is documented as College Board in the existing native audit, with its source URL and checksum retained. Other provider fields remain null until primary evidence establishes the applicable-year owner or contractor role. A familiar assessment name or download domain does not establish its current delivery contractor. Relative target ambition also remains unaudited; the initial page assigns no `+` or `−` indicators. Those markers require evidence comparing equivalent instruments, grades, subjects, years and cut scores.

State boundaries derive from the [2024 Census cartographic archive](https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_state_500k.zip), already used by the state location audits. Its SHA-256 is `3e81cbb6cf5f60d9b01ef3e730afa14d61ce5f784252a0b33a696135e71447bc`. The exporter checks all 50 native FIPS/postal/name identities, excludes DC and territories, retains exterior polygon rings and islands, rejects unexpected holes in this pinned source, and simplifies coordinates with ring-area protection. D3's Albers USA projection provides Alaska and Hawaii insets. Boundary provenance and simplification metadata are committed with `data/us-states.geojson`.

```sh
.venv/bin/python scripts/export_catalog.py
.venv/bin/python scripts/export_assessment_guide.py
node --check assessments.js
node --test tests/assessment-guide.test.cjs
.venv/bin/python -m unittest discover -s tests -p test_assessment_guide.py -v
```

Regenerate the guide after changing the catalog. Rebuilding geometry requires the original ignored Census archive; ordinary guide exports can use the committed boundaries. This page does not import observations, fit models, change school comparisons or resolve source holds. Remaining issue #1 work is provider evidence and defensible equivalent-test threshold comparisons.

Verification on October 9, 2026 passed all 274 Python tests and 18 JavaScript tests, including independent checks for ready-only definitions, exact stored standards, separate regional years, provider evidence, boundary identity/winding and high-school link restoration. Subsequent exporter changes passed the targeted assessment tests. Browser checks covered the first filter after reload, shared-test colors, all 50 geographic paths, map mouse/keyboard selection, empty combinations, source holds, exact PSAT benchmarks, URL restoration, high-school navigation, desktop layout and a 390-pixel viewport without horizontal overflow. Browser console warnings/errors were empty. Existing model and catalog exports remain unchanged.
