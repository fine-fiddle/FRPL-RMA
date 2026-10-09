# Connecticut source audit

Connecticut is not yet available as a model. Official sources identify an appropriate same-year individual meal-eligibility measure, but the documented native guest export currently fails in both HTTP and browser access.

## Audited official sources

- [EdSight Smarter Balanced achievement](https://public-edsight.ct.gov/performance/smarter-balanced-achievement-participation) links to a native SAS assessment report and [report notes](https://edsight.ct.gov/relatedreports/ReportNotes_SmarterBalanced.pdf).
- [Free and Reduced-Price Meal Eligibility Export](https://public-edsight.ct.gov/students/enrollment-dashboard/free-and-reduced-price-meal-eligibility-export) explicitly describes the PSIS October Collection. Eligibility means individual eligibility for free/reduced-price meals or free milk under income guidelines, or categorical eligibility such as SNAP, TANF, or homelessness. This is an appropriate candidate income definition; universal meal service is not a substitute.
- [Public School Enrollment Export](https://public-edsight.ct.gov/students/enrollment-dashboard/public-school-enrollment-export) provides a companion enrollment view.
- [Connecticut School Day SAT](https://public-edsight.ct.gov/performance/connecticut-school-day-sat) has separate assessment/report notes and would need a distinct high-school cohort.

## Concrete access obstacle

On October 9, 2026, the public assessment page's linked `SmarterBalancedAssessmentReport_SiteCore` request redirected to the SAS login form. The public guest route also redirected to SAS login. We did not authenticate or substitute cached search results for a complete native export.

The income and enrollment pages embed a guest SAS Visual Analytics report on `https://edsight-v.ct.gov`, report URI `/reports/reports/31baedc2-3372-4d1b-884a-4b7fb924c23f`, pages `vi4889` and `vi833`. Their documented export route is the embedded object's **Export to Excel** menu. Fetching the report URI directly returned HTTP 401. On October 9, 2026, a separate browser visit to the documented public income export confirmed the embedded message **“Unable to log on to the server.”** The browser console reported **“[authorization] Unable to log in as guest.”** No school-year or Export controls rendered. Page/report responses are retained locally under ignored `data/raw/connecticut/`.

This establishes an access gap, not missing official data. Before importing, obtain the complete native 2024–25 school-level exports, verify authoritative school identifiers, valid-score definitions, suppression and grade-school/SAT populations, and reconcile every percentage. Smarter Balanced grade percentages must not be averaged using enrollment weights. No canonical Connecticut observations, guessed denominator counts, inferred name joins, or browser-ready placeholder models were created.
