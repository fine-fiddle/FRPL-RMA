# South Carolina 2024–25 data

The `sc-fay-scored-pip-2025` snapshot fits separate South Carolina Math, ELA and Combined models against individual Day135 Pupils in Poverty (PIP). It retains 831 operational grade-school profiles with a single elementary or middle report card; 819 have usable Math, 821 ELA and 818 Combined. The response is **actual proficiency among scored FAY students**, calculated from independently visible score-level counts, with SC READY and SC-Alt thresholds both explicit. It differs from the published report-card percentage that includes eligible nonparticipants in its denominator. All modeled subjects have complete actual score counts and sampling intervals. PIP has an explicit three-year benefits-eligibility lookback. This conservative subset is not statewide school completeness or a national ranking; associations do not measure causal effectiveness or overall school quality.

## Actual score counts and population

The [official 2025 download page](https://screportcards.com/files/2025/data-files/) provides the [2024–25 research workbook](https://screportcards.com/files/2025/data-files/report-cards-data-for-researchers-2024-25/). The adapter reads `2a.AchievPrepSuccessELEMMIDD`, selecting year 2025 and report types `E`/`M`. It preserves all 180 native fields, source row numbers and all separate report-card records in the compact extract. There are 1,044 E/M records for 952 exact native school IDs. All match the historical 2024–25 CCD directory. Of those, 57 are outside operational grade-school scope and 64 have separate E/M report cards; 831 single-report profiles remain.

For each Math/ELA subject, the source independently publishes:

```text
E_/M_NbrME, NbrExceeding, NbrReady, NbrClose, NbrInNeedOfSupport,
NbrNotTest, NbrTOT, PctME
```

The [historical 2024–25 accountability manual](https://www.eoc.sc.gov/sites/eoc/files/Documents/Acct%20Manual%2024%2025/FINAL%20Accountability%20Manual%20SY%202024-25%20%28UPDATED%202025%2003%2030%3B%20REDLINE%29.pdf), pages 29–31, affirmatively defines four separate achievement-level bins as **students who scored at each achievement level**, with nonparticipants reported separately in **Not Tested**. All native displayed fractions use the eligible indicator denominator, including nonparticipants. The score-level counts remain actual scored students; nonparticipants are assigned zero **indicator points**, not a fabricated achievement-level score. The federal 95% rule changes accountability ratings, and does not supply this adapter's response or denominator.

The adapter calculates:

```text
actual proficiency = 100 × NbrME /
    (NbrExceeding + NbrReady + NbrClose + NbrInNeedOfSupport)
```

All four level counts and the separate `NbrME` numerator must be independently visible, nonnegative integers. ME must exactly equal Exceeding + Ready. The sum must be positive and, when native total and Not Tested are both visible, those bins must reconcile. This uses native schoolwide actual counts rather than averaging grades or inferring protected values. For Diamond Hill Elementary (`0160019`), ELA is exactly **87 / 123 ≈ 70.73%**; native `NbrTOT=124` includes one Not Tested student and native `PctME=70.2%`. The new response deliberately describes the 123 actual scored students. At John C. Calhoun Elementary (`0160007`), `NbrNotTest='*'` remains protected and untouched even though all actual score bins are visible. The adapter never fills that protected cell or uses it as zero.

The source's FAY population is continuously enrolled at the same school from day45 through day160 and in the testing window, subject to authorized documented exclusions. Recently arrived multilingual learners are excluded under the manual rules. Non-FAY scored students are outside this native population. The separate SC READY all-test-taker grade workbook describes a different regular-only population; for Wright Middle it totals 326 ELA test takers, while the research workbook has 309 FAY scored students. Those sources are not spliced together.

Both **SC READY** and **SC-Alt** are included. SC READY Levels 3/4 correspond to Meets/Exceeds Expectations; SC-Alt uses Meets/Exceeds. Their state-defined native performance classifications remain explicit rather than silently treating alternate assessment as regular-only. Grades are 3–8 at schools whose historical offers and complete reconciled enrollment exclude high school, adult and unknown ungraded programs. ELA assesses revised 2023 standards in 2025; the manual pages 15–16 and 29 describe this assessment change. History contains only 2025, with no connection to an earlier standards era.

## Separate report cards and protected counts

Manual pages 20–21 define schools receiving separate report cards for different organizational levels. The native file has 92 repeated E/M school IDs with different grade-specific counts; 64 are otherwise verified grade schools. For example Macedonia Elementary/Middle (`0601003`) has elementary eligible total 92 and middle total 103. A complete, disjoint band-union audit is required before adding these records. The first release conservatively excludes those 64 schools and retains every raw record and exclusion reason. It neither picks one band nor sums partially protected bands. Schools with high-school enrollment are excluded even if an elementary or middle report card exists.

Native `*`, missing, ranges and inequalities remain unavailable. A protected actual bin or ME numerator excludes the whole subject; no lower-bin complement or rounded percentage reconstructs it. There are three protected Math subjects and one protected ELA subject among retained single-report profiles. Nine further profiles have income enrollment reconciliation problems. Every modeled member has a complete actual score denominator. Combined is the equally weighted Math/ELA proficiency mean, not pooled counts or the proportion proficient in both. Interval propagation uses every model member; externally studentized residuals do not provide enrollment adjustment or shrinkage.

## Individual Day135 income

The [official 2024–25 Day135 PIP workbook](https://www.ed.sc.gov/data/other/student-counts/active-student-headcounts/2024-25-active-student-headcounts/135-day-school-headcount-by-gender-ethnicity-and-pupils-in-poverty/) labels **April 2025 QDC3, 135th Day Extraction**. Its numerator is the independently published individual **Pupils in Poverty / Yes** count, and its denominator is the same-record **Total # Actively Enrolled Students**, including pre-K where enrolled. Active/funded status is based on enrollment entry/exit dates, valid entry code and inclusion in state reporting. The [same-day grade workbook](https://www.ed.sc.gov/data/other/student-counts/active-student-headcounts/2024-25-active-student-headcounts/135-day-school-headcount-by-grade/) must agree exactly on enrollment, reconcile the sum of grades and show no high-school enrollment. Both workbooks have the same 1,226 school IDs and integer PIP counts; no numerator exceeds enrollment. Ten statewide records have different enrollment totals across the two files; nine are in the retained single-report population and receive unavailable income.

Manual page 156 defines individual PIP for EFA as transient, runaway, foster or homeless students, or students Medicaid-eligible or qualified for SNAP/TANF **within the last three years**. That benefit lookback is part of the official definition for currently enrolled pupils; it is not importer backfill. This is neither full household-income FRPL nor CCD direct certification, and is not a universal free-meal or CEP claiming percentage. No multiplier, tested-subgroup ratio or earlier-year income is used. The April Day135 income covers the full active/funded school population, while the response is the narrower FAY scored population. Academic year and exact school identity match; collection dates and student populations are not asserted identical.

The separate native published Poverty Index differs from the exact April Day135 count fraction at some schools. For example John C. Calhoun has **98 / 114 ≈ 85.96%** in the selected individual headcount file, while its separately published index is 86.8%. Those collection versions/populations are not interchangeable, and the index never fills or replaces missing counts.

## Identity, rebuild and verification

Native numeric research SIDNs are preserved as raw integers and formatted to the authoritative seven-digit width. Native Day135 IDs already appear as seven-character strings. Both match exact historical CCD `ST_SCHID=SC-district(4)-school(3)`, with no name join, current directory or previous-year fallback. Directory names, district and city are display metadata. Map coordinates are unavailable; lists and charts retain eligible schools.

The committed `data/source/south-carolina.json` preserves all selected native records, duplicates, headcount headers/rows, directory/grade records, URLs and full-file SHA-256 checksums. Raw downloads remain ignored under `data/raw`. Default rebuilding is offline:

```sh
.venv/bin/python scripts/prepare_south_carolina.py
.venv/bin/python -m unittest discover -s tests -p test_south_carolina.py -v
```

`--extract` reads the registered raw files; `--database PATH` supports an independently initialized SQLite store. Tests verify actual score-bin aggregation instead of eligible-denominator rates, protected Not Tested preservation, whole-subject missingness, ME/top-two equality, exact IDs/year, individual PIP bounds/reconciliation, exclusion of separate report cards/high schools, intervals and independent deleted-school OLS studentization. Repeat imports must preserve output hashes, unrelated canonical rows/static JSON, Chicago results and foreign keys.
