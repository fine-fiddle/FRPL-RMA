# Data provenance

Retrieved September 17, 2026. All inputs are public school aggregates; no individual student records.

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
.venv/bin/python scripts/prepare_data.py
```

2024 remains the snapshot endpoint. CPS labels its newer 2025 release as redefined performance levels; those results are outside this release.

## Annual income counts

`income-history.csv` is extracted from the school-level sheets of all ten [CPS annual demographic reports](https://www.cps.edu/about/district-data/demographics/) for 2014–15 through 2023–24. Exact workbook URLs, SHA-256 checksums, sheet names and counts are in `income-sources.json`. Older `.xls` files use `All Schools` or `Schools`; newer `.xlsx` files use `Schools`. We select School ID, School Name, Total, and the count under Free/Reduced Lunch or Economically Disadvantaged. District totals and footnotes are excluded. Counts, rather than rounded published percentages, determine income percentage; blank or suppression tokens are retained.

`year` always means the school-year ending year, so fall 2023 20th-day income data joins spring 2024 assessments. No year is forward-filled or backfilled. CPS notes define economically disadvantaged as family income within 185% of the federal poverty line; naming and collection practices can change over time. School-wide demographics and tested-grade populations differ. The annual source replaces the directory's income values even in the 2024 snapshot, so the current and historical models agree.

Models include every eligible school in each annual assessment source, including schools no longer in the current directory. Schools serving both tested levels can appear in the two separate models. `../history.json` preserves every source school/year/level/assessment record, exclusions, and coefficients/sample sizes for all annual models; directory histories show the school's current primary level only. Suppressed results, fewer than ten tested, and missing/invalid same-year income have no residual. Models require at least four eligible schools and varying income.

## Map

`../chicago-areas.geojson`: https://data.cityofchicago.org/resource/igwz-8jzy.geojson

Official community area polygons. No street basemap or third-party tile requests.
