# New York statewide, 2024–25

This snapshot adds statewide public and charter school coverage from NYSED. It preserves the existing NYC release, its different economic-need indicator and its separate NYSTP/Regents populations. New York statewide comparisons are not interchangeable with NYC or other states.

## Sources and identity

The [NYSED downloads page](https://data.nysed.gov/downloads.php) publishes the [Report Card Database](https://data.nysed.gov/files/essa/24-25/SRC2025.zip) and [Enrollment Database](https://data.nysed.gov/files/enrollment/24-25/ENROLLMENT_2025.zip). The downloaded report database is `SRC2025_Group4.mdb`, with a ReadMe last modified July 30, 2026; the enrollment database is `ENROLL2025_20251217.mdb`, with its December 17, 2025 ReadMe. Both include earlier years; the adapter selects only `YEAR=2025`, explicitly meaning 2024–25.

The exact 12-digit BEDS `ENTITY_CD` joins same-year public-school directory, BEDS-day grade enrollment, demographic factors and annual assessment totals. The directory's eight-digit district code and published county/name fields provide display metadata. Names never establish identity. State, district, county and needs-group aggregate rows absent from the same-year school directory are excluded.

## Economic disadvantage

`Demographic Factors.NUM_ECDIS` divided by `BEDS Day Enrollment.K12` supplies the predictor. The enrollment ReadMe defines both as K–12, including ungraded pupils and excluding pre-K. Enrolled grade counts must sum exactly to `K12`. Published `PER_ECDIS` must reconcile within its whole-percent rounding precision; the exact count ratio retains greater precision.

The [2024–25 SIRS manual](https://www.nysed.gov/sites/default/files/programs/information-reporting-services/sirs-manual-2024-2025.pdf), printed pages 59 and 253, defines poverty service code 0198 through individual/family participation in FRPL, SSI, SNAP, foster care, refugee assistance, EITC, HEAP, Safety Net Assistance, BIA or TANF. This is broader than FRPL. For CEP schools, NYSED requires actual individual eligibility through direct certification and alternate income forms; universal meals alone do not identify poverty. The manual also permits a 60-operating-day eligibility carryover for 2024–25. That native reporting rule is retained as part of this same-year measure; the adapter never joins prior-year school income.

The enrollment ReadMe suppresses these demographic counts for groups under five or equal to total K–12 enrollment. Blank counts or percentages remain unavailable, including apparently 100% schools. No count is inferred from a percentage or complementary subgroup.

## Outcomes and populations

`Annual EM ELA.ELA3_8` and `Annual EM MATH.MATH3_8`, subgroup `All Students`, are directly published school totals. The report ReadMe, pages 17–18, defines `NUM_TESTED` as students with valid scores and `NUM_PROF` as those scoring Levels 3–4 in ELA or Levels 3 and above in math. Math's native total includes middle-grade Regents results. NYSAA alternate results occupy a different table and are excluded.

Proficiency is the exact native `NUM_PROF / NUM_TESTED` ratio. It must agree with `PER_PROF` within the displayed whole-percent rounding precision. Available complete performance-level counts must reconcile too. `TOTAL_COUNT` includes students without valid scores; neither that field nor participation/enrollment counts replaces `NUM_TESTED`. No grade percentages are averaged and no suppressed count is recovered from other cells. Native assessment suppression begins below five; the site's existing minimum of ten valid scores additionally applies.

| Population | Directory | Math model | ELA model | Combined model |
| --- | ---: | ---: | ---: | ---: |
| Ordinary grade schools | 2,634 | 2,506 | 2,573 | 2,505 |
| Mixed-grade schools, grades 3–8 outcomes | 1,035 | 797 | 940 | 797 |

Ordinary grade schools have known enrolled grades 3–8 and no grade 9–12 or ungraded-secondary enrollment. Mixed-grade schools have grades 3–8 plus high-school or ungraded-secondary pupils and form separate models in a separate region. Their outcomes still cover grades 3–8, not high-school achievement. Pure high schools and schools without known enrolled grades 3–8 are excluded. All school-level income percentages describe enrolled K–12 pupils, so their population can differ from tested grades.

Each population has separate math, ELA and Combined models. Combined equally weights the two subject rates. Externally studentized residuals describe associations, not causal effects or school quality. All eligible members have verified valid-score counts, supporting the site's conditional sampling intervals. State thresholds remain separate; there is no national ranking. This release has one year, no verified admissions classifications and no imported coordinates.

## Rebuild and verification

The committed [normalized extract](../data/source/new-york.json) retains native identity/year cells, exact counts, rounded published percentages, suppression, whole-school grade membership, source row numbers, URLs and archive/manual SHA-256 hashes. Raw ZIPs, MDBs and exported CSVs remain ignored under `data/raw/`.

```sh
.venv/bin/python scripts/prepare_new_york.py
.venv/bin/python scripts/export_catalog.py
```

To reproduce the extract from the downloaded official ZIPs and manual, install `mdbtools` and run:

```sh
.venv/bin/python scripts/prepare_new_york.py --export-tables
```

`--extract` normalizes already exported raw CSVs without downloading. Offline rebuilds need neither `mdbtools` nor network access. Tests verify native totals and exact same-year identity, valid scores versus participation, income suppression, ordinary/mixed-grade separation, independent deleted-school regressions and repeat import preservation of unrelated datasets.
