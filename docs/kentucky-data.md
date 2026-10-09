# Kentucky 2024–25 source audit

Kentucky is not approved for a grade-school snapshot yet. The native assessment file contains individual-grade proficiency percentages without valid-score counts; the native accountability file supplies grade-band totals but has a different denominator policy. No school-total rate or valid weighting has been approved for aggregating grades 3–8.

## Sources inspected

The [official historical SRC index](https://www.education.ky.gov/Open-House/data/Pages/Historical-SRC-Datasets.aspx) exposes these 2024–25 files with consistent `School Code` and `State School Id`:

| File | Relevant fields | Finding |
| --- | --- | --- |
| [ASMT Kentucky Summative Assessment](https://www.education.ky.gov/Open-House/data/HistoricalDatasets/KYRC25_ASMT_Kentucky_Summative_Assessment.csv) | Year, School Code, State School Id, Grade, Subject, Demographic, Suppressed, Proficient / Distinguished | All Students Reading/Mathematics rates are integer percentages at grades 3–8 and 10. No count column or all-grades school total. |
| [ACCT Kentucky Summative Assessment](https://www.education.ky.gov/Open-House/data/HistoricalDatasets/KYRC25_ACCT_Kentucky_Summative_Assessment.csv) | Same identity, Level, Subject, Demographic, Suppressed, Proficient / Distinguished, Content Index | Native elementary, middle and high accountability totals exist, but are not interchangeable with tested-only proficiency. |
| [Overview Economically Disadvantaged](https://www.education.ky.gov/Open-House/data/HistoricalDatasets/KYRC25_OVW_Economically_Disadvantaged.csv) | Year, School Code, State School Id, Demographic, TOTAL COUNT ECON DISADVANTAGED, TOTAL MEMBERSHIP | Actual school enrollment-based economic count and denominator are available; individual eligibility scope still needs a source-specific final audit. |
| [Overview Student Membership](https://www.education.ky.gov/Open-House/data/HistoricalDatasets/KYRC25_OVW_Student_Membership.csv) | Year, school IDs, Demographic, All Grades, Preschool/K/grade counts | Grade enrollment is available, but cannot weight test proficiency. |
| [District School List](https://www.education.ky.gov/Open-House/data/HistoricalDatasets/KYRC25_OVW_District_School_List.csv) | Year, School Code, State School Id, Low/High Grade, school type, coordinates | Exact native state IDs are available. NCES IDs are rounded in the CSV (scientific notation), so they cannot establish an exact federal crosswalk. |

The [February 2025 Kentucky Consolidated State Plan](https://www.education.ky.gov/comm/Documents/Kentucky%20Consolidated%20State%20Plan%20February%202025.pdf), printed pages 79–80 (PDF pages 79–80), says students without approved exemptions who do not participate are assigned the lowest reportable score for accountability, included in the denominator, and counted as novice. This is concrete evidence against approving the ACCT band totals as actual tested proficiency without a separate denominator audit.

KDE's [September 2024 KSIS newsletter](https://www.education.ky.gov/districts/tech/sis/Documents/KSIS_Newsletter_202409.pdf) describes the 2024–25 FRAM collection: direct certification, meal-benefit applications and Household Income Forms. It specifically allows CEP schools to collect HIF for educational funding with a disclaimer that the form does not grant meal benefits. The [FRAM standard](https://www.education.ky.gov/districts/tech/sis/documents/datastandard-fram.pdf) separately identifies household-income eligibility and direct certification and contains transfer/carryover rules; its live PDF now has a 2026 revision. Therefore native SRC economic counts are a promising path, but universal-meal or reimbursement counts cannot be substituted. The [supplemental meal dataset](https://www.education.ky.gov/Open-House/data/Pages/Supplemental-EconomicallyDisadvantaged.aspx) is a separate program-eligible October count and has not been approved for this predictor.

## Work needed

Obtain a primary school-level tested-only published total for Math and ELA, or independently verified valid-score denominators for every grade included in the intended school total. A current source should explicitly distinguish assessed results from nonparticipant novice assignments and identify KSA versus alternate KSA. Then audit the native SRC economic count/member definition and date, preserve suppression, and join using the native state ID. Until those steps pass, no grade-level average, enrollment weighting, inferred count or accountability total should produce a site snapshot.

Official downloads are retained only under ignored `data/raw/KYRC25_*.csv`; no model or ready descriptor has been created.

## Standalone grade 10 audit

The `ASMT` file also has an unaggregated `Grade=10th` All Students row for each subject. This could avoid grade weighting in a separate high-school cohort. The inspected file has 402 school identities with these rows; 206 have an exact native-directory pure-high grade span and both subjects, and 191 have unsuppressed numeric values for both. Those are discovery counts, not approved model membership.

The [2024–25 KSA technical manual](https://www.education.ky.gov/AA/Reports/Documents/KY_SP26_TechReport.pdf), printed pages 22 and 25–26, describes the regular assessment's exemptions, separate school summaries by grade and subject, and performance levels. It does not establish that the historical `KYRC25_ASMT_Kentucky_Summative_Assessment.csv` follows that summary population rather than the accountability nonparticipant rules. No source-specific mapping has been verified. The same-year [KSA yearbook](https://www.education.ky.gov/AA/Reports/Documents/KY1165847_KY_SP26_Yearbook.pdf) supplies statewide tested results, but does not supply an authoritative school denominator or resolve the CSV population.

The grade-10 path therefore remains unapproved pending two concrete source checks: a KDE definition tying `ASMT` percentages to actual assessed students with its regular/alternate inclusion rule, and a dated SRC definition tying the economic count and membership denominator to individual income eligibility (including CEP and carryover handling). The existing accountability rule is evidence against substituting `ACCT`; it is not proof that the separate `ASMT` file is contaminated. Native `State School Id` and `School Code` can support exact joins once these definitions are resolved, without repairing rounded NCES IDs by name.
