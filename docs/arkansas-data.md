# Arkansas 2024–25 data

The `ar-atlas-dc-2025` snapshot fits separate Arkansas ATLAS Math, ELA and Combined models against individual same-year CCD direct certification. It contains 654 operational grade-school profiles; 653 have each subject and Combined. This conservative population excludes high schools and does not cover every public school. The income proxy is narrower than full FRPL eligibility. State thresholds are not a national scale, and associations do not measure causal effectiveness or overall school quality.

## Native post-correction school totals

The [official 2025 assessment page](https://dese.ade.arkansas.gov/Offices/public-school-accountability/assessment-test-scores/2025) links two versions of ATLAS results. Use the explicitly labeled post-correction downloads:

- [No-Grade schoolwide workbook](https://dese-admin.ade.arkansas.gov/Files/ATLAS_Summary_Post-Corrections_Scores_No-Grade_Spring_2025_PSA.xlsx), 495,374 bytes, Schools sheet with 1,017 rows and 58 columns.
- [Grade-level workbook](https://dese-admin.ade.arkansas.gov/Files/ATLAS_Summary_Post-Corrections_Scores_Spring_2025_PSA.xlsx), 1,867,466 bytes, Schools, Districts and State sheets. State rows explicitly identify grades 03–12; ELA is administered in grades 3–10, grade-level Math in 3–8, plus separate Algebra/Geometry EOCs.

Both use literal seven-digit `District LEA` and `School LEA` strings, preserving leading zeros. Charter districts can end in `700`, rather than `000`; the adapter does not discard those legitimate identities. All 1,017 native school IDs join the [same-year CCD directory](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip) through exact `ST_SCHID=AR-district-school`. Names, city, grade offers and operational status come from that historical directory. There is no name-based match, prior-year fallback or current directory backfill.

Use the already published `Math % Level 3 & 4` and `ELA % Level 3 & 4` schoolwide percentages. They are one-decimal percentage strings, never fractional units. The [2025 official report-card business rules](https://docs.google.com/document/d/1Qhf9liDMCPG34QAGGk4MQt5FrRwKhNNYMx5hLUGd2Dc/edit?usp=sharing), Module 2, define score-level percentages among tested students after assessment corrections. They include highly mobile students and distinguish score-level proficiency from participation and accountability measures. ELA includes Reading and Writing. The Reading component is distinct and is not substituted for ELA. Math Combined blends grade Math and EOCs and is not substituted for grade-level Math. Advanced students taking only EOC Math fall outside this model’s Math response. DLM alternate results are separately published and are not included in these ATLAS totals.

At the retained grade schools, complete unadjusted same-year offers and reported/derived enrolled-grade totals prove no grades 9–13, ungraded or adult programs and maximum grade 8. Thus the native tested response is grades 3–8. The adapter excludes 363 native profiles outside this scope and averages no grade percentages.

`N Tested` is retained raw but is not imported as a valid-score denominator without independent proof of its score-validity treatment. All models therefore have unavailable sampling intervals. Enrollment, participation, a 95% federal denominator or a count inferred from rounded levels is never substituted. `N<10`, `RV`, ranges, inequality rates, `---`, missing values and other protected cells stay unavailable. One retained profile has both responses unavailable.

## Individual economic eligibility

The model uses reported school-level CCD 2024–25 `Direct Certification / Education Unit Total` divided by positive reported same-year `Membership / Education Unit Total`, including pre-K where enrolled. Both counts must carry the Reported flag and the same authoritative school identity; DC greater than membership is excluded. No Arkansas-specific lunch reporting exception was listed in the downloaded final CCD notes. This is a benefits-based individual eligibility proxy; application-only eligible students are absent. Membership is a fall snapshot, so matching academic years does not establish identical collection dates.

The [official Arkansas direct certification guidance](https://dese.ade.arkansas.gov/Files/Direct_Certification_7.5.22_COMM.pdf) distinguishes verified exact matches and documented household extensions from high/low probability matches, which alone do not establish eligibility. It describes updating individual eSchool meal status through the school year. At CEP and Provision 2 schools, school meal-service and individual eligibility codes require special treatment; free meal access does not itself establish individual DC eligibility. The [NCES definition](https://nces.ed.gov/learn/blog/understanding-school-lunch-eligibility-common-core-data) likewise distinguishes individual DC counts from schoolwide free-meal or CEP reimbursement measures.

The [MySchoolInfo public statewide generator](https://myschoolinfo.arkansas.gov/Plus/Schools) was also audited. Select 2024–2025, grades, October enrollment, free/reduced counts/percentages, Direct Certification (Final) and ATLAS all-grade ELA/Math/Reading. Its actual XLSX export has 1,075 school rows: **1,060 numeric Direct Certification (Final) entries are zero and 15 are unavailable**, despite positive individual CCD DC counts. This native placeholder is not used as zero income. The report-card rule defines native low-income from meal status 1/2/4 and audited Child Nutrition data, but its treatment at special provision schools was not established as individual eligibility. Consequently neither native FRPL nor the native DC field is used as a fallback.

The public report generator has earlier two-decimal ATLAS values differing from the post-correction workbook. For example, Dewitt Middle has generator ELA 31.95% and Math 46.51%, versus post-correction ELA 31.6% and Math 46.3%. This adapter uses one explicit source release consistently and does not mix versions.

## Rebuild and audit

The compact extract preserves every native schoolwide field, row number, historical directory/grade data, individual economic counts, the unused-native-DC audit and SHA-256 checksums/URLs. Raw official files remain ignored under `data/raw`. Only the committed extract is required for default rebuilds:

```sh
.venv/bin/python scripts/prepare_arkansas.py
.venv/bin/python -m unittest discover -s tests -p test_arkansas.py -v
```

`--extract` reads the raw official files listed in `data/source/arkansas.json`; `--database PATH` supports an independently initialized SQLite store. The browser export used public `POST /Plus/RenderSchools` with `yearTrend=35,35`, `operation=export`, `response-format=xlsx` and elements `16,4,296,297,299,300,301,303,304,2035,1864,2206`. There is no authentication requirement. Default rebuilding is offline.

Tests preserve suppression and distinct ELA/Reading/Math/EOC responses, reject wrong-year/identity joins and unreported income counts, verify high-school exclusion, and independently check externally studentized residuals using deleted-school OLS for each model. Repeat import/output hashes, unrelated canonical observations, Chicago outputs and foreign keys are checked before integration. Combined is the equally weighted Math/ELA mean. No map coordinates are exported because historical campus positions were not established; schools remain available in lists and charts. History contains only 2025.
