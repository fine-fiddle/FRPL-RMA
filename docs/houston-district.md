# Houston ISD 2024–25 source and numerical audits

The source audit independently reopens the original state and federal sources for Houston ISD, NCES LEA `4823640`, native agency `TX-101912` and TAPR `DISTRICT` `101912`. Its committed evidence is [houston-district-audit.json](../data/source/houston-district-audit.json), whose pure validator recomputes the roster, exclusions and prospective subject availability without fitting or importing. The separate [published-rate numerical audit](#published-rate-numerical-contract) uses original whole-percent displays under an explicit unknown-count policy. Both artifacts retain false source/model approvals and create no district comparison.

## Exact same-year roster

The original 2024–25 CCD directory attaches 274 open schools to the exact district: 261 regular, ten alternative and three special education schools. Seven are labeled charter schools. These flags are retained as evidence; they do not remove schools from the source population. The original CCD native identity has the complete format `TX-101912-101912068`, whose final nine digits match TAPR `CAMPUS` `101912068`. Names never join.

The three native TAPR CSV tables each contain the same 273 Houston campus identities. The remaining CCD school is EL DAEP, native `101912466`, NCES `482364012656`, with reported-zero CCD membership and no native TAPR campus row. Absence is retained; no zero income or outcome is created. All 273 matched native enrollment totals equal their individual CCD school membership totals. Both school sums and the separate CCD agency total equal 176,727.

TAPR also reports a distinct PEIMS membership count of 176,039, different from enrollment at 150 campuses. The glossary distinguishes membership from enrollment because some pupils receive less than two hours of service. The income denominator uses the native enrolled count, rather than substituting the membership count. Neither administrative total is an assessment denominator. Original CSV headers, labels, row numbers and complete raw values are retained, including both enrollment and membership fields. The CCD `RECON_STATUS` flag is also preserved: four schools report Yes, and this label does not exclude them.

## Native enrolled-grade population

Cohort selection uses the complete 2025 native enrolled counts for early childhood, pre-K, kindergarten and grades 1–12. Their sum reconciles with native enrollment for every Houston campus. Pre-K three/four-year-old fields are retained as subcategories and are not added twice.

| Native enrollment configuration | Campuses | Prospective Math / ELA / Combined availability |
| --- | ---: | ---: |
| Positive grades 3–8, no grades 9–12 | 212 | 210 / 210 / 210 |
| Early childhood/primary only, no positive grades 3–8 | 10 | 0 / 0 / 0 |
| High only | 42 | Outside audited grade-school population |
| Mixed lower/high grades | 9 | Outside audited grade-school population |

The 222 no-high-grade profiles include the ten primary-only campuses, which remain outside the proposed assessment population. There are no incomplete or unknown native grade vectors in this snapshot; the validator preserves unknown/masked grade evidence as an unclassified configuration when evaluating its pure helper. All high and mixed records remain in the audit, with explicit exclusions.

T H Rogers School `101912039` is an essential boundary check: its reference type is E and span is `EE - 08`, but its native enrollment includes four grade-nine, seven grade-ten, seven grade-eleven and thirteen grade-twelve pupils. These 31 high-grade pupils require mixed classification despite the reference label. The other eight mixed campuses also remain outside the grades 3–8 population. Seven mixed campuses have arithmetically usable native subject fields, but those fields do not audit a mixed-school assessment population or meet a separate 30-school cohort floor. Three charter campuses are among the 210 prospective grade-school members; other charter campuses remain in their actual enrollment configurations.

The original CCD planning replay reproduces 212 potential grade schools and 42 potential high schools. Planning remains a separate identity and size check. LAS AMERICAS `101912340` / NCES `482364008608` has blank native subject totals; SECONDARY DAEP `101912402` / NCES `482364012655` has native `-1` masked totals. These are the only two exclusions from prospective grade-school subject availability. Missing and masked fields remain distinct raw evidence.

## Individual economic status

The native 2025 enrollment fields report status as of October 25, 2024. For all 273 campuses, economic-disadvantage and non-disadvantage counts sum to enrollment, and the reported tenth-percent display reconciles with the exact count ratio. District enrollment is 176,727 and economic-disadvantage enrollment is 137,435. No income is backfilled from another year.

The [2024–25 TEDS student reporting guide](https://www.texasstudentdatasystem.org/sites/texasstudentdatasystem.org/files/TEDS_Data_Submission_Requirements_Student_Identification_and_Demographics_Domain.pdf), physical pages 36–40, describes individual codes 01/02/99: free/reduced meal eligibility or other economic disadvantage. CEP requires individual direct certification and annual local income surveys for other pupils; receiving universal meals does not classify every pupil as disadvantaged. Provision 2 can retain base-year eligibility for continuously enrolled students, so administrative status can lag current family income. Unreturned surveys can be code 00; reporting undercount is unknown. Other assistance makes this a broader state-specific proxy than uniform FRPL or household income, and the all-enrolled income population is broader than the tested grades 3–8 population.

The [official income-verification extension](https://tea.texas.gov/taa-letters/school-year-2024-2025-income-eligibility-verification-forms-extension) allows documentation updates through January 16, 2025 while requiring pupils to have been enrolled and eligible on October 25, 2024. The archived primary page is pinned and retained as definition evidence.

## Published performance arithmetic and denominator hold

The exact All Students fields are `CDA38AM0E025D`, `CDA38AM0E225N`, `CDA38AM0E225R` for Math and the corresponding `…AR…` fields for ELA. The original CSV labels and native dictionary identify the enrolled-grades 3–8 Math/Reading Including EOC performance denominator, number at Meets Grade Level or Above, and published percentage. Direct subject totals are used; grade-level percentages are never averaged. Where all three fields are unmasked, the numerator/count ratio reconciles to the whole-percent display within rounding tolerance. A masked percentage is never reconstructed from visible counts. Blank, `-1`, `-2`, `-3`, bullet and asterisk values remain unavailable; an unsuppressed zero percentage is a real zero.

The [2024–25 TAPR glossary](https://tea.texas.gov/school-and-district-leaders/accountability/academic-accountability/performance-reporting/2024-25-comprehensive-tapr-glossary-0.pdf), physical pages 1–3, defines the TAPR accountability subset as pupils at the same district/campus on the fall snapshot and testing date. It includes STAAR with/without accommodations, Spanish STAAR and Alternate 2, and corresponding Algebra I or English I/II EOC outcomes for enrolled grades 3–8. The separate TPRS all-testers population and native percentage passing both subjects are not used. Combined is the equal mean of Math and ELA subject proficiency; it does not describe pupils proficient in both.

There are 217 reconciled native performance totals per subject, including seven mixed campuses outside the proposed population. Prospective grade-school availability is 210 each, screened using individual income, unmasked matching subject fields and native reported performance counts of at least ten. These 210 subject records have a minimum reported denominator of 72. Math totals are 62,468 reported tests / 30,826 at Meets or Above; ELA totals are 62,519 / 33,808. These are reported performance counts and arithmetic checks, **not certified valid-score counts**. The source's masking rule for small denominators 1–4 and the repository's minimum ten valid scored tests are distinct rules. Reported counts above ten do not yet certify that valid-scored requirement.

The [2025 Accountability Manual](https://tea.texas.gov/texas-schools/accountability/academic-accountability/performance-reporting/2025-accountability-manual-full.pdf), printed pages 168/172 (physical 173/177), establishes that CAF corrections feed TAPR and that A/Absent and O/Other score codes are excluded from performance calculations. Its participation section remains separately retained. The [2025 performance/participation student-listing guide](https://sboe.texas.gov/texas-schools/accountability/academic-accountability/performance-reporting/interpreting-staar-performance-participation-student-list-2025.pdf), physical pages 4/6/8, distinguishes performance and participation statuses and lists S/M/N/A/O codes. **Current primary evidence does not explicitly map N/NAAR and M/medical exemptions to these exact enrolled-grade TAPR `#Tests` fields.** Older-year FAQs do not resolve the 2025 gate, and EL performance-measure substitutions are not assumed to apply to these fields.

Accordingly, every verified-valid-score count, sampling variance and interval remains null/unavailable, and the ten-valid-scored-test requirement remains uncertified. The numerator/denominator/display arithmetic and point-rate availability are preserved; the unresolved mapping is a verification limit, not evidence that the published state results are incorrect.

## Replay and release criteria

```sh
.venv/bin/python scripts/audit_houston.py --extract
.venv/bin/python scripts/audit_houston.py
.venv/bin/python -m unittest discover -s tests -p test_houston_audit.py -v
```

`--extract` checks original source bytes and checksums, then reparses all saved TAPR CSV/PDF/HTML files and original CCD directory/membership archives. Default replay uses the committed evidence and pinned historical Texas extract offline. Source row/header/value fingerprints and typed metadata reject drift. Neither path touches SQLite, computes a regression, exports browser data or changes the statewide Texas population.

Under the historical count-based contract, district release requires resolving the exact current-year N/M performance-denominator mapping and scored-count floor; separately auditing the proposed numerical fits, all-member uncertainty rules and diagnostics; implementing and verifying the canonical repeatable importer and served comparison; and verifying the browser, shared links and assessment guide. Any later point-only release requires its own explicit review and unavailable-interval labeling. High/mixed assessments, admission or school-program classifications, coordinates, provider roles and cross-assessment relative ambition are not audited here. Statistical results, when released, will describe associations rather than causal effectiveness or overall school quality.

## Completed source verification

Two independent original-source reviews pass. The final replay retains 273 native campuses, 212 prospective grade-school profiles and 210 available records per subject. Two original-source extractions reproduce identical audit bytes. Independent review also passes 123 document-corruption rejection cases and 69 semantic/edge checks. The 56 targeted Python tests cover Houston, Texas extraction, district planning and nearby audit contracts. Every earlier served data file and the canonical database remain unchanged. At the source phase, the 69 first-tier and 172 second-tier candidate queue was unchanged and numerical/integration work remained pending.

[Issue #16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) records the precise scored-count evidence gate and its release criteria. [Issue #17](https://github.com/robot-assisted-projects/FRPL-RMA/issues/17) records the separate Texas CSV extraction defect: the original assessment labels say `SY 2024-25`, while income labels say `2025`. The repaired year check accepts those current labels and rejects prior-year labels. Independent temporary extraction reproduces all 9,084 original campuses twice and exactly preserves all 6,573 historical normalized profiles. That repair changes neither the published Texas data nor the unresolved denominator gate. The original PDF replay dependency is pinned as `pypdf==6.20.0` in [requirements.txt](../requirements.txt).

## Published-rate numerical contract

The separate [houston-model-audit.json](../data/source/houston-model-audit.json) audits a distinct point-only outcome: the original unmasked whole-percent All Students Meets-or-above fields `CDA38AM0E225R` and `CDA38AR0E225R`. It pins the complete source artifact and retains every original definition, raw value, identity and population exclusion. It never rewrites the historical source audit's count-ratio arithmetic or promotes its approval flags.

Eligibility is independently derived from exact operational district attachments, complete native enrolled grades 3–8 with no positive grades 9–12, reconciled same-year individual economic status, and the subject's unmasked published percentage. The reported performance counts do not set membership in this contract and are not certified as valid scored results. There are 212 native grade-school profiles and 210 usable published-rate members per subject, preserving the original missing and masked campus exclusions. High, mixed, primary-only and absent-native records remain outside these models.

The predictor remains exact individual economic-disadvantage enrollment divided by native enrollment; the outcome retains the published whole-percent precision. The new Math outcome differs from count-derived precision at 202 schools and ELA at 203 schools. Combined is the equally weighted mean of those two published subject rates, requiring both; it never uses the native percentage passing both subjects. Separate district Math, ELA and Combined models use equal school weights and externally studentized residuals. Diagnostics cannot change membership.

This explicit unknown-count policy permits a numerical investigation under the repository's point-only mechanism; it does not certify the ten-valid-scored-test requirement. Valid-score counts, sampling variances and every interval endpoint stay null for all model members. A zero vector used inside the fitter is only a computational sentinel. School enrollment and reported performance counts remain provenance, never substitute denominators. Rounded native rates, the broader all-enrolled economic-status proxy, assessment-type/grade mix and omitted prior attainment or admissions remain limitations. Residuals describe associations, not causal school quality.

Canonical/static integration remains a separate audited unit. It must explicitly validate the published-rate eligibility contract, preserve the uncertified scored-count floor and unavailable-interval caveats, verify repeatable imports and every earlier comparison, and pass HTTP browser checks before readiness. [Issue #16](https://github.com/robot-assisted-projects/FRPL-RMA/issues/16) stays open for exact N/M score-status mapping; numerical success does not resolve count-based release criteria or establish that existing statewide Texas results are wrong. Provider roles, admissions classifications, geometry and high/mixed assessment scope remain unaudited. Houston remains a candidate in the unchanged 69/172 queue.

```sh
.venv/bin/python scripts/audit_houston_models.py
.venv/bin/python scripts/audit_houston_models.py --check
.venv/bin/python -m unittest discover -s tests -p test_houston_models.py -v
```

The numerical replay validates the pinned source and recomputes all fits offline. It touches neither SQLite nor served JSON. The source-only commands above remain valid and reproduce the unchanged historical audit.

## Independent published-rate fits

Each subject retains all 210 published-rate members, including three charters and one alternative school. All 630 explicit deleted-school fits use 209 training schools and 207 residual degrees of freedom, with rank-two designs and positive residual scales. The largest line shift over observed economic disadvantage after removing a school is 0.930174 proficiency points. The recorded leverage, Cook distance and residual flags are descriptive; no school is removed by a fit diagnostic.

| Subject | Intercept | Slope per economic-status point | R² | Largest deleted-line shift (proficiency points) |
| --- | ---: | ---: | ---: | ---: |
| Math | 79.570354 | -0.387219 | 0.463701 | 0.930174 |
| ELA | 92.140631 | -0.485618 | 0.643799 | 0.620842 |
| Combined | 85.855493 | -0.436419 | 0.597476 | 0.766564 |

These coefficients belong only to the separate Houston published-rate audit and are never substituted for statewide Texas results. The numerical status is `numerically_verified_pending_integration`, with both approvals false; the unresolved count-definition hold and all unavailable interval values remain explicit.

## Completed numerical verification

Forty targeted Python tests pass: twelve new Houston numerical tests and 28 Houston source, Texas extraction and district-planning regression tests. Two independent reviews reproduce the original inputs and all 630 deleted fits. They also pass 238 corruption rejection cases and 62 semantic/edge checks; these additional 300 checks are separate from the test count. One review independently compares all 70,434 original retained CSV cells, and both compare the original-rate inputs and numerical results.

Two numerical builds and an offline saved replay reproduce identical bytes. The immutable source audit, every prior served file (225 files), canonical database bytes and all earlier source/model artifacts remain unchanged. The district planner preserves its extract and 69 first-tier / 172 second-tier queue. No canonical import, served export, assessment-guide change, master merge or deployment occurs in this numerical phase. Separately audited canonical/browser integration remains next; #3, #16, Detroit #15 and all state source holds stay open.
