# Utah native 2024–25 data

**Audit pending:** this adapter and its numerical exports are held out of the ready catalog. The workbook's native Percent Proficient definition still needs documentary confirmation that it measures assessed performance rather than the federal 95%-adjusted achievement indicator. `release_status` is preserved as `audit_pending` across offline rebuilds. Numerical repeatability does not establish that measurement definition.

The Utah release uses USBE's published school-level RISE grades 3–8 and Utah Aspire Plus grades 9–10 proficiency fractions, joined to individual NSLP meal eligibility in schools outside CEP and Provision 2. These are separate Utah models for each assessment and subject. The comparison population is restricted to eligible NSLP schools; it does not represent every Utah public school.

## Official sources and school identifiers

[USBE Data and Statistics reports](https://schools.utah.gov/datastatistics/reports) links the following native files, retrieved October 9, 2026:

- [2025 RISE/Aspire proficiency rates](https://schools.utah.gov/datastatistics/_datastatisticsfiles_/_reports_/_assessments_/RISEAspireProficiencyRates2025.xlsx), created November 19, 2025. `Results by School` supplies School Year, Assessment Type, District ID, SchoolID, SchoolNumber, Subject Area and Percent Proficient. The release includes RISE ELA results omitted from the earlier September release.
- [October 31, 2024 CNP survey](https://schools.utah.gov/datastatistics/_datastatisticsfiles_/_reports_/_cnpnslp_/CNP%20October%20Survey%202024.xlsx), sheet `CNP October Survey SY25`. USBE describes this annual survey as the free, reduced-price and paid eligible students enrolled in schools operating NSLP, measured on the last operating day of October. The native table supplies Sponsor Number, Site Number, Enrollment and eligibility percentages. Enrollment is the NSLP site population, not a valid-score denominator.
- [Complete SY2025 CEP/Provision school roster](https://schools.utah.gov/datastatistics/_datastatisticsfiles_/_reports_/_cnpnslp_/CEP2025Provision.xlsx), dated September 18, 2024, with 78 actual program records. It identifies CEP formula claiming percentages and Provision 2 base-year percentages separately. It also warns that some CNP identifiers differ from USBE identifiers. The May 2024 [annual CEP notification](https://schools.utah.gov/datastatistics/_datastatisticsfiles_/_reports_/_cnpnslp_/CEP2025Notification.xlsx) contains proxy eligibility and is not used as a participation roster or income source.
- [Official school directory](https://www.schools.utah.gov/schoolsdirectory), whose native page explicitly loads the [CACTUS school API](https://cactus.schools.utah.gov/api/legacy/schools?overrideCache=true). The API binds internal SchoolID and DistrictID to the authoritative districtNumber and schoolNumber site codes. Its current grades and closure flags are not treated as 2024–25 membership; this matters for the subsequent Alpine district split.
- [Public USBE reportcard inventory](https://reportcard.schools.utah.gov/). Every imported selector URL explicitly contains `schoolyearendyear=2025`, SchoolID, DistrictID, SchoolNbr, SchoolLevel and IsSplitSchool. The same-year selector and CACTUS record must reconcile all three internal identifiers exactly. The former supplies school names and year-specific classification; the latter supplies the authoritative site-code crosswalk.

The canonical school key is DistrictID plus SchoolNumber, such as `480-102`. SchoolID is independently verified and retained in provenance. SchoolID alone is not a unique site identifier: six native inventory groups reuse it for elementary and secondary school-number units. Individual NSLP eligibility is excluded for those ambiguous units rather than assigning one site percentage to both populations. Names never establish a join.

The inventory supplies 1,026 school selector records; nine have no exact native crosswalk and remain excluded. The imported directory has 1,017 records. Of 978 native NSLP site records, 923 match an imported school exactly; 55 unmatched or ambiguous records retain their raw data in the source extract. This includes several charter site codes Excel converted into numeric scientific notation, such as `3E-100`. These IDs are unavailable and are never reconstructed from a school name, sponsor or a numeric value.

## Individual income eligibility and program exclusions

The October survey explicitly marks CEP schools with `*` and Provision 2 schools with `**`. Its footnotes explain that these rates can apply a formula or a base-year claiming percentage to current enrollment instead of recording current individual eligibility. Every marked site is excluded, including base-year program sites. The separate complete SY2025 program roster supplies a second exclusion check; absence of a survey flag cannot override a roster match. There are 72 matched program sites and five matched sites with unresolved shared-SchoolID units. Neither category enters a regression.

For remaining sites, `Free and Reduced %` is the published individual eligibility fraction. Free plus Reduced must reconcile to the combined fraction within the native four-decimal rounding precision. Enrollment must be a positive exact integer. The published fraction is retained; eligible counts are unavailable and are never manufactured by multiplying a rounded rate by enrollment. Suppressed eligibility, missing enrollment and absent NSLP sites remain missing.

Other Utah income sources were audited and rejected for this release. The same-year October enrollment workbook has economic-disadvantage counts but only school names, without authoritative identifiers. The native reportcard demographic chart has no verified population denominator and can differ substantially: Academy Park's 2024–25 profile shows 72% while the October membership table reports 169 of 323, approximately 52.3%. Those sources are not joined by name or substituted for individual NSLP eligibility. National CCD FRPL collection provenance is still unapproved for Utah and is not used.

## Assessments, suppression and regression populations

[RISE](https://schools.utah.gov/assessment/assessments/rise) and [Utah Aspire Plus](https://schools.utah.gov/assessment/assessments/utahaspireplus) measure their respective Utah grade-level standards. The extract retains the source's English Language Arts and Mathematics rows for school year 2025. It uses the native aggregate for each assessment; it never combines RISE with Aspire or averages individual grade percentages. Native `Overall Results`, science, ACT and DLM are excluded. This one-year release makes no historical standards-continuity claim and does not put the two assessments on a common proficiency scale.

Grade-school models use RISE only in schools classified K8, not split-grade, and without a native Aspire record. A native Aspire row establishes high-school grade presence even when the inventory calls a grade-7–9 junior high K8. Schools flagged HS, split-grade or having Aspire results appear only in the high-school list and use Aspire grades 9–10. Their lower-grade RISE rows are excluded. This preserves the grade-school filter's exclusion of high-school grades. There are 335 excluded RISE subject rows from high or mixed-grade schools.

The workbook's FERPA notes suppress groups below ten and replace small-group or extreme percentages with ranges. All text ranges, bounds and missing fields are unavailable; they are never turned into zero, a midpoint or a bound. Exact numeric native proficiency fractions, including numeric zero if published, are retained.

The school table has no verified valid-score count. The separate proficiency-level workbook has school percentages but does not expose audited same-year school valid-score counts; its undocumented `Sheet1` contains older-style grade-11 and SAGE test categories and is not used. Enrollment, expected participation and counts from national proxies are not substituted. Utah accountability documentation applies a 95% participation rule to its federal achievement indicator and distinguishes that from state calculations. The adapter does not reconstruct either measure or claim that the workbook fractions are a separately verified tested-only rate. Every tested count and every sampling interval remains unavailable.

The [2024 Accountability Technical Manual](https://reportcard.schools.utah.gov/Documents/AccountabilityTechnicalManual2024.pdf), page 15 and footnote 2, explicitly describes a 95% denominator rule for the achievement indicator and a full-academic-year requirement of 160 days. Those accountability rules cannot simply be assumed to define the separate Data and Statistics proficiency workbook. Its November 2025 notes identify the year, revision and privacy rules but do not specify whether the published fractions apply the participation adjustment, full-academic-year restrictions or another valid-score exclusion. The December 2025 level workbook likewise has no such definition. This is the remaining documentary obstacle, checked October 9, 2026.

There is a concrete unresolved corroboration issue. The rates workbook's state RISE ELA row reports 123,212 proficient and 285,367 tested, but publishes 0.433240973853359 rather than the simple ratio 0.4317668125606675. Math similarly publishes 0.445650162291441 rather than 125,217 / 282,628 = 0.4430452750612112. State Aspire fractions reconcile exactly to the corresponding counts. Proficiency-level percentages differ from the rates in some school and state records. Higher published RISE fractions are inconsistent with applying a 95% penalty to those same numerators and denominators, but that inference is not conclusive evidence of the workbook definition. Readiness remains held pending confirmation of the native measurement and its exclusions.

There are six externally studentized models. Math, ELA and Combined are separate within RISE and Aspire. Combined is the equally weighted mean of the two eligible subject percentages. The Combined populations contain 589 grade schools and 205 high schools. UI filters do not refit these models. Exclusions and per-subject coverage are saved in `data/utah/audit.json`.

## Rebuild and validation

The committed `data/source/utah.json` contains selected native records, source URLs and SHA-256 hashes, survey/program flags, identity crosswalks, suppression values and the unmatched-record audit. A normal rebuild needs only that committed extract:

```sh
.venv/bin/python scripts/prepare_utah.py
.venv/bin/python scripts/export_catalog.py
```

To refresh the extract, download the five files listed in `FILES` in `scripts/prepare_utah.py` to `data/raw/utah` as `rates.xlsx`, `meal-survey.xlsx`, `CEP2025Provision.xlsx`, `cactus-schools.json` and `reportcard.html`, then run:

```sh
.venv/bin/python scripts/prepare_utah.py --extract
.venv/bin/python -m unittest discover -s tests -p test_utah.py -v
```

The initial build and repeated build used an isolated database, followed by two canonical imports. Eight tests verify native percentages, authoritative IDs, suppression, program exclusions, ambiguous units, cohort separation, repeat import preservation and an independent externally studentized calculation for all six models. All four outputs were byte-identical across the isolated and canonical repeats. Unrelated rows in all nine canonical tables and Chicago schools/history JSON retained identical SHA-256 fingerprints; foreign-key checks were clean. The release provides one year, no admissions classification and no audited historical map coordinates; boundaries remain null.
