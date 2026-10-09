# Washington OSPI 2024–25

Washington uses official OSPI Report Card data published through Data.WA. The snapshot joins current-year SBAC proficiency to individual low-income eligibility by the authoritative six-digit school organization ID and the same 2024–25 school year. Its models remain separate from every other state and from each other.

## Sources and definitions

- [OSPI assessment data and API field definitions](https://data.wa.gov/education/Report-Card-Assessment-Data-2024-25-School-Year/h5d9-vgwi), updated September 10, 2025.
- [OSPI enrollment data](https://data.wa.gov/education/Report-Card-Enrollment-2024-25-School-Year/2rwv-gs2e), updated June 18, 2025.
- [Assessment Report Card data notes](https://data.wa.gov/api/views/h5d9-vgwi/files/f4862f81-7170-4645-bb71-49e195bdef72?download=true&filename=ReportCardDataNotes.xlsx) and [enrollment data notes](https://data.wa.gov/api/views/2rwv-gs2e/files/53a7d0f1-3589-46b6-ad2a-e548e9dcb9c1?download=true&filename=ReportCardDataNotes.xlsx).
- [CEDARS 2024–25 reporting guidance](https://ospi.k12.wa.us/sites/default/files/2024-07/reporting_guidance_2024-25ada.pdf), especially pages 94–95, defines individual free/reduced-price meal and comparable-income eligibility.
- [OSPI disclosure avoidance rules](https://data.wa.gov/api/views/h5d9-vgwi/files/018658f4-2d27-4ac0-bc32-4515c636af84?download=true&filename=protecting-student-privacy-public-reporting_adav3_92023.pdf).

The assessment source distinguishes two different proficiency definitions. `Percent Consistent Grade Level Knowledge And Above` divides by students expected to test, including previously passed students. It is excluded. We use the directly published `Percent Consistent Tested Only`: current-year students scoring in SBAC levels 3 or 4 divided by all current-year valid scores in levels 1–4. Untested and previously passed students are excluded. AIM alternate assessments and science are outside these models.

The native table does **not** publish an exact valid-score count. Expected-to-test counts, participation rates, and enrollment are not valid substitutes. All Washington `tested`, `low`, and `high` fields therefore remain null: studentized residuals are available, but sampling intervals are unavailable for all six models. No denominator is recovered by rounding or multiplying published rates.

## Grade populations

SBAC tests grades 3–8 and grade 10 in 2025. Grade-school models use directly published `All Grades` school totals only where same-year enrollment has no grade 9–12 rows. Their assessed population is consequently within grades 3–8. We neither average grade percentages nor weight them with enrollment.

A school with any high-school grade row appears only in the high-school directory, even when the membership count is privacy-redacted to zero. Its high-school outcome uses the separate grade-10 SBAC row. Its `All Grades` total may include lower grades and is excluded. These mixed schools' grades 3–8 results cannot be aggregated without verified valid-score weights, so they are outside the grade-school regression population. Schools serving only grades below 3 are outside the directory.

## Individual income eligibility and privacy

OSPI enrollment counts students attending their primary school on the first business day in October. It includes Pre-K through grade 12. Program characteristics identify students receiving the relevant status at any time during that school year. Income is `Low-Income / All Students`, checked against the complementary `Non-Low Income` count.

CEDARS uses individual free/reduced-price meal eligibility or comparable-income status. The 2024–25 Child Nutrition Eligibility & Education Benefit application merges the meal application and family income survey; schools operating CEP or Provision 2 still collect individual eligibility information. Universal meal service does not turn every enrolled student into a low-income student. This is distinct from CEP reimbursement percentages, direct-certification multipliers, and area-eligibility files.

Any assessment disclosure avoidance (`DAT`) flag excludes that assessment record, including records where a numeric tested-only field remains. Enrollment privacy sometimes writes zero into both complementary protected fields. The importer preserves those raw zeros but leaves eligibility unavailable, without interpreting them as zero income or reconstructing the protected count. A Foster Care-only flag does not suppress reconciled low-income counts.

Whole-school Pre-K–12 income, grade mix, participation, and representation remain limitations. The release includes only 2025, no admissions classification, and no audited school coordinates or map.

## Rebuild

The committed `data/source/washington.json` retains each used original field, API row ordinal, school-grade membership, official source URL, checksum, and retrieval time. API ordinals refer to the filtered, explicitly ordered downloaded JSON. Ignored native files live in `data/raw/washington/`. The filtered assessment request selects school/all-student/SBAC math and ELA, `All Grades` and `10`; enrollment selects same-year school records. Exact request URLs are retained in provenance, including query filters, ordering, and the limit. Downloaded row counts must remain below that limit.

```sh
.venv/bin/python scripts/prepare_washington.py
.venv/bin/python scripts/export_catalog.py
```

To refresh the extract, download the native JSON from the recorded API URLs, save the URLs as `assessment-url.txt` and `enrollment-url.txt`, and download the source metadata, attached notes, privacy rules, and same-year CEDARS guidance using their recorded filenames and URLs. Then run `prepare_washington.py --extract`. The importer replaces only `wa-ospi-2025`; repeated runs preserve other states and produce identical exports from an unchanged extract.
