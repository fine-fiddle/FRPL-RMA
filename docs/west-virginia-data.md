# West Virginia 2024–25 source audit

West Virginia remains **audit pending**, with no released model or catalog descriptor. Official bulk assessment, same-year school composition, school directory and individual direct-certification files were recovered on October 9, 2026. Their identifiers support an exact school join. The unresolved issue is the assessment outcome: published school proficiency can use a participation-adjusted denominator. Removing sampling intervals does not turn that outcome into actual scored-student proficiency.

## Recovered official files

The following public files download directly from West Virginia's own servers. Their original URLs, SHA-256 hashes, observed sheet metadata and representative native records are preserved in `data/source/west-virginia-audit.json`.

- [SY25 Assessment Results, Public All Final](https://static.k12.wv.us/zoomwv/data/SY25_AssessmentResults_Public_All_Final.xlsx): school/district overall proficiency, proficiency by grade, four achievement-level percentages and a separate `# Students Tested` sheet.
- [SY25 Enrollment and School Composition, Final](https://static.k12.wv.us/zoomwv/data/SY25_EnrollmentAndSchoolComposition_Final.xlsx): exact numeric school enrollment in Pre-K, K and Grades 1–12, plus the native school directory with six-digit school ID and NCES ID.
- [West Virginia Percent Needy Report](https://static.k12.wv.us/zoomwv/data/WV_PercentNeedy_Report.xlsx): the `SY24-25 Percent Needy` sheet publishes native school IDs, individual direct-certification counts, its own October 1 enrollment denominator and published fractions. Newer and older sheets are not substituted.
- [2025 West Virginia Assessment Results](https://wvde.us/sites/default/files/2025-08/2025%20West%20Virginia%20Assessment%20Results.pdf), page 1: assessment scope and full-academic-year inclusion.
- [Current linked accountability methodology](https://wveis.k12.wv.us/essa/docs/methodology.pdf), pages 10–13: valid-score and full-academic-year inclusion, performance levels and the 95% participation adjustment. The dashboard also explicitly links [methodology_revised2022.pdf](https://wveis.k12.wv.us/essa/docs/methodology_revised2022.pdf), which returned identical bytes on the audit date.

The public ZoomWV assessment dashboard defaulted to 2026. Its year filter and CSV export did not change visible state or download a file in the browser; ordinary public requests to its dashboard API returned HTTP 401. The recovered static 2025 files resolve that access problem. No authenticated token was replayed and no access-control bypass was used.

## Exact identities and economic scope

The assessment's three-digit `Dist` plus three-digit `Schl` equals the economic report's six-digit `School ID`, such as `002501`. The directory independently publishes that native ID and NCES ID. All 601 native assessment school records match both the same-year composition table and the same-year income table exactly. District and state rows with school code `999` are summaries, not schools. No school name establishes a join.

The income workbook's introduction explicitly says that, beginning in 2017–18, low socioeconomic status uses **only individual students directly certified** for free or reduced-price meals. This replaces the earlier practice that also treated all children at CEP schools as low SES. The new method applies consistently regardless of CEP status and is distinguished from meal reimbursement or claiming percentages. The workbook retains a legacy definition cell saying the direct-certification field is presented only for CEP schools; that cell must not override the explicitly stated post-2017 reporting scope or turn a missing count into zero.

`Total Enrolled Students` is certified October 1 enrollment under Title I eligibility rules, primarily K–12 plus some Pre-K students with IEPs. It is the income report's own denominator and can differ from the general school composition headcount. For example, Philippi Elementary (`002204`) has 368 in the income table and 387 in the composition table. A future importer must retain this distinction, the native count and the published fraction. Suppressed enrollment or direct certification remains unavailable; the footer warns of suppression below ten. This enrollment is never an assessment denominator.

The composition table has 702 school profiles, all with exact numeric Pre-K, K and Grades 1–12 enrollment. There are 485 profiles with tested Grades 3–8 and no Grades 9–12, 93 with high-school grades and no Grades 3–8, 96 with both, and 28 outside these two tested populations. Future separate grade-school and high-school models must exclude mixed profiles, rather than place grade-6–12 schools in the grade-school filter.

## Assessment definition and concrete hold

The current 2025 summary describes combined WVGSA and WVASA outcomes for Grades 3–8, and SAT School Day plus WVASA for Grade 11. Results include students enrolled at least **135 days during the school year** and present in the end-of-year enrollment file. The separate assessment systems and their grade scopes must remain explicit. The file supplies native school totals; no grade percentage averages or pooled history would be introduced.

The performance workbook contains a material denominator warning. For Philip Barbour High School Complex (`002501`), it publishes:

| Field | Math | ELA |
| --- | ---: | ---: |
| Four level fractions | 0.5118, 0.2801, 0.1545, 0.0290 | 0.3090, 0.1642, 0.3573, 0.1449 |
| Sum of four fractions | 0.9754 | 0.9754 |
| Native proficiency fraction | 0.1835 | 0.5022 |
| Separate students tested | 101 | 101 |

The math fractions match the integer pattern 53, 29, 16 and 3 divided by **103.55**, which equals 95% of 109. For example, 53 / 103.55 rounds to 0.5118, and 19 / 103.55 rounds to the native proficiency fraction 0.1835. This is a diagnostic consistency example, **not a published count source**: neither 109 nor those level counts are imported or claimed as authoritative observations.

The linked official accountability methodology, pages 11–13, states that the achievement calculation retains nonparticipants when participation falls below 95%, replacing the actual scored-student denominator with 95% of full-year enrollment. Native four-band deficits also appear at Martinsburg High (`004502`), Clay County High (`016501`) and Wildwood Middle (`037404`), so the concern is not limited to one school or to high schools. Deficits exceed the rounding precision of four published four-decimal fractions.

The methodology defines a weighted achievement-points indicator rather than expressly documenting these particular public proficiency columns. Consequently, its formula and the native counterexamples establish a concrete unresolved outcome issue; they do not authorize reversing rounded percentages into actual level counts. A subset whose bands happen to sum to 100% would not establish all population and denominator adjustments. Renormalizing the bands, manufacturing counts from them, importing the native totals as raw proficiency, or simply omitting intervals would leave that issue unresolved.

## What resolves the hold

An official current definition tied to these public proficiency columns must establish actual valid-score proficiency and every population adjustment, or a native scored-student numerator/denominator must support a separate actual proficiency measure. Verified valid-score grade weights would also support complete within-assessment grade aggregation after exact school identities and grade scope are retained. Suppression must remain intact throughout.

Until that evidence is available, the recovered sources and exact counterexamples are an audit result. No West Virginia JSON model, catalog descriptor or canonical dataset has been created. The source audit retains enough provenance to resume without repeating the access and identity work.
