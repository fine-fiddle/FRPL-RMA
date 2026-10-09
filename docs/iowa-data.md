# Iowa 2024–25 grade schools

The Iowa snapshot fits three separate subject models to public grade schools
with complete grades 3–8 score counts and same-year individual lunch eligibility.
It includes ISASP and DLM, as published in the source workbook. It does not pool
Iowa with another state's assessment standards.

## Official sources and reproducibility

All numeric sources are linked on Iowa's
[PK–12 Education Statistics](https://educate.iowa.gov/pk-12/data/education-statistics)
page. The extract records retrieval date, source URL, SHA-256 checksum, original
row number and raw cells. Downloaded files stay in ignored `data/raw/`.

| Local raw file | Official source |
| --- | --- |
| `ia_assessment_2025.xlsx` | [2024–25 proficiency by public school](https://educate.iowa.gov/media/11702/download?inline=) |
| `ia_income_2025.xlsx` | [2024–25 individual FRL eligibility by school](https://educate.iowa.gov/media/11022/download?inline=) |
| `ia_grades_2025.xlsx` | [2024–25 public school fall grade enrollment](https://educate.iowa.gov/media/10910/download?inline=) |
| `ia_directory_2025.xlsx` | [2024–25 public school directory](https://educate.iowa.gov/media/10250/download?inline=) |
| `ia_cep_reporting.pdf` | [CEP and SRI individual eligibility reporting](https://educate.iowa.gov/media/6358/download?inline=) |
| `ia_sri_dictionary.pdf` | [Current SRI data dictionary](https://educate.iowa.gov/media/8703/download?inline=) |

The current dictionary URL is mutable: the October 9, 2026 download is the
2026–27 edition, revision August 14, 2026, although search metadata still calls
it 2025–26. It is supporting reporting guidance, not numeric data for 2024–25.
The separate CEP/SRI guidance predates this snapshot and explicitly distinguishes
individual eligibility from participation at universally free-meal schools.
No income is backfilled from either guidance document or a different year.

## Income definition

The source uses the 2024–25 Fall Student Reporting in Iowa file. The denominator
is school K–12 enrollment; pre-K is excluded. Eligibility is the sum of individual
free and reduced-price lunch eligibility counts. A child reported eligible for
both is counted once under free. The importer validates the count sum and the
published percentage (rounded to two decimals), then uses the exact count ratio.
K–12 enrollment must equal the same-year grade file's KG through grade 12 sum.

Iowa's CEP/SRI instructions require individual household income information and
direct certification. A school's CEP status does not make every student eligible.
The workbook preserves its CEP flag; the adapter applies no claiming multiplier.
Nonresponse or incomplete reporting may undercount eligibility. Its magnitude is
unknown. This is an eligibility proxy, not direct family income.

The workbook masks counts for enrollment below 10. It also masks counts and
reports inequalities when FRL is at or below 10% or at or above 90%. `***`, `≤ 10`
and `≥ 90` remain unavailable; none becomes zero or a boundary estimate.

## Assessment and model population

The ELA and Math sheets each provide nine grade blocks, grades 3–11. Each block
contains Not Proficient, Proficient, Total Tested and % Proficient. This release
uses grades 3–8 for schools with no enrolled grades 9–12 in the same-year fall
grade file. Schools with any high-school grade enrollment are outside this
snapshot. The grade-school directory includes schools with no tested grades,
with explicit exclusions; UI filters do not refit the population.

Workbook notes say these assessment results include ISASP, DLM alternate
assessment and Partial Academic Year students, and exclude English learners in
their first or second year enrolled in the US. `small N` means total tested
below 10. These are the workbook's published assessment results, not an
accountability performance index or a federal 95%-participation measure.

For every numeric grade the importer verifies Not Proficient + Proficient =
Total Tested, with the published percentage agreeing within its one-decimal
rounding. A numeric zero tested block has zero proficient and no percentage.
All six blocks must be complete or published zeros. Any masked grade invalidates
the school subject aggregate; suppressed counts are never inferred, and an
unsuppressed subset of grades is never substituted for the full school result.
School rates are exact summed proficient / summed tested ratios. Rounded grade
percentages are not averaged.

Math, ELA and Combined have separate models. Combined is the equally weighted
mean of math and ELA rates. Residuals are externally studentized using the entire
eligible population. Every eligible member has complete valid-score counts, so
the existing interval propagation can operate for all three models. Enrollment
never substitutes for a score denominator. These associations do not estimate
causal school effectiveness or overall school quality.

## Identity, coverage and locations

School identity is the composite four-digit District Code and four-digit School
Code (`0009-0409`, for example). Building codes repeat among districts. Never
join by school name, building code alone, or a stripped numeric identifier.
Leading zeros and both source identity fields are preserved. Seven `0000`
building rows represent district-level enrollment, not schools, and are excluded.

| Coverage | Count |
| --- | ---: |
| Public school enrollment records | 1,550 |
| Grade-school profiles | 1,186 |
| High or mixed-grade schools outside this snapshot | 364 |
| Eligible Math / ELA / Combined members | 795 / 795 / 795 |
| Grade-school income not reported | 274 |
| Grade-school FRL suppressed | 41 |
| Assessment not reported, each subject | 334 |
| Incomplete masked grade aggregates, each subject | 25 |

Income and assessment exclusions overlap. They must not be added together as
distinct unavailable-school counts. Most income-absent profiles are pre-K-only
sites because income enrollment covers K–12. The release retains these profiles
and their exclusions instead of manufacturing income or scores.

The exact-ID directory supplies city/county descriptions. Coordinates have not
been imported because no verified NCES/state-ID crosswalk accompanies these
workbooks. All schools remain available in the list and charts; the catalog
explicitly marks maps unavailable. The missing locations do not alter eligibility.
This release contains one year, so there is no invented history segment.

## Rebuild and checks

Download the six files above to their listed raw names. The standard HTTP file
downloads worked with a browser User-Agent; the portal HTML itself returned 403
to the default Python User-Agent. No private or student-level data is required.

```sh
.venv/bin/python scripts/prepare_iowa.py --extract
.venv/bin/python scripts/prepare_iowa.py
.venv/bin/python -m unittest discover -s tests -p test_iowa.py -v
```

Without `--extract`, the importer rebuilds offline from committed
`data/source/iowa.json`. It replaces only its own `ia-isasp-dlm` SQLite rows.
Its catalog descriptor is `data/iowa/catalog.json`; the shared catalog exporter
checks its database models and referenced files before advertising readiness.
