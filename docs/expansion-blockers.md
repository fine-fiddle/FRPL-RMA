# Verified expansion blockers

These are specific source problems observed on October 9, 2026. Minnesota and Michigan’s earlier route problems have recovered public flows; Ohio has an unresolved scientific definition
and identity problem for broad coverage even though its source workbooks are downloadable. They are not
evidence that a state has no suitable data. No blocked source is represented as a
ready regression population.

## Current unresolved states

The release queue contains 38 available states. Each available comparison has its own restricted population and source definitions; this is not complete school coverage. The remaining twelve states have these concrete next steps:

| State | Evidence and resolution |
| --- | --- |
| Connecticut | [Native guest exports fail](connecticut-data.md); obtain the current official assessment and individual eligibility exports. |
| Kentucky | [Actual school totals or valid grade weights are missing](kentucky-data.md); verify source-specific assessed proficiency and individual income definitions. |
| Michigan | The normal public bulk-download form requires an authorized delivery email; acquisition is pending that address. |
| Nebraska | [Accountability level counts can include nonparticipants](nebraska-data.md); obtain an actual scored-student population. |
| New Hampshire | [Assessment CSV lacks school IDs](new-hampshire-data.md); obtain a native ID export or authoritative exact crosswalk. |
| North Dakota | [Income definitions and nutrition plant-to-school IDs remain unresolved](north-dakota-data.md); establish individual eligibility and a complete exact mapping. |
| Ohio | [FY25 public income can include blanket provision coding](ohio-data.md); isolate individual codes or resolve complete program/site and annual population scope. |
| South Dakota | [Income definitions and invalidated-score instructions need resolution](south-dakota-data.md); identify corrected/excludable school IDs and actual score scope. |
| Utah | [Native proficiency population and fractions remain unresolved](utah-data.md); its adapter preserves an audit hold across rebuilds. |
| Vermont | [Same-year individual income with exact school IDs is unavailable](vermont-data.md); do not backfill older income or use provision claiming percentages. |
| West Virginia | [Native rates show a participation-adjusted denominator](west-virginia-data.md); obtain independently published actual scored numerators and denominators. |
| Wyoming | [Native grade data lack school IDs, totals and exact weights](wyoming-data.md); obtain authoritative-ID school totals or complete valid-score grade counts. |

## Michigan: earlier route failures; current public flow recovered

