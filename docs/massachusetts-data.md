# Massachusetts MCAS 2025

The Massachusetts release uses the official Education-to-Career portal's [Next-Generation MCAS Achievement Results](https://educationtocareer.data.mass.gov/Assessment-and-Accountability/Next-Generation-MCAS-Achievement-Results/i9w6-niyt/about_data) and [Enrollment by Grade and Selected Populations](https://educationtocareer.data.mass.gov/Students/Enrollment-by-Grade-and-Selected-Populations/t8td-gens/about_data). The native API metadata, data extracts, definitions and technical report have source URLs and SHA-256 checksums in `data/source/massachusetts.json`. The initial audited snapshot is school year 2024–25; other available portal years require their own audits.

## Identity and income

Join the exact eight-digit `org_code` and `sy='2025'`. Enrollment uses `org_type='School'`; MCAS uses `org_type in('Public School','Charter School')`, `stu_grp='All Students'` and `subject_code in('ELA','MATH')`. Do not join by school name. Independent API count queries confirmed 1,817 enrollment rows and 11,848 MCAS rows. Every MCAS identity matches same-year enrollment. Preserve all reported grade and assessment rows in the extract; 2025 enrollment and grades define the modeled population.

The predictor is the published `li_pct` proportion × 100. Preserve `li_cnt` and `total_cnt`, and check that they reconcile within the published three-decimal rounding. [DESE's definition](https://profiles.doe.mass.edu/help/data.aspx?section=students) says 2022-present Low Income includes SNAP, TAFDC, DCF foster care and expanded MassHealth/Medicaid eligibility up to 185% of the federal poverty level, plus district-reported homeless and documented supplemental low-income students. October 1, 2024 SIMS enrollment is the same school year as spring 2025 MCAS. It includes pre-K and beyond-grade-12 enrollment. The 2015–21 Economically Disadvantaged definition differs; do not connect or backfill it without an explicit definition-era audit. CCD lunch counts are not used for Massachusetts income.

## Assessment populations and denominators

Use native `test_grade='ALL (03-08)'` totals for grade schools and the separate mixed-grade cohort. Use native `test_grade='10'` for pure high schools. These are published school totals, so no grade percentages are averaged and no suppressed grade rates are reconstructed. Preserve `m_plus_e_pct` × 100 as the outcome, including its whole-percentage-point rounding.

The [2025 MCAS technical report](https://www.doe.mass.edu/mcas/tech/2025-technical-report.pdf), appended Reporting Business Requirements pp. 25–27 (PDF pp. 1115–1117), distinguishes achievement from participation. Aggregate calculations include accountable students (`Summarize=1`) with `TestStatus=T`, assigned to their official school. First-year English learner and non-score statuses are excluded from achievement calculations. Performance-level counts `e_cnt + m_cnt + pm_cnt + nm_cnt` must equal `stu_cnt`; `e_cnt + m_cnt` must equal `m_plus_e_cnt`. These checks pass for every included source row. The separate `stu_part_pct` is preserved as audit metadata and never used as the denominator. This E2C dataset reports the general assessment and excludes MCAS-Alt, which DESE publishes separately.

[DESE suppresses achievement percentages for fewer than ten students](https://profiles.doe.mass.edu/help/data.aspx?section=assess). The API omits those rows; missing totals remain unavailable. An absent or suppressed rate cannot become zero or be inferred from other grades or counts. Subject models have all verified score denominators and therefore support sampling intervals. Combined is the equal mean of math and ELA, not the percentage proficient in both; uncertainty follows the repository's conservative propagation method.

## Coverage and separate cohorts

Classify schools from the complete same-year grade-enrollment snapshot. Grade schools have no enrolled grade 9 or above; pure high schools have no enrolled pre-K through grade 8. Mixed-grade schools have a separate grades 3–8 regression population. Their published grade-10 rows are retained in the extract but are not pooled into pure-high-school models. Two zero-enrollment identities are not modeled. Missing grades at those identities stay raw missing values.

| Cohort | Directory schools | Combined model | Mapped schools |
| --- | ---: | ---: | ---: |
| Grade schools, MCAS grades 3–8 | 1,396 | 1,228 | 1,384 |
| Pure high schools, MCAS grade 10 | 274 | 242 | 270 |
| Mixed-grade schools, MCAS grades 3–8 | 145 | 126 | 142 |

The high-school ELA model contains 243 schools; math and Combined contain 242. Exclusions include schools with no assessed grade, withheld totals, and missing same-year income. `coverage.json`, `history.json` and school-level exclusions retain these limits. There is one audited year. No national regression, common state proficiency scale, causal effectiveness claim or retrospective income substitution is implied.

## Map locations

The [CCD 2024–25 school lunch archive](https://nces.ed.gov/ccd/Data/zip/ccd_sch_033_2425_l_1a_073025.zip) supplies identity crosswalk fields only: `ST_SCHID=MA-DDDD-SSSSSSSS` and `NCESSCH`. Validate the exact organization-code component. Join that explicit NCES ID to the [NCES EDGE 2023–24 public-school coordinate service](https://nces.ed.gov/opengis/rest/services/K12_School_Locations/EDGE_GEOCODE_PUBLICSCH_2324/MapServer/0). The map dates are metadata; neither coordinates nor CCD lunch values determine model membership. Unmatched locations remain available in the list. County/city display labels come from that coordinate source.

## Rebuild and verify

Download the exact sources enumerated in `scripts/prepare_massachusetts.py` into ignored `data/raw/` to refresh the extract. Ordinary rebuilds use the committed extract offline:

```sh
.venv/bin/python scripts/prepare_massachusetts.py
.venv/bin/python scripts/prepare_massachusetts.py
.venv/bin/python scripts/export_catalog.py
.venv/bin/python -m unittest discover -s tests -p 'test_massachusetts.py' -v
```

Use `--extract` only with all required official source files present, or `--database PATH` for an isolated audit database containing `scripts/schema.sql`. The importer validates the whole incoming payload before replacing its own records and preserves unrelated datasets. Numerical verification independently recomputes deleted-school residuals, checks native denominators and published rounding, checks cohort separation and same-year joins, and imports twice. The shared catalog descriptor publishes only when matching SQLite models exist.
