# Arizona native 2024–25 data

Arizona uses the Arizona Department of Education's native Spring 2025 assessment results and October 1, 2024 enrollment workbooks. Grade schools have separate AASA/MSAA grades 3–8 models; high and mixed-grade schools have regular ACT grade 11 models. Both use same-year individual Income Eligibility 1 or 2. These state-specific standards and populations are not pooled with other states.

## Official sources and reproducible extract

The [ADE accountability data page](https://www.azed.gov/accountability-research/data) links both native files, retrieved October 9, 2026:

- [2025 AASA, ACT and MSAA assessment results](https://www.azed.gov/sites/default/files/2025/10/math_ela_assessmentsfy25.xlsx), version 1.09. Data were captured August 18, 2025; the workbook was created September 30, 2025. The `School` sheet has 701,058 worksheet rows. The extract preserves 5,142 selected All Students/FAY Status All rows for All Assessments and regular ELA/Math Grade 11, before any school-population exclusions.
- [FY2025 October 1 enrollment](https://www.azed.gov/sites/default/files/2025/04/Oct1EnrollmentFY2025.xlsx), version 1.04, captured and created April 22, 2025. `School by Grade` supplies 2,063 native profiles after statewide rows are excluded. `School by Subgroup` supplies same-table All Students and Income Eligibility 1 or 2 counts.

The native Introduction, Data Dictionary and Subgroup Dictionary are retained in `data/source/arizona.json`, along with raw selected assessment and enrollment rows, native worksheet row numbers, exact source URLs and SHA-256 checksums. `data/raw/arizona/` is ignored. Normal offline rebuilds use the committed extract and do not require downloading the 72 MB assessment workbook again.

The assessment SHA-256 is `fc45802b39add6b77f51159245f9d2fb40ab3b62f74e433f3187c4c30f4a19a4`; enrollment is `a41cc8d6572c6621277ae860c8dfb632b9a638a00f9bfe6efb0b420986da142b`. Ordinary requests encountered ADE's browser challenge. Both files were recovered from the observed official download links through the in-app browser, and their XLSX ZIP signatures and native worksheets were verified.

## Identity and model populations

Every join uses ADE's exact numeric School Entity ID and the same-year native LEA Entity ID. School and district names never establish identity. The source fiscal year must be 2025, which the native dictionaries define as 2024–25. Assessments without native October enrollment and cross-district mismatches remain excluded.

The enrollment introduction says blank grade cells are unserved grades. Any positive or suppressed grade 9–12 enrollment therefore classifies the school as high school, including mixed-grade schools. A suppressed high-school grade is never treated as absent. Other schools serving grades 3–8 are grade schools; early childhood and other non-tested grade profiles remain outside the directory.

The workbook's All Assessments rows combine regular AASA/ACT with MSAA alternate assessments, which have alternate achievement standards. They are used directly only for grade schools without enrolled grades 9–12, restricting the applicable assessment population to grades 3–8. There is no native all-regular-assessments grade-school total; grade percentages are not averaged. High and mixed-grade schools use only the regular `Math Grade 11` and `ELA Grade 11` rows. Their All Assessments totals and alternate Grade 11 rows are excluded.

The native introduction says valid test results are included for students enrolled at the first date of the Spring test window. Results are assigned to the entity where testing occurred; repeated assessments retain the highest score. These are tested-performance results, rather than a 95% participation-adjusted indicator. The All FAY population is used, not a full-academic-year subset. The school where testing occurred can differ from the school of October enrollment, so even an exact school-ID join does not establish identical student populations across the two measurements.

## Individual income eligibility

Income is `100 × Income Eligibility 1 or 2 Total / All Students Total`, using two published counts from the same October enrollment subgroup table. Counts from the grade table or ethnicity columns do not substitute for that denominator. The denominator includes all enrolled grades, including preschool where served; it is not an assessment denominator.

The native subgroup dictionary identifies these flags as of October 1, 2024. ADE's [FY2025 alternative household income form](https://www.azed.gov/sites/default/files/2024/07/2025-%20Alternative%20Form%20for%20Income-Based%20Eligibility.pdf) specifies individual Income Eligibility 1 and 2 against its household income thresholds. [October 2024 CEP reporting guidance](https://www.azed.gov/sites/default/files/2024/10/October%202024%20Staying%20on%20Track%20QA%20for%20Event%20Follow-Up%20.pdf) confirms that CEP schools report directly certified individuals, with additional Income Eligibility 1/2 reporting permitted from alternative applications. Universal meal access does not mark every student individually eligible. CEP schools that omit alternative household forms may underreport broader individual eligibility; this remains a coverage caveat.

Of the 2,063 native grade profiles, 1,934 have an explicit combined eligibility row; 1,846 publish numeric individual counts and 88 suppress them. An absent or suppressed numerator is unavailable. Free/reduced parts, other subgroup counts, names, older years and complements do not reconstruct it.

## Suppression and valid-score denominators

The assessment introduction and dictionary jointly establish that `Number Tested` belongs to the included valid-result population. It is preserved only when the native field is numeric. No enrollment, expected participation or federal adjustment counts are substituted.

ADE suppresses groups of 10 or fewer, complementary values that disclose such groups, and extreme proficiency values. `*`, `<2%`, `>98%` and missing values are unavailable, not zero or midpoints. Performance percentages are whole numbers rounded with the largest remainder method. The four unsuppressed bands must sum to 100; separately rounded Percent Passing may differ by one point from levels 3+4. No proficient-student numerator is inferred from those rounded rates.

All eligible grade-school members have valid counts, so grade-school intervals propagate sampling uncertainty across the entire model. Each high-school subject model and Combined has nine eligible members with suppressed tested counts. Consequently every high-school interval is unavailable, including intervals for members whose own counts are published. Studentization remains available and is not enrollment adjustment or shrinkage.

## Current coverage

The directory contains 2,010 schools: 1,416 grade schools and 594 high or mixed-grade schools. The source audit excludes 1,167 selected assessment rows with mixed or non-applicable test populations and 16 assessment rows without same-year October enrollment. No matched assessment/enrollment district-ID discrepancy is present in the current extract.

| Model | Math | ELA | Combined |
| --- | ---: | ---: | ---: |
| Grade school AASA/MSAA 3–8 | 1,229 | 1,280 | 1,228 |
| Regular ACT grade 11 | 249 | 283 | 246 |

Combined is the equally weighted mean of the two eligible subject percentages. It is not the percentage proficient in both. Exclusions preserve 771 missing or suppressed subject results, 507 missing subject-pair results and 147 missing or invalid same-year income results. These categories are per record/subject and are not a sum of unique schools.

This release contains one year, no audited coordinates and no admissions classifications. The catalog has null boundaries and an explicit unavailable-location message. There is no invented map or connected history across assessments.

## Rebuild and verification

With the existing extract:

```sh
.venv/bin/python scripts/prepare_arizona.py
```

To reproduce the source extract after saving the two official files as `data/raw/arizona/assessments.xlsx` and `enrollment.xlsx`:

```sh
.venv/bin/python scripts/prepare_arizona.py --extract
.venv/bin/python -m unittest discover -s tests -p test_arizona.py -v
```

Eight tests check bounded and suppressed values, independent rounding, authoritative same-year identity, individual income counts, mixed-grade partitioning, native output values, importer repeatability and unrelated rows, and independent external studentization for all six models. They also verify the whole-model interval rule. Repeated isolated imports produce byte-identical schools, history, audit and catalog exports.
