# ISBE historical assessment data request

Prepared September 25, 2026. **Not submitted.**

ISBE directs Report Card data questions to [reportcard@isbe.net](mailto:reportcard@isbe.net) on its [official help page](https://irc.isbe.net/Help). Its [public records portal](https://isbe.govqa.us/webapp/_rs/SupportHome.aspx), linked from [ISBE's FOIA page](https://www.isbe.net/foia), requires a login. Paste the request body below into the portal's request-description field, or send it to the Report Card team to locate an existing export. Do not submit both routes simultaneously.

Portal status: inspected, signed out. No request number exists. Requester identity, reply address, and any required commercial-use declaration must come from the requester; they are not inferred from this repository. Keep those contact details out of Git.

## Subject

Existing school-level PARCC, IAR and SAT proficiency records and valid-score counts

## Request body

Hello,

I am seeking existing electronic records for Illinois public schools to complete a public school comparison project, Achievement x Economic Disadvantage. The project compares school proficiency with the level associated with the same year's school low-income percentage. Only school-level aggregates are needed; no student-level records or personally identifiable student information are requested.

Please provide existing files or exports covering the following assessment administrations, in this priority order. Years below mean the spring assessment year / school-year ending year; 2020 is intentionally excluded.

| Priority | Assessment | Years | Requested records |
| --- | --- | --- | --- |
| 1 | PARCC, grades 3–8 | 2018 | School-wide ELA and math proficiency rates, proficient counts where maintained, and the corresponding valid-score denominators |
| 1 | IAR, grades 3–8 | 2019, 2021, 2022 | The same school-wide subject records |
| 2 | PARCC, grades 3–8 | 2017 | Valid-score denominators and corresponding subject proficiency records, to reconcile with the published rates |
| 2 | SAT, state high-school administration | 2017, 2018, 2019, 2021, 2022, 2023, 2024 | Valid EBRW and math score counts and corresponding state-standard proficiency records |

For each record, please retain existing fields identifying the school RCDTS (including leading zeros), school/district names, assessment year, assessment name, subject, grade or grade span, and student group. The all-students group is sufficient. Please preserve suppression and missing-value indicators and include closed or renamed schools where they appear in that year's records.

For grades 3–8, school-wide aggregates specific to PARCC or IAR are preferred. If those are not maintained, existing school-by-grade subject records with their matching valid-score counts would also meet the need. Please keep alternate assessments such as DLM separate. For SAT, the requested measure is proficiency under the Illinois standards applicable in that year, rather than College Board college-readiness benchmarks or graduating-class participation reports.

The denominator needed is the count of valid subject scores underlying the corresponding proficiency percentage. Testing enrollment, total enrollment, or an accountability denominator increased to 95% of enrollment would not serve the same purpose. Existing count/rate pairs and their documentation are requested so the populations can be reconciled, not inferred.

Please also include any existing data dictionary or business rules describing the fields, proficiency cut points, included/excluded students, school attribution, retests, rounding, and suppression. No new calculations, custom analysis, unsuppression, or written explanations need to be created for this request.

CSV, Excel, or the existing machine-readable format is preferred. If responsive files are already public, direct links and the relevant fields would be sufficient. Separate files and partial fulfillment are welcome; priority 1 is the most useful first delivery. Please advise before incurring any charges.

Thank you.

## Recording the response

After submission, record the date, channel and reference number here, without personal contact details. Preserve the response's source files locally under `data/raw/`, record checksums and source definitions, and validate counts against published rates before changing the website. If the response merely points to the existing annual workbooks, follow up using the specific missing aggregate/denominator distinctions above.
