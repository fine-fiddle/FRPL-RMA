# North Dakota 2024–25 source audit

North Dakota remains an audited blocker, not a modeling-ready state. Its official public sources offer native school assessment totals, school-year enrollment, demographics and a dated directory. The unresolved gate is an independently established individual economic definition or an authoritative nutrition-site-to-school crosswalk with compatible population scope.

## Native published outcomes

[Insights Data Downloads](https://insights.nd.gov/Data) provides the official `Insights-AssessmentPerformance-CSV-2024-2025-v20251113.csv`. Ordinary public page download controls return the CSV through their ASP.NET form; preview `ShowFile` responses can be empty. Preserve the CSV returned by the public download, rather than treating an empty preview as missing data.

The columns are `AcademicYear`, `InstitutionName`, `InstitutionID`, `Grade`, `Subject`, `AssessmentType`, `Accomodations`, `Subgroup`, and lower/upper ranges for Novice, Partially, Proficient and Advanced. Filter `2024-2025`, `All Grades`, `All` subgroup and accommodations, Math/Reading, and native `Comp` (Combined assessment type). This is a native published all-grades total; no grade aggregation is needed.

The [official student-achievement explanation](https://insights.nd.gov/Education/State/StateAssessment/StudentAchievement) distinguishes achievement from participation. The performance population comprises students enrolled at least 120 days and assessed with ND A+ or the state alternate assessment. The 2024–25 system covers grades 3–8 and 10; high-school ACT accountability ends after 2023–24. General and alternate standards must be labeled explicitly. That page also describes a weighted achievement index. The index is a different outcome from proficiency: a future adapter must use only the published Proficient and Advanced category proportions.

Only a category with equal numeric lower and upper bounds is exact. Both Proficient and Advanced must be exact before summing them; no range midpoint, inferred endpoint, complement, estimated count or enrollment weight is acceptable. There are 261 exact Math/Reading native Comp all-grades rows across 145 school/district/state units, of which 116 have both subjects. The dated public-school directory identifies 72 of those paired units as schools. These are discovery counts, not approvals. The source publishes no tested denominators in this file, so any approved adapter would be point-only with all tested counts and intervals null.

## Income definition gate

The native `Insights-K12Enrollment-AllSubgroups-AllGrades-CSV-v20251230.csv` includes school `Low Income` proportions by academic year. The [Data page](https://insights.nd.gov/Data) describes these as rounded or ranged proportions of the student body. It does not specify the operational Low Income eligibility rule, direct-certification categories, treatment of CEP/universal meals, or the mapping from student administrative fields.

The current raw demographic capture contains 564 school Low Income rows, of which 189 have an exact numeric 2024–25 proportion. Joining only exact published outcomes, exact income and dated directory IDs reveals 65 pure grade-school and six pure high-school candidates. Those counts demonstrate feasibility after the definition is resolved; they do not establish that the economic predictor is individual eligibility.

[STARS Direct Cert / NS Lunch guidance](https://www.nd.gov/dpi/sites/www/files/documents/STARS/EnrollmentHelp/STARS%20-%20Enrollment%20-%20NS%20Lunch.pdf), version 3 dated August 15, 2022, describes direct certification and the NS Lunch flag, including homeless students and lunch programs other than full pay. The [current student import layout](https://www.nd.gov/dpi/sites/www/files/documents/STARS/layouts/student_data.pdf), updated May 1, 2026, distinguishes the NS Lunch flag, free/reduced/paid status, direct-certification status and serving educational entity. Neither document directly establishes which field feeds the Insights Low Income series or verifies its 2024–25 CEP handling. A current student-field definition alone does not approve a dated published series.

Needed: an official, applicable-year Insights Low Income definition naming the individual eligibility statuses and confirming how CEP, state-paid meals, universal meals and full-pay students are treated. A published student-level administrative-field-to-demographic mapping would resolve the gate. Do not replace this evidence with a numeric correlation to lunch counts or the assessment's Low Income tested subgroup.

## Restricted native nutrition alternative

The official [2024–25 Free and Reduced Site Data](https://www.nd.gov/dpi/sites/www/files/documents/ChildNutrition/SNP/2024-2025_FR_%20Site_Publish.pdf) reports LA number, four-digit plant number, site name, grades, provisions, Free, Reduced, State 200, total and Federal F/R percentage. CEP, Provision 2 and RCCI flags are explicit. State 200 is a separate category and must not be counted as federally free/reduced. A restricted ordinary-program cohort using native individual Free + Reduced divided by its own native enrollment could be viable after authoritative identity and scope are established.

The nutrition plant is a nine-digit district-plus-plant entity. Insights has ten-digit school unit IDs; the public directory distinguishes elementary/middle/secondary units. Among its 511 public school rows, 111 additional units share an existing nine-digit prefix. For example, the native directory has both Alexander elementary `2700203151` and secondary `2700203153`. One plant-level nutrition count must not be assigned to both or to one arbitrarily.

[NDDPI MIS03 instructions](https://www.nd.gov/dpi/sites/default/files/documents/STARS/manual/MIS03_Instructional_Manual.pdf), page 6, specify the two-digit county, three-digit LEA and four-digit DPI-assigned school number. That establishes the administrative plant format but does not, by itself, crosswalk the extra Insights school-unit digit or certify which nutrition populations span multiple units. No truncation, name matching or denominator reconstruction has been approved.

Needed: an official mapping between nutrition LA/plant and the dated Insights school units, with an exhaustive multiple-unit rule. Exclude every shared/ambiguous plant and every CEP/Provision/RCCI site unless individual eligibility and the exact school population are separately verified. Confirm that a remaining single school unit's grades and nutrition enrollment refer to that individual school, rather than a feeding-site allocation.

## Saved evidence and next action

[north-dakota-audit.json](../data/source/north-dakota-audit.json) records the native file schemas, official URLs, raw checksums, exact-value inventory, cohort discovery counts, primary definitions and actionable gates. Raw downloads remain ignored in `data/raw/`. No North Dakota dataset, descriptor, canonical observations or models were created. Assessment and economic missingness remain preserved.
