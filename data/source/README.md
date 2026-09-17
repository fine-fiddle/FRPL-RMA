# Data provenance

Retrieved September 17, 2026. All inputs are public school aggregates; no individual student records.

## School demographics / directory

`cps-profile-sy2324.csv`: full CSV export of [CPS School Profile Information SY2324](https://data.cityofchicago.org/d/cu4u-b4d9).

Download: https://data.cityofchicago.org/api/views/cu4u-b4d9/rows.csv?accessType=DOWNLOAD

Uses school ID, names, primary category, classification description, address, latitude/longitude, total enrollment and low-income count. Demographics are not necessarily measured on the assessment date. The publication is SY2023–24; no unverified definition of low income as exactly FRPL is imposed.

## Assessments

`assessments-2024.csv`: extracted **without interpreting suppression strings** from these official CPS workbooks linked on [Assessment Reports](https://www.cps.edu/about/district-data/metrics/assessment-reports/):

`assessments-history.csv` is the same extraction across every available year in the IAR/PARCC workbook (2015–2019 and 2021–2024) plus 2024 SAT. The missing 2020 row is intentional: statewide assessment administration was canceled. The historical chart is descriptive; it does not fit one regression across years or treat IAR/PARCC and SAT as interchangeable.

- https://www.cps.edu/globalassets/cps-pages/about-cps/district-data/metrics/assessment-reports/iar-parcc_2015to2024_schoollevel.xlsx
- https://www.cps.edu/globalassets/cps-pages/about-cps/district-data/metrics/assessment-reports/assessment_psatsat_schoollevel_2024.xlsx

IAR: `IAR-PARCC ELA Results` and `IAR-PARCC Math Results`; Year 2024 and Test Name beginning `Combined` (grades 3–8); columns School ID, # Students Tested, % Met or Exceeded (column 12, not subscore columns).

For history, the same `Combined` rows are retained for grades 3–8 across all available years, and grades 9–12 for the two years present in the workbook (2015 and 2016). The site labels these observations IAR/PARCC.

SAT: `All Students Data` (not Metric Data, whose population differs); School Year 2023-2024, Test SAT; subject-specific # Students with EBRW/Math Score and % Met or Exceeded State EBRW/Math Standards. The College Readiness Benchmark and mean scale scores are **not** substituted for state proficiency.

Download workbooks locally then run:

```sh
.venv/bin/python scripts/import_assessments.py /path/to/iar.xlsx /path/to/sat.xlsx
.venv/bin/python scripts/prepare_data.py
```

2024 was selected to use matched historical demographics and assessment standards. CPS labels its newer 2025 release as redefined performance levels; this release makes no trend comparison.

## Map

`../chicago-areas.geojson`: https://data.cityofchicago.org/resource/igwz-8jzy.geojson

Official community area polygons. No street basemap or third-party tile requests.
