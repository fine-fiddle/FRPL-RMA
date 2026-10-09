# Oklahoma 2024–25 data

The `ok-ostp-dc-2025` snapshot fits separate regular OSTP Math, ELA and Combined models against individual same-year CCD direct certification. It preserves 1,205 verified operational grade-school profiles; 344 have usable Math, 169 ELA and 148 Combined. Every modeled subject has complete visible valid-score counts, supporting propagated sampling intervals. Extensive native suppression makes this a conservative subset, not statewide school completeness. The explicit spring 2025 standards reset is not connected to 2024 history. State thresholds are not a national scale, and associations do not measure causal effectiveness or overall school quality.

## Native population and exact identities

The [official testing resources page](https://oklahoma.gov/education/services/assessments/state-testing-resources.html) labels the [native CSV](https://oklahoma.gov/content/dam/ok/en/osde/documents/services/assessments/state-testing-resources/2025-state-testing-resources/2425OKOSTPMediaRedacted.csv) **2025, Grades 3–8, District & School (ELA/Math/Science)**. It contains 7,471 rows, all administration `2425`, grade `03`–`08`. Native identity fields are `Grade`, `CountyName`, `OrganizationId`, `Group`, and `Administration`. For each subject it provides `Total N`, `Valid N`, and four performance-level counts and whole-number percentages. The compact extract preserves all relevant Math/ELA native fields, including protected counts, and source row numbers. Alternate OAAP, science and high-school ACT/CCRA do not supply this response.

Nine-character school codes contain county (2), district (4) and school (3), including leading zeros and district letters. For example `05I006125` joins exact same-year CCD `ST_SCHID=OK-05-I006-05-I006-125`; the browser profile retains `05I006125`. Of 1,221 native school profiles, 1,220 match the 2024–25 CCD directory, one remains unmatched and 15 fall outside the verified grade-school population. Names are display metadata and never identity matches.

School scope requires operational status, reported historical grade offers, maximum grade 8, complete unadjusted enrolled grades reconciled to membership, and no high-school/adult program. Ungraded offers cannot authorize unknown enrolled grades. A subject must expose exactly one native row for every grade 3–8 offered or positively enrolled. There is no current-directory or earlier-year backfill. The response is `100 × sum(Proficient No. + Advanced No.) / sum(Valid N)` across the complete grade set. It is not an unweighted mean of rounded grade percentages. Elk City Elementary (`05I006125`, grade 3) gives ELA exactly `50 / 145` and Math `62 / 145`.

## Verified valid-score denominator and suppression

The [2024–25 technical report Part II](https://oklahoma.gov/content/dam/ok/en/osde/documents/services/assessments/state-testing-resources/24-25%20OK_TechReport_Part-II_AppM-V.pdf), Appendix V **Reporting Business Requirements**, explicitly establishes the source schema and denominator:

- Printed page 14 (PDF 742) defines attemptedness as at least five scorable operational MC/PMC/TEI items, including ELA grades 5/8 even when a writing response exists.
- Printed pages 16–17 (PDF 744–745) distinguish Valid Participant status `Z` from Did Not Attempt, Emergency Exemption, Do Not Report, Invalidated/Breach, No Longer Enrolled, OAAP, duplicates, grade invalidation and voided booklets. Those nonvalid statuses have no performance-level score; final voids are suppressed.
- Printed page 18 (PDF 746) defines `TotalN` to include valid participants and some nonvalid/alternate records, while number tested and performance-level aggregates include **only Valid Participants**. The native other-placement exclusion rules apply to school aggregates. `Total N`, enrollment and participation are not substitutes for `Valid N`.
- Printed page 22 (PDF 750) names the MediaRedacted CSV layout, administration code, grade, OrganizationID, subject `Total N`/`Valid N` and performance counts. It separately defines redaction: small valid or total N, 100% levels, two-level complements and low level counts receive protected cells.

The adapter requires independently published integer `Valid N`, `Proficient No.` and `Advanced No.` for **every required grade**. Missing, `***`, ranged or inequality-masked required counts make the entire subject unavailable. It never derives a hidden count from a rounded percentage or complementary cells. Independently visible Proficient and Advanced counts may be summed while protected Below Basic or Basic values remain protected and unchanged. When all four counts are visible, their sum must agree exactly with Valid N.

Math has 850 profiles excluded for protected required counts and 11 for incomplete grades; ELA has 1,025 and 11 respectively. All 1,205 profiles have individual DC income. Each model's eligible population has complete valid-score counts; interval propagation uses every model member. Combined is the equally weighted Math/ELA proficiency mean, not pooled counts or proficiency in both subjects. Externally studentized residuals do not provide enrollment adjustment or shrinkage.

## Standards reset

The [same-year technical report Part I](https://oklahoma.gov/content/dam/ok/en/osde/documents/services/assessments/state-testing-resources/24-25%20OK%20Tech%20Report%20to%20Appendix%20L.pdf), printed page 20 and page 98, documents that May 2025 CEQA rescinded the 2024 ELA/Math grade 3–8 cut scores and restored the cuts used in 2023, effective for spring 2025. The 2024 performance descriptors remained on the 2025 reports. Proficient plus Advanced therefore has explicit **2025 reset** metadata. It cannot silently continue the 2024 standards era. History contains only 2025.

## Individual income eligibility

The numerator is the reported CCD 2024–25 `Direct Certification / Education Unit Total`, divided by positive reported same-year `Membership / Education Unit Total`, including pre-K where enrolled. Both records must match authoritative NCES/state IDs and academic year; DC cannot exceed membership. The [NCES definition](https://nces.ed.gov/learn/blog/understanding-school-lunch-eligibility-common-core-data) distinguishes individual categorical eligibility from all students receiving free meals at CEP schools. This is a benefits-based proxy narrower than full application-based FRPL; no multiplier, meal-recipient count, FRPL fallback, tested-subgroup ratio or prior-year income is used. CCD membership is fall; same academic year does not imply identical collection dates.

The [official state nutrition page](https://oklahoma.gov/education/services/child-nutrition/documents.html) publishes separate 2025 low-income meal and CEP ISP/proxy-ISP workbooks. The latter distinguishes actual ISP and proxy ISP and explicitly prohibits a 1.6 multiplier in its instructions. Neither workbook supplies this model's income. The [July 2025 state nutrition manual](https://oklahoma.gov/content/dam/ok/en/osde/documents/services/child-nutrition/child-nutrition-documents/school-meal-program-various-documents-forms/2026%20School%20Training%20Manual.pdf), eligibility E-29–E-31, documents individual WAVE certification categories including SNAP, TANF, FDPIR, foster/liaison statuses and Medicaid, separately from applications and universal meal provision. It corroborates individual certification processes but is later than the fall 2024 collection; the adapter does not assert an identical benefit-program mix across those dates.

The [final same-year CCD notes](https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx) say Oklahoma does not currently distinguish Free Lunch and Reduced Price Lunch and reports their combined count as economically disadvantaged. That note is preserved; neither of those categories is this adapter's separately reported DC numerator.

## Alternative download and reproducibility

The official [Report Card download page](https://oklaschools.com/download-data/) exposes a broader 2025 **contextual Assessment Performance** CSV, separate from accountability Academic Achievement. Its ordinary download control successfully downloaded 229,138 rows, published November 26, 2025. The report-card file contains no valid-score count and its public schema uses generic indicator definitions; it is retained as checksummed audit evidence, not a source for filling protected counts or blending populations. The native OSTP grade CSV and same-year reporting rules give a directly verifiable regular-assessment population instead.

Source URLs, full-file SHA-256 checksums, raw values, grade/income/directory records and source row numbers remain in `data/source/oklahoma.json`; raw downloads are ignored under `data/raw`. Default rebuild is offline:

```sh
.venv/bin/python scripts/prepare_oklahoma.py
.venv/bin/python -m unittest discover -s tests -p test_oklahoma.py -v
```

`--extract` reads downloaded files listed in the source registry; `--database PATH` uses an independently initialized SQLite store. Tests verify exact aggregation, whole-subject suppression, protected lower-cell preservation, same-year exact ID joins, DC category and bounds, no-high-school scope, the standards reset, intervals and independent deleted-school OLS studentization. The importer is run twice before integration, with identical output hashes and preserved unrelated canonical rows, static JSON, Chicago results and foreign keys. Map coordinates are unavailable; lists and charts retain eligible schools.
