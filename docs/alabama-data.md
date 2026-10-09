# Alabama 2024–25 data

`al-acap-dc-2025` models native Alabama ACAP Summative/Alternate school proficiency against same-year individual direct certification. Its 893 grade-school profiles include 847 Math, 877 ELA and 833 Combined model members. This is a benefits-based economic proxy, not full FRPL eligibility. Published rates support point estimates; sampling intervals are unavailable. State proficiency standards are separate, and the residuals describe associations rather than causal effectiveness.

## Sources and native totals

The [official School Performance page](https://www.alabamaachieves.org/reports-data/school-performance/) links the [2024–25 Math workbook](https://www.alabamaachieves.org/wp-content/uploads/2025/08/RD_SP_2025813_2024-2025ParticipationandProficiencyMath_v1.xlsx) and [ELA workbook](https://www.alabamaachieves.org/wp-content/uploads/2025/08/RD_SP_2025813_2024-2025ParticipationandProficiencyELA_v1.xlsx). They downloaded successfully (89,758,453 and 94,996,903 bytes). County, City and Charter sheets publish exact three-digit system/four-digit school codes, native ALL totals and suppressed subgroup percentages. Both State sheets publish ALL plus grades `03`–`08` and `11`; grade `02` is absent. ACAP is administered in grade 2, but this public proficiency total does not include it. The adapter retains those native grade-definition rows as evidence.

The [native Supporting Data proficiency page](https://reportcard.alsde.edu/SupportingData_Proficiency.aspx) adds enrolled, tested, proficient and performance-level counts. Choose reporting year 2024–2025; require Grade=All Grades, Gender=All Gender, Race=All Race, Ethnicity=All Ethnicity and Sub Population=All SubPopulation. Reveal **System Code and School Code** through Choose fields before Export to CSV. The observed public export has 4,302 rows and 761,866 bytes; 1,297 school IDs have Math/ELA totals after excluding `School Code=0000` district/state totals and Science. Source URL, checksum, exact filter, raw cells and original CSV row numbers are in the compact extract. No authentication was required.

The [official glossary](https://www.alabamaachieves.org/reports-data/school-data/glossary-of-terms/) defines proficiency as Levels 3/4 among valid scores. These native unweighted rates are separate from the Academic Achievement indicator, whose [business rules](https://www.alabamaachieves.org/reports-data/school-data/fed-rep-car-business-rules/) apply level weights and the federal 95% denominator. Do not import accountability indicators, annual MIP actual rates or feeder-assigned indicator scores as this response. No K–2 feeder schools appear among the native school proficiency totals.

Use the exact published two-decimal Proficient Rate with no grade averaging. Asterisk is suppression, including small groups and complementary protection; tilde is a protected extreme percentage, not a number. Numeric zero remains zero. Ranges, missingness and protected rates stay unavailable.

Native **Tested is not automatically the proficiency denominator**. For example, state ELA Tested=378,291 while its four proficiency levels sum to 375,517; 210,964 proficient / 375,517 agrees with the native 56.18%, whereas dividing by Tested does not. ELA exemption rules can change the response population. All tested/level cells remain raw evidence, and no score denominators are imported or inferred. All Math, ELA and Combined intervals are therefore unavailable, including schools with visible Tested cells.

## Individual economic measure

Use reported school-level Direct Certification Education Unit Total in the [CCD 2024–25 lunch release](https://nces.ed.gov/ccd/Data/zip/ccd_sch_033_2425_l_2a_073025.zip), divided by positive reported Education Unit Total in the [same-year membership release](https://nces.ed.gov/ccd/Data/zip/ccd_sch_052_2425_l_1a_073025.zip). Match exact NCES ID and Alabama state school ID, with no name join or other-year fallback. Membership includes pre-K where enrolled. This captures individual categorical eligibility; application-only eligible families are outside this proxy, and every CEP meal recipient is not counted as disadvantaged.

The [official CCD state notes](https://nces.ed.gov/ccd/xls/SY_2024-25_CCD_Final_2a_Data_Notes.xlsx) explicitly confirm that Alabama's DC total includes students certified for **both free and reduced meals**. The SEA attributes an approximately 6% decline in direct certification to Medicaid eligibility rollback noticed in April 2025. Treat this eligibility era and state definition separately. Same-year CCD matching does not guarantee identical dates: membership is a fall snapshot, while the income notes discuss spring reporting. No reported DC count exceeded its matched membership. Nonreported counts are unavailable; do not substitute another lunch category.

Alabama's [PowerSchool page](https://www.alabamaachieves.org/powerschool/) links its public [Data Code Manual](https://www.livebinders.com/b/2767891), whose [meal-status section](https://docs.google.com/document/d/1ZQOvtIocJhqNeyXM7uWNrYjTfGYYrjyb3Jk0ruh9xXk/edit) distinguishes individual Medicaid free/reduced and household-extension eligibility. That current manual supplements the authoritative same-year CCD note; it does not justify interpreting every native Fall FRL count at CEP schools as a current individual income determination. The downloadable Fall FRL workbook has CEP flags and counts below enrollment, but its exact CEP reporting treatment was not established. It is not used as an income fallback.

## Scope and identity

The [official 2024–25 CCD directory](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip) exactly matches all 1,297 native school IDs through `AL-DDD-SSSS`. Retain operational status 1/3/4/5/8, complete unadjusted grade offers ending at grade 8, no grades 9–13/adult offers, and complete reported/derived enrolled-grade counts reconciling to membership. High, adult and ungraded enrolled categories must be explicitly zero. This excludes 404 profiles. Names and cities come from that historical directory; coordinates remain unavailable. No school is classified from current displayed metadata.

Separate statewide subject models use every eligible member and externally studentized residuals. Combined is the equally weighted Math/ELA mean. UI filters never refit. History contains only 2025.

## Rebuild and verification

Default rebuilds use only the committed compact extract:

```sh
.venv/bin/python scripts/prepare_alabama.py
.venv/bin/python -m unittest discover -s tests -p test_alabama.py -v
```

For extraction, save the native filtered CSV as `data/raw/al_proficiency_2025.csv`, have the linked CCD ZIPs, notes, reference files and Math/ELA workbooks under the raw filenames recorded in the extract, and run `prepare_alabama.py --extract`. Raw files remain ignored; checksums preserve provenance. `--database PATH` supports a separately initialized SQLite test store. Tests cover individual DC reporting flags, suppression, exact ID/year joins, grade scope, point-only intervals and independent deleted-school residual fits. Repeat import hashes, foreign keys and unrelated canonical/Chicago preservation are checked before integration.
