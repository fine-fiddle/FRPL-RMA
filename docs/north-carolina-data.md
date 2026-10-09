# North Carolina 2024–25 snapshot

The snapshot uses DPI's **published regular-assessment school totals** for All Students, grades 3–8, joined by exact state school code to **April 2025 individual EDS**. It contains 1,886 grade schools: 1,877 have Math, 1,884 have ELA, and 1,876 have Combined. High schools, mixed-grade schools and history are unavailable.

## Assessment and population

DPI's [Green Book archive](https://www.dpi.nc.gov/districts-schools/accountability-and-testing/school-accountability-and-reporting/state-testing-results-green-book/state-testing-results-green-book-archive) links the [2024–25 disaggregated performance ZIP](https://accrpt.tops.ncsu.edu/docs/disag_datasets/Disag_2024-25.zip). The ZIP contains `Disag_2024-25_Data.txt` and a two-page source description. The selected rows are `subgroup=ALL`, `type=RG`, `grade=GS`, and `subject=MA` or `RD`.

The source description explicitly defines RG as regular multiple-choice assessments, ALL as the composite of assessment types, and NCEXTEND1 as alternate. GS is the native grades 3–8 composite, including NC Math 1 EOC at grade 8. GLP is Achievement Level 3 and above. The adapter preserves `pct_glp` exactly as published; it never averages grade percentages or reconstructs suppressed proficiency from achievement levels. Math therefore includes the state's grade-8 Math 1 substitution and is not solely the grade-8 math EOG population.

The broader report-card `rcd_acc_pc` totals and native `type=ALL` totals include alternate assessments. They are not substituted into this regular cohort. This assessment distinction is established by the native codebook, rather than inferred from differences in rates. The [2025 accountability technical guide](https://www.dpi.nc.gov/dpischoolgradetechnicalguidedraft2024-25/open), sections 3.1–3.1.3, limits the federal 95% denominator adjustment to School Performance Grades and long-term goals and distinguishes test-results reporting. This snapshot uses the disaggregated test performance table, whose description specifies completed tests; it does not use the SPG or long-term-goal tables.

`num_tested` is retained as raw provenance but has not been independently approved as a valid-score sampling denominator. All normalized tested values and all sampling intervals are null. Each subject uses its own eligible school population. Combined is the equally weighted mean of Math and ELA. All three models use externally studentized residuals within this NC cohort.

## Income, identifiers and exclusions

The [DPI EDS collection guidance](https://www.dpi.nc.gov/documents/economically-disadvantaged-data-collection/open) identifies April as the report-card collection and defines a school enrollment denominator that includes currently enrolled PK through grade 13 and ungraded students, with charter pre-K excluded. The adapter reads only `APR 2025` in the [official all-years workbook](https://www.dpi.nc.gov/eds-all-years-spreadsheet/open), preserving the published `pct_eds` and `den` cells. Individual eligibility includes direct certification, qualifying categorical statuses and optional locally verified financial need. CEP participation alone does not make every student individually EDS. `pct_nslp`, `pct_nslp_adj` and tested-subgroup ratios are not used.

The currently published April workbook sometimes differs from the earlier report-card EDS copy by 0.1 percentage points. The committed extract retains the current published precision and workbook checksum; it does not manufacture a low-income student count from this rounded rate. Suppression (`<5`, `>95`, `*`, or `<10` enrollment) remains unavailable. A literal unsuppressed numeric 5 or 95 is preserved.

The authoritative same-year CCD `ST_SCHID=NC-PSU-SCHOOL` components concatenate to the native six-character `school_code`, preserving leading zeroes and charter letters. Names are not used for identity. An exact CCD directory and membership join establishes school grade scope. Unadjusted offered grades must contain no high-school/adult grades, and reported PK–8 grade subtotals must reconcile to reported total membership. The native grade span must also exclude high grades. April EDS enrollment remains the economic denominator; fall CCD membership is used for grade classification only.

The extract excludes 193 mixed/high/adjusted/unknown configurations, 125 units without an exact CCD school identity (including state and district aggregates), and 8 schools with unavailable April EDS/enrollment. Eleven subject rates are suppressed or missing. Every excluded unit and raw source field needed for these decisions is preserved in the committed extract.

## Rebuild and verification

```sh
.venv/bin/python scripts/prepare_north_carolina.py --database data/build/north-carolina-audit.sqlite
.venv/bin/python -m unittest discover -s tests -p test_north_carolina.py -v
```

`--extract` reads the ignored official downloads and regenerates `data/source/north-carolina.json`. Default rebuilding is offline. The adapter was imported twice into an isolated database. Tests independently fit deleted-school regressions, verify studentization and Combined, reject wrong years, alternate/all-assessment substitutions, mixed grade scope, income proxy substitutions, fabricated counts and reconstructed suppression, and verify repeatable import without changing unrelated datasets.
