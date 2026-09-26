# New York City data

This adapter adds New York → New York City, with independent NYCPS models. It does not enable New York statewide rankings or pool NYC with Illinois.

## Measures and coverage

| Level | Snapshot | History | Outcome |
| --- | --- | --- | --- |
| Grade schools | 2026 | 2022–2026 | NYSTP grades 3–8, published all-grades/all-students Levels 3 + 4 percentage |
| High schools | 2023 | 2022–2023 | Regents ELA and Algebra I, score 65 or above, highest score per student/exam/year |

The grade-school source is NYCPS's district-school release, not all public schools statewide. Its notes exclude charter schools and generally District 75 from school-level records. Do not describe this as complete NYC public-school coverage. The directory contains 1,568 source-matched schools; 1,566 have unambiguous coordinates. Admissions classifications are not inferred; the NYC school-type filter is disabled.

Regents records include January, June and August administrations. Exam takers can be in different grades and are not a fixed graduating cohort. Students who completed Algebra I in middle school may be absent from their high school's Algebra I denominator. This limits interpretation of high-school rankings. Math means Algebra I only; ELA and math populations can differ. Combined is the equally weighted mean of the two rates, not the percentage passing both. Keep the 2023 high-school year visible independently of the 2026 grade-school year.

Income is the same school year's NYCPS **Poverty** percentage: meal-eligibility or Human Resources Administration benefits. It is not NYC's Economic Need Index, which combines additional circumstances and census-tract estimates. Do not label this measure identical to Illinois Low Income. Preserve the source's `Above 95%` / `Below 5%` strings as unavailable. Do not impute a midpoint, cap, or reconstruct suppressed percentages. These exclusions particularly affect high-poverty schools and limit representativeness of the fitted population.

The current demographic release includes only schools open in 2025–26, even in earlier-year rows. Assessment schools without a same-year demographic match are excluded from that annual model; historical coverage is not complete. Joining on the exact six-character DBN preserves its leading district zero. Never join by school name or reuse a later income percentage.

The directory uses the most recent demographic grade enrollment: schools with grades 9–12 are listed under high schools. Eligible grades 3–8 results from mixed-grade schools still enter the ES model. Thus the model's sample size can exceed the ranked schools visible in that directory level. This follows the same cohort/directory distinction used in Illinois.

NYSTP changed standards in 2023. The importer uses separate assessment identities for 2022 and 2023 onward, and history lines break there. The published 2020/2021 grade-school gap is not filled. Earlier assessments outside the demographic workbook's years are not modeled. Both subjects require published rates, exact tested counts of at least ten, and matching numeric income. Count/rate pairs must reconcile within 0.011 percentage points. Model formulas and conservative combined sampling intervals reuse `prepare_data.build_history`.

## Sources and rebuild

[NYCPS Test Results](https://infohub.nyced.org/reports/academics/test-results) supplies ELA, math and Regents workbooks. The [NYCPS information/data overview](https://infohub.nyced.org/reports/students-and-schools/school-quality/information-and-data-overview) supplies the demographic snapshot. The compact `data/source/nyc.json` retains selected raw values, source notes, URLs and checksums. Raw workbooks stay in ignored `data/raw/`.

`scripts/prepare_nyc.py` lists six exact download URLs in `SOURCES`. Save them under the matching filenames in `data/raw/`. The workbook URLs are mutable; a later download may be a new source revision and needs renewed validation. The source snapshot in this branch was retrieved September 26, 2026.

With the existing Chicago/Illinois database built:

```sh
.venv/bin/python scripts/prepare_nyc.py --extract
.venv/bin/python scripts/export_catalog.py
```

To rebuild solely from committed extracts, omit `--extract`. The NYC importer replaces only its own records and preserves Illinois. Run it twice and compare output hashes. A complete fresh build is:

```sh
.venv/bin/python scripts/build_database.py --illinois data/raw/24-RC-Pub-Data-Set.xlsx
.venv/bin/python scripts/prepare_data.py
.venv/bin/python scripts/prepare_illinois.py
.venv/bin/python scripts/prepare_nyc.py
.venv/bin/python scripts/export_catalog.py
```

The [city school-point file](https://data.cityofnewyork.us/d/jfju-ynrr) is dated August 28, 2024. Coordinates are explicit latitude/longitude fields, joined by ATS/DBN. Multiple different locations for one DBN are left unmapped; no name matching or geocoding is used. Locations can be older than the assessment snapshot. [NYC Planning borough boundaries](https://data.cityofnewyork.us/d/gthc-hcne) are rounded to five decimal places and oriented for D3. They are map context, not regression boundaries.

`data/nyc/schools.json` serves the interface; `data/nyc/history.json` includes every retained assessment record, model and exclusion. SQLite definitions carry state NY, assessment year, standards and source population. The manifest exposes only NYC under New York.

## Next source improvements

Charter and admissions inputs have now been gathered and validated separately: see the [charter and admissions coverage audit](nyc-expansion-coverage.md). They are not yet part of the published NYCPS models; the audit describes the outcome and identity decisions needed before integration.

Prioritize integrating the gathered NYSED assessment/economic sources with explicit outcome definitions, and archived annual demographics that retain schools subsequently closed. The NYCPS demographic notes warn that Poverty can understate need for charters not using NYCPS meal services; the new NYSED measure must have its own models. Current NYC admissions categories still need an authoritative program mapping rather than CPS labels or undated reuse of the 2021 directory. None of these gaps should be concealed by guessed data.
