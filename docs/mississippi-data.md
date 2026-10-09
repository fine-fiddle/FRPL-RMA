# Mississippi 2024–25 data

The `ms-maap-dc-2025` snapshot fits separate Mississippi regular MAAP Math, ELA and Combined models against individual same-year CCD direct certification. It contains 511 operational grade-school profiles: 354 have Math, 413 ELA and 339 Combined. Complete visible valid-score counts support propagated sampling intervals. This conservative population excludes high schools, protected or incomplete grade distributions, and grade-school subjects with unexpected EOC rows. It does not cover every public school. Individual DC is narrower than full FRPL eligibility. State thresholds are not a national scale; associations do not measure causal effectiveness or overall school quality.

## Native counts and academic year

The [official SPP/APR publication page](https://mdek12.org/specialeducation/spp-apr/) explicitly labels the [School MAAP Proficiency workbook](https://mdek12.org/wp-content/uploads/sites/39/2026/02/School-MAAP-Proficiency.xlsx) **Assessment Public Reporting 2024–2025 School MAAP Proficiency**. This accessible 480,470-byte workbook contains 10,796 rows, including 5,432 All-student rows and 5,364 Students with Disabilities rows. Its exact header is:

```text
YEAR, Subject, District ID, District, School ID, School,
Student Group, Grade, Assessment Type, Number Proficient, Number Not Proficient
```

All rows carry the native academic **start year `2024`**, not ending year 2024. The publication label and native report-card year selector establish that this means 2024–25. All assessment types are `Regular Assessment`. Subjects contain padded `MATH`, `ELA` and `SCIENCE` strings; grades are `03`–`08` or `HS`. The adapter keeps raw values and source row numbers, selects the `All` group and constructs only complete grade 3–8 Math/ELA responses. The Students with Disabilities subgroup is not added to All, and alternate MAAP-A files are not blended into the regular response. Proficient means MAAP Level 4 or 5; Level 3 “Passing” does not meet this criterion.

The four-digit district and three-digit school codes are authoritative strings with leading zeros. For example `4820` / `006` joins exact same-year CCD `ST_SCHID=MS-4820-4820006`; the browser profile is `4820-006`. All 788 native All-student school IDs match the historical CCD directory. No school identity is inferred from a name. The directory supplies names, district, city and historical grade offers. Of those profiles, 277 are outside the verified grade-school population. Retention requires operational status and complete unadjusted offered/enrolled grade data with maximum grade 8, no high-school/adult programs, and enrollment totals reconciled across every grade. There is no current-directory or earlier-year fallback.

Each subject must contain exactly one regular-assessment All-student row for **every** grade 3–8 offered or positively enrolled in the same-year directory/membership records. Every row must expose both integer proficient and not-proficient counts. The school response is `100 × sum(proficient) / sum(proficient + not proficient)`, rather than an unweighted average of grade percentages. At Aberdeen Elementary (`4820-006`), native ELA grade 3 is 17 proficient + 44 not proficient, and grade 4 is 20 + 40: the response is exactly `37 / 121`, not the accountability or report-card performance rate.

The whole subject is unavailable when a required grade is absent, a count is `NR`, ranged, inequality-masked or missing, or an unexpected grade/EOC row appears. The latter conservative rule avoids quietly turning grade Math into a mixed grade/EOC measure. Math excludes 118 profiles for protected counts and 39 for incomplete/extra grades; ELA excludes 95 and 3 respectively. No hidden counts are inferred from the other subject, participation, complementary groups, rounded percentages or nearby source versions.

## Valid-score evidence

The [October 2025 assessment collection protocol](https://mdek12.org/wp-content/uploads/sites/39/2026/02/C-Protocol-618-Assessment-REVISED.pdf), printed pages 8–9, describes vendor-certified score records and explicitly excludes voided, incomplete and irregular tests before further processing. Duplicate records are reviewed for the valid score. Final warehouse records exclude invalid scores and are the authoritative source for EDFacts achievement files and public reporting. Printed page 13 says the SPP/APR spreadsheets align with submitted EDFacts data.

The [October 2025 Indicator 3 protocol](https://mdek12.org/wp-content/uploads/sites/39/2026/02/K-Protocol-Indicator-3-Assessment-REVISED.pdf), printed pages 1–2 and 5, defines proficiency against **valid scores with assigned proficiency**, includes students with and without a full academic year, and identifies FS175/178 achievement data separately from FS185/188 participation. Enrollment, participation and the federal 95% rule therefore do not supply these denominators.

The independent [2024–25 SPP/APR](https://mdek12.org/wp-content/uploads/sites/39/2026/08/MS-01-SPP-PART-B-FFY-2024-25-3833-20260622085050.pdf), printed pages 35–36, explicitly lists All-student valid-score counts. They exactly match proficient plus not-proficient counts in the [native state workbook](https://mdek12.org/wp-content/uploads/sites/39/2026/02/State-MAAP-Proficiency.xlsx): ELA grade 4 **30,437**, grade 8 **32,025**; Math grade 4 **30,404**, grade 8 **32,009**. This cross-check is enforced in normalization. Native HS values differ slightly from the later APR; HS rows are outside the response and no version backfill is made.

Every eligible model member has the complete verified denominator for its subject. Combined uses the equally weighted mean of Math and ELA proficiency, not a count pooled across subjects or a percentage proficient in both. Interval propagation uses every member of each fitted model. Externally studentized residuals do not supply enrollment adjustment or shrinkage.

## Income eligibility

The model uses reported school-level CCD 2024–25 `Direct Certification / Education Unit Total` divided by positive reported same-year `Membership / Education Unit Total`, including pre-K where enrolled. Both counts must carry the Reported flag, match the same NCES and state school identities, and have DC no greater than membership. All 511 retained profiles have usable counts.

The [official 2024–25 administrator calendar](https://msachieves.mdek12.org/wp-content/uploads/2024/07/2024-25-Administrator-Calendar-Dates-to-Remember.pdf) repeatedly requires direct-certification matches for SNAP-eligible students with weekly file updates. The [NCES individual DC definition](https://nces.ed.gov/learn/blog/understanding-school-lunch-eligibility-common-core-data) separates individual benefits eligibility from schoolwide universal meal access. DC is a benefits-based proxy and excludes students eligible only through household-income applications. No CEP claiming multiplier, universal-meal count, FRPL fallback or prior-year count is used. CCD membership is a fall snapshot; the same academic year does not imply identical collection dates.

The [final same-year CCD notes](https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx) identify one Mississippi school, NCES `280119401201`, whose LEA did not report any free/reduced lunch counts, causing DC to exceed Free Lunch Qualified. This note does not mean DC exceeds enrollment, and does not justify replacing individually reported DC with all meals. The full note is retained in the extract.

## Audited alternative sources

The public [native report-card workbook](https://msrc.mdek12.org/downloads/2024-2025ReportCardData.xlsx) is accessible and has 855 All-student school profiles. Its `Math Proficiency` / `English Proficiency` fields are accountability measures and are distinct from its five-level performance fields. For example Aberdeen Elementary shows Math accountability 45.5%, native performance Levels 4+5 43.9%, and regular-only grade-count proficiency `54 / 121 ≈ 44.63%`. These are distinct populations, not interchangeable rounding versions. The report-card guide privacy-buckets entire level distributions where necessary. Those ranges are never converted to point estimates, even if some counts remain visible. Neither report-card field supplies this adapter’s response.

The [2025 MAAP media file](https://mdek12.org/wp-content/uploads/sites/33/2025/08/2025_maap_mediafile_ELA_MATH.xlsx) provides first-time grade-specific rates and counts but omits authoritative school IDs, and some counts differ from the SPP/APR population. The adapter does not join by name or blend these versions. Both alternative files are checksummed audit evidence, not modeled inputs.

Normal direct requests with generic user agents returned HTTP 403 for some MDE files; the public browser and an ordinary current browser User-Agent retrieved the listed official files successfully. This is not a source-access blocker.

## Rebuild and verification

The compact committed extract preserves native counts, every All-student row, source row numbers, historical directory/grade/income records, independent state-count checks and source URLs/checksums. Raw official downloads remain ignored under `data/raw`. Default rebuilding is offline:

```sh
.venv/bin/python scripts/prepare_mississippi.py
.venv/bin/python -m unittest discover -s tests -p test_mississippi.py -v
```

`--extract` reads the raw files listed in `data/source/mississippi.json`. `--database PATH` supports an independently initialized SQLite store. Tests reject missing or duplicate grades, protected counts, unexpected EOCs, incorrect year/IDs, nonreported DC and independent APR disagreements. They verify exact count aggregation, interval availability and deleted-school OLS studentization for each model. Repeat import/output hashes, unrelated canonical observations, Chicago outputs and foreign keys are checked before integration. Map coordinates are unavailable; schools remain accessible in lists and charts. History contains only 2025.