Initial HTTP requests to the legacy report and public download page returned `403 Forbidden`. Browser verification subsequently found that the [legacy report](https://legacy.mischooldata.org/DistrictSchoolProfiles2/AssessmentResults/AssessmentGradesPerformance2.aspx) is decommissioned and displays Restricted Access. The earlier guessed `/grades-3-8-assessments-performance-level/` path displays Page Not Found.

The current public menu instead links [Grades 3–8 State Testing](https://www.mischooldata.org/grades-3-8-state-testing-includes-psat-data-performance/) and [K–12 Data Files](https://www.mischooldata.org/k-12-data-files/). The latter loads its 2024–25 year, assessment category and Grades3–8 file controls in the browser. Its [current field layouts](https://www.michigan.gov/cepi/-/media/Project/Websites/cepi/MISchoolData/Reference/Data-File-Table-Layouts__051426.xlsx) are public. The public download form requires an email address to deliver the selected files asynchronously. Acquisition is pending the user’s authorized delivery address; no address has been invented or submitted.

This recovers source discovery, not modeling approval. No new Michigan extract or model is ready. The next steps remain obtaining same-year native school assessment and individual enrolled Supplemental Nutrition Eligibility data, then auditing the grade8 PSAT transition, suppression, valid scores and exact IDs. No secure login or CAPTCHA bypass was attempted.

## Minnesota: normal public downloads recovered

The official [Data Center](https://pub.education.mn.gov/MDEAnalytics/Data.jsp)
links assessment and student file selectors. Initial download-driver requests
returned a Radware CAPTCHA/unblock page instead of the source payload:

- <https://pub.education.mn.gov/ibi_apps/WFServlet?IBIF_ex=mdea_ddl_driver&TOPICID=1&DDL_VARS=5>
- <https://pub.education.mn.gov/ibi_apps/WFServlet?IBIF_ex=mdea_ddl_driver&TOPICID=2&DDL_VARS=5>

The normal public topic page and visible selector flow subsequently loaded the
2025 assessment and enrollment file lists without a CAPTCHA. Their official
file links provided authentic Math, ELA and October 2024 enrollment workbooks.
No CAPTCHA was solved or bypassed. Implementation now uses those native files;
the earlier access result is not a current modeling blocker. Dated 2024–25 MARSS
instructions establish individual economic eligibility even under universal
meals, CEP and Provisions 2/3. Native valid-score and suppression definitions
remain part of the adapter audit.

## Ohio: universal-meal status cannot identify individual disadvantage

The subsequent [dated FY25 source audit](ohio-data.md) recovered actual 2024–25 files and primary definitions. It confirms the individual-income and reporting-site obstacles for the requested year. Fifteen narrow community-school profiles are retained as unapproved candidates; numerical feasibility does not resolve their annual income/program scope. The following earlier FY26 discovery is historical context, not the basis for withholding FY25.

The [2025–26 report-card download portal](https://reportcard.education.ohio.gov/home/download)
provided accessible building assessment, detail, grade-enrollment and economic
subgroup workbooks. Its public category-file endpoint was:
<https://edu-prd-reportcard-datarefresh-api.azurewebsites.net/api/v2/CategoriesFileTypes/2026/0/0>.
The official SPA appends its published document token to the returned file
locations; bare Azure blob links do not work.

The [FY26 EMIS Student Attributes guide, v15.1](https://education.ohio.gov/getattachment/Topics/Data/EMIS/EMIS-Documentation/Current-EMIS-Manual/2-5-Student-Attributes_Effective-Date-FD-Record-v15-1.pdf.aspx?lang=en-US)
(printed pages 6–7) permits CEP/Provision 2/3 buildings to report all students as
economically disadvantaged, including students without established individual
eligibility. Codes 4/5 and 6/7 distinguish unverified and verified CEP status,
but `BUILDING_ECON_DIS_2526.xlsx` exposes only `ECONDISADV` and
`NOTECONDISADV`. Those totals cannot safely be treated as individual FRPL or
income eligibility.

The separate [FY26 nutrition-data documentation](https://education.ohio.gov/getattachment/Topics/Student-Supports/Food-and-Nutrition/Resources-and-Tools-for-Food-and-Nutrition/Data-for-Free-and-Reduced-Price-Meal-Eligibility/Description-for-Data-for-Free-and-Reduced-Price-Meal-Eligibility-3.pdf.aspx?lang=en-US)
does not resolve this: CEP percentages use a 1.6 claiming multiplier; Provision
2 applicant counts can come from an earlier base year. Reporting sites can also
combine multiple schools, and the agency keeps no record of which buildings
the combined site includes. Absence from this non-exhaustive nutrition list
does not establish non-CEP status.

Required resolution: a same-year building-level extract distinguishing
individually eligible EMIS codes, or an authoritative complete school crosswalk
and provision registry supporting an explicitly restricted population. No Ohio
model is published from the aggregate `ECONDISADV` field.

## Wyoming: accessible public files lack usable schoolwide identity/weights

The [official public school assessment report](https://reporting.edu.wyo.gov/ibi_apps/run.bip?BIP_REQUEST_TYPE=BIP_RUN&BIP_folder=IBFS%253A%252FWFC%252FRepository%252FPublic%252FAssessment%252FAggregated%252F&BIP_item=SchoolLevelResultsHTML.htm) downloaded a valid 2024–25 XLSX through its normal browser controls. It contains 2,023 grade-level records, no schoolwide totals and no authoritative school IDs; every tested count is a protected range. This is a scientific identity/aggregation hold, not a browser or download-access failure. Protected count ranges cannot weight school totals, and rounded percentages cannot reconstruct them.

The alternate growth report restricts proficiency to students having growth percentiles and caps5/95; the public accountability profile exposes categories or goal attainment rather than actual Math/ELA responses. Official 2025 technical reports provide statewide summaries. The same-year federal extract likewise has zero G38 totals. Resolution requires exact-ID native actual school totals or complete exact-ID grade rows with independently visible valid-score weights, followed by individual same-year income audit. Evidence, schema and checksums are recorded in the [Wyoming guide](wyoming-data.md) and `data/source/wyoming-audit.json`. No ready Wyoming descriptor is emitted.
