# Pennsylvania 2024–25 grade schools

This release fits separate Math, ELA and Combined models to Pennsylvania public
grade schools. It uses published PSSA grades 3–8 school totals and same-year
individual reported economic disadvantage. Pennsylvania's definition is broader
than uniform FRPL eligibility, so it has its own label and regression population.

## Official source files

| Raw file | Official source |
| --- | --- |
| `pa_assessment_2025.xlsx` | [2025 PSSA school results](https://www.pa.gov/content/dam/copapwp-pagov/en/education/documents/data-and-reporting/pssa-and-ayp-results/2025-pssa-school-level-data.xlsx) |
| `pa_income_2025.xlsx` | [2024–25 public school individual low-income enrollment](https://www.pa.gov/content/dam/copapwp-pagov/en/education/documents/data-and-reporting/loan-cancellation/public/2425%20public%20schools%20percent%20low%20income.xlsx) |
| `pa_grades_2025.xlsx` | [2024–25 public school October grade enrollment](https://www.pa.gov/content/dam/copapwp-pagov/en/education/documents/data-and-reporting/enrollment/public-school/enrollment%20public%20schools%202024-25.xlsx) |
| `pa_pims_2025.pdf` | [2024–25 PIMS manual volume 1, v1.1](https://www.pa.gov/content/dam/copapwp-pagov/en/education/documents/data-and-reporting/pims/pims-manuals/2024-2025%20pims%20manual%20vol%201.pdf) |

The files are linked on the official
[assessment reporting](https://www.pa.gov/agencies/education/data-and-reporting/assessment-reporting)
and [enrollment](https://www.pa.gov/agencies/education/data-and-reporting/enrollment)
pages. The committed compact extract records URLs, SHA-256 checksums, retrieval
date, raw cells and original worksheet row numbers. Raw downloads are ignored.

## Individual economic status, including CEP schools

The full `2025 LIP by School` worksheet reports October 1, 2024 total enrollment
and low-income enrollment. Do not use the separate worksheet filtered to schools
above 30% for the model. The underlying field is the PIMS Student Snapshot's
individual economic-disadvantage code, field 88.

PIMS 2024–25 manual printed page 160 identifies permissible poverty sources such
as TANF, census poor, Medicaid, neglected/delinquent institutions and foster
homes; reliable recent FRPL eligibility is a fallback. At CEP schools, field 88
must use individual poverty sources and cannot be set from universal free-meal
eligibility. Food-program eligibility is the separate field 131. This distinction
is also explained by the official
[CEP reporting instructions](https://www.pa.gov/agencies/education/programs-and-services/schools/food-and-nutrition/resources/community-eligibility-provision/reporting-student-data).

The denominator includes pre-K/kindergarten categories where enrolled, unlike
Iowa's K–12-only income denominator. The importer requires income enrollment to
equal all same-year grade counts. The source proportion truncates to four decimal
places (`71 / 996` is published as `.0712`); the model uses exact low-income count
divided by total enrollment. No CEP multiplier is used, and no missing income is
replaced by enrollment or another year's value.

Local poverty-source choices can vary. These are reported state-specific economic
status counts, not one uniform FRPL threshold or direct family income. Reporting
coverage and undercount are unknown. A published numeric zero is retained; an
absent record is unavailable.

## PSSA outcome and valid denominator

Use only `Group=All Students`, `Grade=Total` for Math and English Language Arts.
The native totals span each school's tested PSSA grades 3–8. The model uses
`Percent Proficient and above` exactly as published, with its one-decimal
rounding. It does not sum separately rounded Advanced and Proficient percentages,
average grade percentages, or infer integer proficient counts from the rate.

`Number Scored` is the published scored-assessment denominator. Performance-level
percentages reconcile to 100 and Advanced + Proficient reconciles to the published
combined proficiency within source rounding. Eligible totals have at least 11
scored students. Below that threshold, the source retains a scored count but masks
the rates; the adapter preserves the missing rate and does not reconstruct it
from other rows.

The workbook notes exclude students who enrolled after October 1, homeschoolers,
students excluded from school aggregation, ELL students enrolled for less than
one year, LIFE students entering EL after the prior testing window, and students
who did not attempt. The snapshot therefore differs from an all-spring-testers
population. PSSA is the general assessment; PASA alternate assessment and Keystone
end-of-course exams are outside this release.

The full October grade registry determines membership. Any enrolled grades 9–12
exclude the school from this grade-school cohort. Native PSSA totals for those
high/mixed-grade schools remain in the reproducible source extract but are not
pooled into the grade-school model. No filter refits this population.

Each subject has its own externally studentized model. Combined is the equally
weighted mean of math and ELA rates, not the proportion proficient in both. All
eligible schools have verified scored denominators, permitting the existing
sampling-interval propagation. Source percentage rounding is retained and not
modeled separately in those intervals. Enrollment never replaces scored counts.
These associations do not estimate causal school effectiveness or overall quality.

## Stable identity, coverage and map limits

Identity is nine-digit AUN plus school number normalized to nine digits. For
example, numeric enrollment school `7302` and PSSA `000007302` both become
`112011103-000007302` under the same authoritative AUN. No name matching is used.
Twenty-seven school-number-zero rows describe intermediate units rather than
school buildings, and are excluded with the raw rows retained for audit.

| Coverage | Count |
| --- | ---: |
| Public enrolled school records | 3,389 |
| Grade-school profiles | 2,172 |
| High/mixed-grade schools outside this cohort | 1,217 |
| Eligible Math / ELA / Combined members | 2,008 / 2,008 / 2,008 |
| Grade-school income not reported | 55 |
| Native PSSA total not reported, each subject | 161 |
| Native PSSA rate suppressed, each subject | 3 |
| Assessment totals without same-year enrolled school ID | 0 |

Exclusion categories overlap. All 164 grade-school profiles without a Combined
metric retain a specific explanation. Coordinates are unavailable because this
release has no imported authoritative state-to-NCES coordinate crosswalk. Missing
locations do not alter eligibility; all schools remain available in the list and
charts. This is one year, with no fabricated history.

## Rebuild

Download the four official files above to their raw names, then run:

```sh
.venv/bin/python scripts/prepare_pennsylvania.py --extract
.venv/bin/python scripts/prepare_pennsylvania.py
.venv/bin/python -m unittest discover -s tests -p test_pennsylvania.py -v
```

The default command rebuilds offline from `data/source/pennsylvania.json`. It
replaces only the `pa-pssa` canonical SQLite dataset and writes static school,
history, coverage and catalog JSON. The descriptor includes its preparation
script for the shared audited-state rebuild. The catalog exporter checks canonical
models and files before advertising it as ready.
