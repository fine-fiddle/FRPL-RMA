# New Jersey 2024–25 school reports

The adapter uses the [NJDOE School Performance Reports database](https://www.nj.gov/education/spr/download/) for the 2024–25 school year. It fits separate public-school models for grade-school NJSLA/DLM valid-score proficiency and grade-11 NJGPA graduation readiness. These are different outcomes and populations, not a common achievement scale.

## Published outcomes and denominators

The `ELAParticipationPerformance` and `MathParticipationPerformance` worksheets publish two different proficiency rates. This adapter uses `MetExceededExpectations_School`: proficient students divided by students with valid scores. It never uses `FederalProficiencyRate_School`, which can expand the denominator to satisfy the federal 95% participation rule, or the participation rate. The accompanying `ValidScores_School` is the verified score denominator. The [field layout](https://www.nj.gov/education/sprreports/download/DataFiles/2024-2025/Database_SchoolLayout.xlsx) and [reference guide, pages 12–15](https://nj.gov/education/spr/resources/doc/SPR_ReferenceGuide.pdf) specify these distinctions.

These native totals combine NJSLA Levels 4/5 and DLM Levels 3/4. They follow the state's accountable-school and half-year attendance rules. Only schools with enrolled grades 3–8 and no enrolled grades 9–12 enter this cohort. This avoids treating mixed-grade or high-school totals as grades 3–8 totals. Grade percentages are never averaged, and no suppressed component is reconstructed.

The `NJGPA` worksheet publishes `ELAGraduationReadyPct_School`, `MathGraduationReadyPct_School`, and their corresponding valid-score counts. The guide's pages 19–20 identify this as grade-11 testing, with grade-12 make-ups excluded. ELA is aligned with grade-10 standards; mathematics with Algebra I and Geometry. Schools enrolling grade 11 enter this separate cohort, including schools that also enroll younger grades. The high-school models do not use NJSLA/DLM accountability totals or selected SAT/ACT test-taker results.

Exact published percentages, including their rounding, are retained. `<10%`, suppression messages, and missing values remain unavailable. Valid-score counts support approximate conditional sampling intervals; if an eligible school lacks a count, intervals are omitted for the entire model. No proficient count is inferred from a rounded rate.

## Income, identity and population limitations

`EnrollmentTrendsByStudentGroup` publishes the same-year percentage of enrolled students classified as Economically Disadvantaged. The guide defines this as free/reduced-price lunch eligibility and describes end-of-year attending-school enrollment. The [2024–25 income reporting memo](https://www.nj.gov/education/broadcasts/2024/july/10/GuidelinesforReportingEnrollmentIncomeStatus.pdf) distinguishes federal free/reduced eligibility from the expanded New Jersey free-meal category. [NJDOE CEP reporting guidance](https://www.nj.gov/education/broadcasts/2021/july/7/CommunityEligibleProvisionSurveyandDocumentsfor2021-2022NowAvailable.pdf) requires individual household-income evidence or direct certification for enrollment and assessment reporting. Universal meal access does not automatically make every student economically disadvantaged. Collection completeness can still affect reported eligibility.

Income, enrolled grades and outcomes join through the exact nine-character county/district/school code (2+4+3 digits) and the exact `2024-25` school-year field. Leading zeroes are preserved. School names do not establish identity. The published income percentage is used directly; an exact eligible count is not manufactured from its rounding.

The assessment accountable school can differ from the attending school used for enrollment. Results for students placed in specialized receiving schools can be attributed to their sending public school. Whole-school economic enrollment also differs from the tested-grade population. These differences limit interpretation even with an exact same-year school-ID join. Grade mix and the inclusion of alternate assessments further distinguish this release from other states.

## Coverage and rebuild

The current directory contains 1,754 grade schools and 506 schools enrolling grade 11. Combined models include 1,659 grade schools and 429 high schools. Schools with unsupported or uncertain tested-grade scope are excluded from the directory; missing school totals and suppressed rates remain visible as exclusions. The release is one year, with no verified admissions classification or school coordinates. The list, relationship chart, residual comparisons and annual table remain available.

Rebuild from the committed extract:

```sh
.venv/bin/python scripts/prepare_new_jersey.py
.venv/bin/python scripts/export_catalog.py
```

To reproduce extraction, download the exact URLs in `scripts/prepare_new_jersey.py` into `data/raw/new-jersey/`, using the script's filenames, then add `--extract`. The large school workbook remains ignored. Source URLs, SHA-256 checksums, original worksheet rows, identity components, income values, both proficiency definitions, participation rates and valid-score counts are retained in `data/source/new-jersey.json`. Normalization is revalidated before each import. The canonical importer replaces only its own dataset and can run repeatedly.

`data/new-jersey/coverage.json` records exclusions and unmatched assessment rows. Tests verify all exported values against native fields, reject ranged rates, distinguish valid-score proficiency from the federal adjustment, check grade scopes and exact IDs, run the importer twice, and independently reproduce all six regressions and externally studentized residuals.
