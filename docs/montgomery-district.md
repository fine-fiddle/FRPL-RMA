# Montgomery County source and cohort audit

Montgomery County Public Schools, Maryland has an independently reconstructed 2024–25 grade-school source population of 172 schools. Matching same-year individual income and published regular MCAP rates leave 166 Math observations, 167 ELA observations and 166 Combined observations. The independent numerical audit verifies the three separate district fits and all 499 explicit deleted-school fits. Canonical integration and browser verification remain unfinished; there is no released Montgomery comparison. The immutable historical source audit retains `audit_pending` status, and both the source and numerical audit artifacts retain false source and modeling approvals.

## Original sources and identities

The [committed audit](../data/source/montgomery-district-audit.json) retains the original district records, headers, typed cells and source row numbers. The [audit script](../scripts/audit_montgomery.py) rebuilds from eleven pinned originals, rather than using the statewide extract as its only evidence:

- [MSDE 2025 directory](https://www.reportcard.msde.maryland.gov/DataDownloads/FileDownload/539), [September enrollment](https://www.reportcard.msde.maryland.gov/DataDownloads/FileDownload/541), [special services](https://www.reportcard.msde.maryland.gov/DataDownloads/FileDownload/561), and [regular MCAP workbooks](https://www.reportcard.msde.maryland.gov/DataDownloads/FileDownload/562).
- [MSDE definitions](https://www.reportcard.msde.maryland.gov/Definitions/Index), [MSDE's original reportcard assessment notes](https://reportcard.msde.maryland.gov/graphs), and the [original March 2025 MCAP overview](https://www.marylandpublicschools.org/about/Documents/DAAIT/Assessment/MCAP/MCAP-Overview-A.pdf), which currently resolves to [MSDE's PDF](https://msde.maryland.gov/media/17526).
- Original 2024–25 [CCD school directory](https://nces.ed.gov/ccd/Data/zip/ccd_sch_029_2425_w_1a_073025.zip), [school membership](https://nces.ed.gov/ccd/Data/zip/ccd_sch_052_2425_l_1a_073025.zip), [LEA directory](https://nces.ed.gov/ccd/Data/zip/ccd_lea_029_2425_w_1a_073025.zip), and [LEA membership](https://nces.ed.gov/ccd/Data/zip/ccd_lea_052_2425_l_1a_073025.zip).

Use exact NCES LEA `2400480`, CCD native LEA `MD-15`, and MSDE LEA `15`. Join the native collections using both the two-digit LEA and four-digit school code, retaining leading zeros. Each native directory `NCES Number` directly joins its same-year CCD `NCESSCH`; preserve the separate CCD `ST_SCHID` without deriving ownership from a name or an assumed identifier conversion.

The retained original inventory has 5,253 rows and 87,672 typed source cells: 211 CCD school directory rows, 1,589 CCD school total and grade rows, one CCD LEA directory row, 16 CCD LEA total and grade rows, 211 native directory rows, 1,625 native regular MCAP All Students rows, 1,376 native enrollment rows and 224 native special-services rows. All 211 authoritative school identities match exactly and are operational. There are no unmatched CCD, future, closed or charter records in these pinned district directories. The audit separately retains 18 native enrollment aggregate rows, four income aggregate rows and 24 MCAP LEA aggregate rows under school code `A`; none becomes a school observation.

The complete pinned [Maryland extract](../data/source/maryland.json) is a secondary comparison. Independently reconstructed original identities, grade scope, income and native All Grades performance agree with its 172 Montgomery grade-school profiles and 39 excluded configurations. Changing the historical statewide extract requires a fresh audit.

## School configurations and prospective population

CCD offered-grade bands are 172 grade schools, 27 high-only, five mixed and seven primary-only units. Native directory spans are 138 `E`, 40 `M`, 25 `H`, two `MH`, two `EMH`, and four unknown. These descriptions differ because the sources classify different aspects of school scope; they must not be substituted for one another.

The 172 prospective source profiles require native `E`/`M`/`EM`, an exact operational CCD identity, complete unadjusted lower-grade offers including at least one tested grade from 3–8, no high/adult/ungraded offers, and same-year native September lower-grade enrollment with no grade 9–12 row. A suppressed high-grade enrollment cell still prohibits grade-school inclusion. CCD membership is reconciled separately and never substitutes for the income denominator.

Six native elementary units remain primary-only exclusions: `15-0307`, `15-0754`, `15-0776`, `15-0780`, `15-0791`, and `15-0794`. Four native unknown spans, `15-0239`, `15-0525`, `15-0587`, and `15-0748`, remain unknown even when CCD reports offered grades. Alternative Programs `15-0239` offers grades 6–12 and has zero reported membership; it cannot enter the grade-school population. PEP–Itinerant `15-0587` has 90 reported members and unavailable income counts. Carl Sandburg Center `15-0215`, a special education school with audited lower-grade configuration, remains one of the 172 source profiles; both regular proficiency rates are masked. School type or a school's name does not remove a member from the defined source population.

The planning screen's 172 potential grade schools and 25 potential high schools is reconstructed from original records. The two additional high-only offered configurations have zero enrollment and therefore fail the planning screen. Neither planning count approves high-school models.

## Individual income, rounding and missingness

Income uses individual direct certification from MSDE's Early Attendance collection. The original definition includes SNAP/FSP, TANF/TCA, foster care, Medicaid and other individual categorical statuses. Medicaid entered the definition in 2022–23. FARMS, universal meal access, reimbursement multipliers and tested-student economic subgroups are different measures.

For each school, divide its unsuppressed `Economically Disadvantaged Cnt` by that same row's `Total Student Cnt`, checking agreement with the published one-decimal percentage within 0.0500001 percentage point. Preserve the native whole-school `All` row for multiband schools `15-0799`, `15-0916`, `15-0951` and `15-0965`; never average their elementary/middle/high bands. All four remain outside the grade-school cohort. A single elementary or middle income row establishes its native school's complete income population.

CCD and native September school membership sum to the original LEA total of 159,181. Early Attendance's LEA denominator is 159,872; the sum of known individual-school denominators is 159,747, leaving a gap of 125 with four unavailable school denominators. The audit records the gap without allocating or reconstructing it. The school income and fall denominators differ at 197 schools. September and CCD counts must never replace the Early Attendance denominator. The pinned definition names an as-of collection but does not specify its exact date.

Four grade-school incomes, `15-0410`, `15-0420`, `15-0422` and `15-0604`, have published `<= 5.0` percentages and starred economic counts. They remain unavailable, leaving 168 grade-school profiles with usable same-year income. Numeric zero is preserved as zero; suppression, ranges, blanks and missing values are not zero. Native September enrollment retains 51 masked cells. Missing total rows at three zero-membership programs remain distinct from published zero totals.

## Regular MCAP, accelerated courses and unverified counts

Use native regular `School_Level`, `Year=2025`, `Student Group=All Students`, and subject `All Grades` performance, retaining the raw whitespace in assessment labels. The prospective outcome is the native published numeric `Proficient Pct`. Original MSDE reportcard ELA and mathematics assessment notes establish proficiency as performance Levels 3 and 4 under the four-level standards introduced in 2021–22. The audit pins those original notes and retains section references and paraphrased threshold evidence separately from the overview of tested grades and courses. Grade rows, district aggregates, accountability indicators and alternate DLM cannot replace the native regular totals.

The original March 2025 overview's page 2, Note 2 documents a waiver allowing grade 6–7 students taking high-school mathematics courses to use the course exam instead of the grade-level mathematics exam for school years 2024–25 through 2027–28. The audit retains the original URL, redirect, byte count and checksum, page references and paraphrased scope evidence. Page 1 distinguishes regular MCAP from alternate DLM.

The native All Grades Math population therefore includes accelerated course exams at grade schools. The 172 source profiles have 43 Algebra I, 40 Geometry and 23 Algebra II rows, but only 40, 40 and three of those rows have numeric administrative `Tested Count`. Three elementary Algebra I rows are completely starred; row presence does not establish student participation. Among 148 profiles with entirely numeric Math component counts and a numeric All Grades count, the administrative counts reconcile exactly. This descriptive check never reconstructs a masked rate or certifies a valid-score denominator. Native totals avoid averaging percentages or dropping accelerated middle-school students.

Carl Sandburg `15-0215` has `<= 5.0` Math and ELA rates. Montgomery Village Middle `15-0557` has `<= 5.0` Math despite a numeric administrative tested count of 738; its published ELA rate remains usable. Preserving these masks and the four income masks yields 166 prospective Math, 167 ELA and 166 Combined observations. Combined is the equal mean of usable Math and ELA percentages, not the percentage proficient in both subjects.

Administrative `Tested Count` is retained only as raw evidence. Neither the pinned native files nor the overview establish its precise valid-score rules or a ten-valid-scored school minimum. Every normalized tested count, valid-score count and sampling variance remains null; all sampling intervals and floor certifications remain unavailable. The current definitions HTML links 2026 disclosure requirements, which the audit does not apply retroactively to the 2025 data. Published rates and residual studentization cannot establish counts, enrollment adjustment or causal school effectiveness.

## Offline replay and next release gates

Normal replay uses the retained committed originals and pinned statewide comparison without opening raw archives, reading a membership cache, fitting a model or touching SQLite:

```sh
.venv/bin/python scripts/audit_montgomery.py
.venv/bin/python -m unittest discover -s tests -p 'test_montgomery_audit.py' -v
```

To rebuild from the byte-pinned original downloads already present under `data/raw/`, run:

```sh
.venv/bin/python scripts/audit_montgomery.py --extract
```

All original files, retained records, definitions, headers, derived coverage and source-only approval flags are checked during replay. The independent numerical phase below verifies cohort income variation, rank, leverage, externally studentized residuals and every deleted-school fit. Only separately tested canonical and static integration can later release this district. High, mixed, unknown and primary populations remain excluded from that proposed grade-school comparison.

## Independent numerical audit — integration pending

The [committed numerical audit](../data/source/montgomery-model-audit.json) and [standalone numerical script](../scripts/audit_montgomery_models.py) pin the complete historical source artifact, its source code and source tests. They retain the complete original records, definitions, 211 authoritative identities, 172 grade-school profiles, all masks and the 39 outside configurations. Native original records independently reconstruct eligibility and precise individual income before any fit. Same-year Early Attendance count ratios and published regular MCAP All Grades proficiency enter three unweighted district models; the Maryland statewide coefficients and residuals are not reused.

The fixed populations produce:

| Diagnostic | Math | ELA | Combined |
| --- | ---: | ---: | ---: |
| Usable schools | 166 | 167 | 166 |
| Intercept | 76.191625 | 89.749549 | 82.923827 |
| Income slope | -0.938743 | -0.966343 | -0.950566 |
| R² | 0.694284 | 0.864590 | 0.830700 |
| Maximum leverage | 0.026853 | 0.026442 | 0.026853 |
| Maximum Cook distance | 0.058362 | 0.068840 | 0.064461 |
| Largest deleted prediction change across observed income range, percentage points | 0.583442 | 0.374375 | 0.409386 |

Income spans 6.344171–69.555035% in every model, with 165 distinct values in Math/Combined and 166 in ELA. Population standard deviations are 17.404868 and 17.438370 percentage points respectively. Each full intercept-plus-income design has rank two and positive residual scale. Every explicitly deleted design retains rank two and positive finite residual sum of squares and residual scale. Full residual degrees of freedom are 164/165/164; deleted training populations are 165/166/165, and deleted residual degrees of freedom are 163/164/163.

The independent verifier uses centered full OLS and explicitly refits each of the 499 omissions. It computes the held-out prediction, predictive leverage and deleted residual scale, then compares externally studentized residuals with the shared analytic implementation. Studentization uses the residual scale estimated from the other `N−1` schools and `N−3` degrees of freedom; dividing all residuals by one common standard deviation does not reproduce these results. The separate Combined fit uses the equal mean of its eligible Math and ELA rates and its own externally studentized residuals; averaging subject residual scores would give different results.

Conventional leverage, Cook distance and absolute studentized-residual flags are descriptive review aids. No school is removed because of a diagnostic flag or fit quality. The largest prediction changes above apply to the model's observed income range. They do not certify predictions outside that range, causal school effectiveness, enrollment adjustment or shrinkage.

All eligible administrative `Tested Count` values remain raw, unverified evidence. Every valid-score count, sampling variance and interval endpoint remains null across each full model. The ten-valid-scored floor remains uncertified. Published rate precision, suppression, different income and assessment populations, and accelerated course mixtures remain explicit limits. The numerical artifact's status is `numerically_verified_pending_integration`, its scope is `numerical_audit_only`, and both source and modeling approvals remain false. The immutable historical source audit keeps its original false approvals and `audit_pending` status.

The numerical builder and saved replay operate offline without raw downloads or SQLite access:

```sh
.venv/bin/python scripts/audit_montgomery_models.py
.venv/bin/python scripts/audit_montgomery_models.py --check
.venv/bin/python -m unittest discover -s tests -p 'test_montgomery_models.py' -v
```

This phase produces an auditable numerical artifact. A separately tested canonical/static/browser adapter is the next release gate; no Montgomery catalog entry, browser payload or district release is approved by these fits alone.
