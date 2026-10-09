# Texas 2024–25 grade schools

Texas uses a separate statewide grade-school population and its own proficiency
standard. This release matches native TAPR enrolled-grades 3–8 Math and ELA totals
to individual economic status reported for the same fall snapshot.

## Sources and reproducibility

The [2024–25 TAPR portal](https://rptsvr1.tea.texas.gov/perfreport/tapr/2025/index.html)
links a public data download with All Campuses, Reference, Student Profile and
STAAR grades 3–8 categories. The adapter's `download_url` reproduces the form's
public SAS request; exact query URLs and SHA-256 checksums are retained in
`data/source/texas.json`. All 9,084 campus identities match across the three files.
The extract retains original cells, field labels and CSV row numbers.

Additional primary definitions are the
[2024–25 TAPR glossary](https://tea.texas.gov/school-and-district-leaders/accountability/academic-accountability/performance-reporting/2024-25-comprehensive-tapr-glossary-0.pdf),
[2024–25 Texas Education Data Standards](https://www.texasstudentdatasystem.org/sites/texasstudentdatasystem.org/files/TEDS_Data_Submission_Requirements_Student_Identification_and_Demographics_Domain.pdf)
and [2025 TAPR masking rules](https://rptsvr1.tea.texas.gov/perfreport/tapr/2025/masking.html).
Their downloaded bytes also have provenance checksums. Raw files are ignored.

## Individual economic eligibility

The `CPNTALLC`, `CPNTECOC`, `CPNTNEDC` and `CPNTECOP` Student Enrollment fields
describe October 25, 2024, the last-Friday-in-October PEIMS Fall snapshot. Income
is exact economically disadvantaged count divided by enrollment; its one-decimal
display percentage must reconcile. Economic and complementary counts must sum
to enrollment. Early childhood, pre-K and kindergarten are included where enrolled.
Membership fields (`CPET…`) are a different population and are not substituted.

The individual economic descriptor includes free-meal eligibility, reduced-price
meal eligibility and other economic disadvantage/public assistance (01, 02, 99).
TEDS 2024–25, Version 2025.2.0, printed pages 38–40, requires individual direct
certification and annually distributed local income surveys at CEP schools.
Provision 2 retains base-year eligibility for continuously enrolled students and
uses local surveys for new/returning students. This release uses current-year
reported administrative status; Provision 2 eligibility can therefore lag current
family income. Receiving universal free meals does not classify all students as disadvantaged.
Unreturned surveys can result in code 00, so reporting undercount is unknown.
Other assistance makes this a broader state-specific proxy than uniform FRPL.

The official
[2024–25 income verification extension](https://tea.texas.gov/taa-letters/school-year-2024-2025-income-eligibility-verification-forms-extension)
allows collecting eligibility documentation through the January 16, 2025
resubmission deadline, while requiring students to be enrolled and eligible on
October 25, 2024. Income is never backfilled from another year.

## Native outcomes and valid-score counts

Use All Students columns `CDA38AM0E025D`, `CDA38AM0E225N`, `CDA38AM0E225R` for
Math and their `…AR…` counterparts for ELA. They are native enrolled-grades 3–8
subject totals including the corresponding Algebra I or English I/II EOC exams.
The numerator is At Meets Grade Level or Above; the denominator is the number of
tests in this performance calculation. The download's dictionary and glossary
identify these as performance measures, separate from assessment participation.
Exact count ratios replace whole-percent display rounding after reconciliation.

TAPR's performance population is the accountability subset: students at the same
campus on the fall snapshot and testing dates. It includes STAAR with and without
accommodations, Spanish STAAR and STAAR Alternate 2. The separate TPRS all-testers
population is not used. State assessment exclusions still apply. The outcome is
Meets, rather than Approaches or Masters; Texas thresholds are not a national scale.

Missing cells and masking codes -1/-2/-3 are unavailable. A masked rate is never
reconstructed even if other cells could reveal it. The source masks denominators
1–4; the site's existing model policy additionally excludes fewer than 10 scored.
No grade percentages are averaged. The source's percentage passing both Math and
ELA is not used: Combined remains the equally weighted mean of the two subject
proficiency rates. All eligible model members have verified denominators, so the
existing sampling interval propagation applies to the complete model.

## Scope and coverage

Authoritative nine-digit `CAMPUS` IDs preserve leading zeros, with the first six
digits matching `DISTRICT`. Same-year enrolled grade counts determine membership;
pre-K 3/4 subcategories are not double-counted in the enrollment total. A campus
enrolling any grades 9–12 is excluded from the grade-school cohort, including a
mixed-grade campus classified as Elementary/Secondary by the source.

| Coverage | Count |
| --- | ---: |
| Public campus records | 9,084 |
| Grade-school profiles | 6,573 |
| High/mixed-grade campuses excluded | 2,511 |
| Eligible Math / ELA / Combined members | 6,118 / 6,117 / 6,117 |

Missing/masked results and the model minimum of ten scored explain excluded
profiles; every absent metric retains a reason. No coordinate crosswalk is
imported, so school maps are unavailable and list/chart coverage is unaffected.
This is a one-year snapshot. Subject populations are fitted separately using
externally studentized residuals; UI filters do not refit them. Results describe
associations, not causal effectiveness or overall school quality.

## Rebuild

```sh
.venv/bin/python scripts/prepare_texas.py --download
.venv/bin/python scripts/prepare_texas.py
.venv/bin/python -m unittest discover -s tests -p test_texas.py -v
```

`--download` saves the official CSV/PDF/HTML files, extracts compact source JSON,
and imports. `--extract` reuses the saved raw files. Default preparation rebuilds
offline from the committed extract via `state_snapshot.py`, replacing only
`tx-tapr-2025`. The catalog descriptor declares the checked-in preparation script;
shared catalog validation checks SQLite models and exports before readiness.
